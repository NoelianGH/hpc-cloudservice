"""
Login web relawan: HANYA email + password.

Kredensial dipisah menurut pemakainya:
  - Email + password  -> MANUSIA di website. Login membuat SESI web (hpc_ws_...), disimpan
    browser di cookie httpOnly, hanya untuk endpoint dashboard (/api/me, jobdesk, sertifikat).
  - Token node (hpc_ng_...) -> ssh + git di compute node, satu per jobdesk (node_access.py).
  - Token worker (hpc_w_...) -> MESIN worker CPU (pengujian), diatur admin lewat ./hpc.sh / .env.
    Tidak ditampilkan dan tidak bisa dipakai di website.

Tabel worker_sessions hanya menyimpan hash SHA-256 token sesi (lihat schema.py).
Akun lama tanpa password: atur password lewat kode OTP email (password_reset).

Endpoint:
  POST /api/auth/login                {email, password}
  POST /api/auth/logout               hapus sesi web
  GET  /api/auth/session              identitas pemilik sesi (untuk navbar)
  POST /api/auth/password/request     {email} -> kirim kode OTP atur ulang password ke email
  POST /api/auth/password/reset       {email, otp, password} -> password baru, semua sesi lama keluar
  POST /api/me/password               buat / ganti password (butuh sesi web)
  POST /api/me/profile                ubah profil (nama, username, ...; butuh sesi web)
"""
import os
import secrets
import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from admin_auth import DUMMY_HASH, hash_password, hash_token, verify_password
from common import db, client_ip
from email_service import generate_otp, send_email

SESSION_DAYS = float(os.environ.get("WORKER_SESSION_DAYS", "7") or 7)
MIN_PASSWORD_LEN = 8
SESSION_PREFIX = "hpc_ws_"

# Kunci sementara setelah banyak password salah (per email dan per IP), seperti login admin
LOCK_SECONDS = 15 * 60
MAX_FAILS_EMAIL, MAX_FAILS_IP = 5, 20
_fails: dict[str, list[float]] = {}

router = APIRouter(tags=["login relawan"])


def check_password_rule(password: str) -> None:
    if len(password) < MIN_PASSWORD_LEN:
        raise HTTPException(400, f"Password minimal {MIN_PASSWORD_LEN} karakter.")
    if len(password) > 200:
        raise HTTPException(400, "Password terlalu panjang (maks. 200 karakter).")


def _bearer(auth: str | None) -> str | None:
    if auth and auth.startswith("Bearer "):
        return auth[7:].strip() or None
    return None


def _locked(key: str) -> bool:
    now = time.time()
    recent = [t for t in _fails.get(key, []) if now - t < LOCK_SECONDS]
    if recent:
        _fails[key] = recent
    else:
        _fails.pop(key, None)
    return len(recent) >= (MAX_FAILS_EMAIL if key.startswith("email:") else MAX_FAILS_IP)


def _record_fail(key: str) -> None:
    if len(_fails) > 10_000:
        _fails.clear()
    _fails.setdefault(key, []).append(time.time())


def worker_from_session(auth: str | None) -> dict | None:
    """Worker pemilik sesi web (hpc_ws_...), atau None bila bukan sesi web / sudah habis."""
    token = _bearer(auth)
    if not token or not token.startswith(SESSION_PREFIX):
        return None
    with db() as c:
        w = c.execute("""
            SELECT w.id, w.name, w.github_username, w.email, w.status, w.username,
                   w.first_name, w.last_name,
                   coalesce(w.show_in_appreciation, false) AS show_in_appreciation,
                   w.appreciation_consent_at, w.password_hash IS NOT NULL AS has_password,
                   s.expires_at
              FROM worker_sessions s JOIN workers w ON w.id = s.worker_id
             WHERE s.token_hash = %s AND s.expires_at > now()""", (hash_token(token),)).fetchone()
        if w:
            c.execute("UPDATE worker_sessions SET last_used_at = now() WHERE token_hash = %s",
                      (hash_token(token),))
    if not w:
        raise HTTPException(401, "Sesi login sudah berakhir. Silakan login lagi.")
    if w["status"] != "active":
        raise HTTPException(403, f"Akun relawan '{w['name']}' ditangguhkan admin ({w['status']}).")
    return w


def check_volunteer_auth(auth: str | None, web_only: bool = True) -> dict:
    """
    Autentikasi endpoint dashboard relawan: hanya sesi web (hpc_ws_...). Token worker
    (hpc_w_...) tidak lagi diterima di website. Argumen web_only dipertahankan agar
    pemanggil lama tetap jalan. Mengembalikan {"type": "individual", "worker": {...}, "via": "web"}.
    """
    w = worker_from_session(auth)
    if w:
        return {"type": "individual", "worker": w, "via": "web"}
    raise HTTPException(401, "Butuh login website (email + password).")


def _new_session(c, worker_id: str, request: Request, user_agent: str | None) -> tuple[str, datetime]:
    token = SESSION_PREFIX + secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    c.execute("DELETE FROM worker_sessions WHERE expires_at < now()")
    c.execute("""INSERT INTO worker_sessions (token_hash, worker_id, expires_at, ip, user_agent)
                 VALUES (%s, %s, %s, %s, %s)""",
              (hash_token(token), worker_id, expires, client_ip(request), (user_agent or "")[:200]))
    return token, expires


class LoginBody(BaseModel):
    email: str | None = None
    password: str | None = None


@router.post("/api/auth/login")
def volunteer_login(body: LoginBody, request: Request, user_agent: str = Header(None)):
    ip = client_ip(request)
    email = (body.email or "").strip().lower()
    password = body.password or ""
    if not email or not password:
        raise HTTPException(400, "Email dan password wajib diisi.")
    keys = [f"email:{email}", f"ip:{ip}"]
    if any(_locked(k) for k in keys):
        raise HTTPException(429, "Terlalu banyak percobaan login gagal. Coba lagi 15 menit lagi.")
    with db() as c:
        rows = c.execute("""SELECT id, name, github_username, email, status, password_hash
                              FROM workers WHERE lower(email) = %s AND password_hash IS NOT NULL
                             ORDER BY created_at""", (email,)).fetchall()
    w = next((r for r in rows if verify_password(password, r["password_hash"])), None)
    if not rows:
        verify_password(password, DUMMY_HASH)  # waktu respons sama walau email tidak ada
    if not w:
        for k in keys:
            _record_fail(k)
        raise HTTPException(401, "Email atau password salah. Belum punya password / lupa? "
                                 "Pilih 'Lupa / belum punya password?' untuk kode OTP lewat email.")
    for k in keys:
        _fails.pop(k, None)
    if w["status"] != "active":
        raise HTTPException(403, f"Akun relawan '{w['name']}' ditangguhkan admin ({w['status']}).")
    with db() as c:
        token, expires = _new_session(c, w["id"], request, user_agent)
    print(f"[RELAWAN] Login web: {w['name']} (@{w['github_username']}) dari {ip}", flush=True)
    return {"session": token, "expires_at": expires.isoformat(), "worker_name": w["name"],
            "github_username": w["github_username"], "has_password": True}


@router.post("/api/auth/logout")
def volunteer_logout(authorization: str = Header(None)):
    token = _bearer(authorization)
    if token and token.startswith(SESSION_PREFIX):
        with db() as c:
            c.execute("DELETE FROM worker_sessions WHERE token_hash = %s", (hash_token(token),))
    return {"ok": True}


@router.get("/api/auth/session")
def volunteer_session(authorization: str = Header(None)):
    w = worker_from_session(authorization)
    if not w:
        raise HTTPException(401, "Belum login.")
    return {"worker_id": w["id"], "worker_name": w["name"], "github_username": w["github_username"],
            # Nama tampilan navbar: PREFERRED USERNAME dari Register, cadangannya username GitHub
            "username": w["username"] or w["github_username"] or w["name"],
            "has_password": w["has_password"], "expires_at": w["expires_at"]}


class PasswordBody(BaseModel):
    password: str
    current_password: str | None = None


@router.post("/api/me/password")
def set_password(body: PasswordBody, authorization: str = Header(None)):
    w = check_volunteer_auth(authorization, web_only=True)["worker"]
    check_password_rule(body.password)
    with db() as c:
        cur = c.execute("SELECT password_hash FROM workers WHERE id = %s", (w["id"],)).fetchone()
        if cur["password_hash"] and not verify_password(body.current_password or "", cur["password_hash"]):
            raise HTTPException(400, "Password lama salah.")
        c.execute("UPDATE workers SET password_hash = %s WHERE id = %s", (hash_password(body.password), w["id"]))
    return {"ok": True, "message": "Password tersimpan. Mulai sekarang login website pakai email + password."}


class ProfileUpdateBody(BaseModel):
    name: str | None = None
    worker_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    email: str | None = None
    github_username: str | None = None


@router.post("/api/me/profile")
def update_profile(body: ProfileUpdateBody, authorization: str = Header(None)):
    w = check_volunteer_auth(authorization)["worker"]
    with db() as c:
        updates = []
        params = []
        fn = body.first_name.strip()[:50] if body.first_name is not None else None
        ln = body.last_name.strip()[:50] if body.last_name is not None else None
        un = body.username.strip()[:30] if body.username is not None else None
        wn = (body.worker_name or body.name or "").strip()[:50] if (body.worker_name is not None or body.name is not None) else None

        if fn is not None:
            updates.append("first_name = %s")
            params.append(fn)
        if ln is not None:
            updates.append("last_name = %s")
            params.append(ln)
        if un is not None:
            updates.append("username = %s")
            params.append(un)
        if wn is not None and wn:
            updates.append("name = %s")
            params.append(wn)

        # Email dan username GitHub sudah DIVERIFIKASI saat daftar (OTP email + cek akun GitHub),
        # jadi tidak bisa diganti dari profil. Mengganti keduanya = daftar ulang lewat halaman Register
        # (verifikasi GitHub + OTP lagi) atau lewat admin.
        cur = c.execute("SELECT email, github_username FROM workers WHERE id = %s", (w["id"],)).fetchone()
        if body.email is not None and body.email.strip().lower() != (cur["email"] or "").strip().lower():
            raise HTTPException(400, "Email tidak bisa diganti dari profil (sudah diverifikasi OTP). "
                                     "Daftar ulang lewat halaman Register atau hubungi admin.")
        gh = (body.github_username or "").strip().lstrip("@")
        if body.github_username is not None and gh.lower() != (cur["github_username"] or "").lower():
            raise HTTPException(400, "Username GitHub tidak bisa diganti dari profil (sudah diverifikasi). "
                                     "Daftar ulang lewat halaman Register dengan akun GitHub baru.")
        if updates:
            params.append(w["id"])
            c.execute(f"UPDATE workers SET {', '.join(updates)} WHERE id = %s", tuple(params))
    return {"ok": True, "message": "Profil berhasil diperbarui."}


# ---------------------------------------------------------------------------- atur ulang password

RESET_MINUTES = 10
RESET_MAX_ATTEMPTS = 5
RESET_COOLDOWN_S = 60


def _otp_hash(email: str, otp: str) -> str:
    return hashlib.sha256(f"{email}:{otp}".encode()).hexdigest()


class ResetRequestBody(BaseModel):
    email: str


@router.post("/api/auth/password/request")
def password_reset_request(body: ResetRequestBody, request: Request):
    """
    Kirim kode OTP ke email akun relawan (akun lama tanpa password / lupa password).
    Jawaban selalu sama, ada atau tidak akunnya, agar email terdaftar tidak bisa ditebak.
    Kode TIDAK pernah dikirim ke browser; di mode dev email, kode hanya tampil di log koordinator.
    """
    email = (body.email or "").strip().lower()
    generic = {"ok": True, "message": f"Bila {email or 'email itu'} terdaftar, kode OTP sudah dikirim "
                                      f"(berlaku {RESET_MINUTES} menit)."}
    ip = client_ip(request)
    if not email or "@" not in email or len(email) > 200:
        raise HTTPException(400, "Email tidak valid.")
    # Batas per EMAIL (bukan per IP: lewat website semua permintaan datang dari IP server web)
    key = f"reset:{email}"
    recent = [t for t in _fails.get(key, []) if time.time() - t < LOCK_SECONDS]
    if len(recent) >= 5:
        raise HTTPException(429, "Terlalu banyak permintaan kode untuk email ini. Coba lagi 15 menit lagi.")
    _record_fail(key)
    with db() as c:
        w = c.execute("""SELECT id, name, email, status FROM workers WHERE lower(email) = %s
                          ORDER BY created_at DESC LIMIT 1""", (email,)).fetchone()
        if not w or w["status"] != "active":
            return generic
        last = c.execute("""SELECT extract(epoch FROM now() - created_at) AS age FROM worker_password_resets
                             WHERE email = %s""", (email,)).fetchone()
        if last and last["age"] < RESET_COOLDOWN_S:
            return generic   # kode sebelumnya masih baru: tidak dikirim ulang (jawaban tetap sama)
        otp = generate_otp(6)
        c.execute("""INSERT INTO worker_password_resets (email, worker_id, otp_hash, expires_at, attempts, created_at)
                     VALUES (%s, %s, %s, now() + make_interval(mins => %s), 0, now())
                     ON CONFLICT (email) DO UPDATE SET worker_id = EXCLUDED.worker_id, otp_hash = EXCLUDED.otp_hash,
                         expires_at = EXCLUDED.expires_at, attempts = 0, created_at = now()""",
                  (email, w["id"], _otp_hash(email, otp), RESET_MINUTES))
    res = send_email(w["email"], "Kode atur password HPC Cloud Service",
                     f"Halo {w['name']},\n\nKode untuk mengatur password website HPC Cloud Service: {otp}\n"
                     f"Berlaku {RESET_MINUTES} menit. Abaikan email ini bila Anda tidak memintanya.\n")
    if res.get("status") not in ("sent", "dev"):
        print(f"[RELAWAN] Kirim OTP atur password ke {email} gagal: {res}", flush=True)
    print(f"[RELAWAN] Kode atur password diminta untuk {w['name']} ({email}) dari {ip}", flush=True)
    return generic


class ResetBody(BaseModel):
    email: str
    otp: str
    password: str


@router.post("/api/auth/password/reset")
def password_reset(body: ResetBody):
    email = (body.email or "").strip().lower()
    otp = (body.otp or "").strip()
    check_password_rule(body.password)
    with db() as c:
        r = c.execute("""SELECT worker_id, otp_hash, attempts, expires_at > now() AS valid
                           FROM worker_password_resets WHERE email = %s FOR UPDATE""", (email,)).fetchone()
        if not r or not r["valid"] or r["attempts"] >= RESET_MAX_ATTEMPTS:
            raise HTTPException(400, "Kode OTP tidak berlaku (kedaluwarsa / terlalu banyak salah). Minta kode baru.")
        if not hmac.compare_digest(r["otp_hash"], _otp_hash(email, otp)):
            c.execute("UPDATE worker_password_resets SET attempts = attempts + 1 WHERE email = %s", (email,))
            raise HTTPException(400, f"Kode OTP salah. Sisa percobaan: {max(0, RESET_MAX_ATTEMPTS - r['attempts'] - 1)}")
        c.execute("UPDATE workers SET password_hash = %s WHERE id = %s",
                  (hash_password(body.password), r["worker_id"]))
        c.execute("DELETE FROM worker_sessions WHERE worker_id = %s", (r["worker_id"],))   # sesi lama keluar
        c.execute("DELETE FROM worker_password_resets WHERE email = %s", (email,))
    _fails.pop(f"email:{email}", None)
    print(f"[RELAWAN] Password website diatur ulang lewat OTP: {email}", flush=True)
    return {"ok": True, "message": "Password tersimpan. Silakan login dengan email + password baru."}
