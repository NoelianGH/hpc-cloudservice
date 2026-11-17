"""
Login web relawan (email + password) dan pemisahannya dari token worker (CLI).

Dua kredensial, dua kegunaan:
  - WORKER_TOKEN (hpc_w_...)  -> dipakai MESIN: kontainer worker mengirimnya sebagai
    Authorization: Bearer di setiap /api/register, /api/tasks/claim, /api/heartbeat,
    /api/tasks/submit. Disimpan di file .env repo worker. Tidak pernah dipakai browser.
  - Email + password          -> dipakai MANUSIA di website. Login membuat SESI web
    (hpc_ws_...), yang disimpan browser di cookie httpOnly dan hanya bisa membuka
    endpoint dashboard (/api/me, jobdesk, sertifikat, apresiasi), BUKAN mengambil tugas.

Tabel worker_sessions hanya menyimpan hash SHA-256 token sesi (lihat schema.py).

Endpoint:
  POST /api/auth/login            {email, password} atau {token} (sekali, untuk akun lama tanpa password)
  POST /api/auth/logout           hapus sesi web
  GET  /api/auth/session          identitas pemilik sesi (untuk navbar)
  POST /api/me/password           buat / ganti password (butuh sesi web)
  GET  /api/me/cli-token          tampilkan token worker untuk CLI (butuh sesi web)
  POST /api/me/cli-token/rotate   terbitkan token worker baru, token lama langsung tidak berlaku
"""
import os
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from admin_auth import DUMMY_HASH, hash_password, hash_token, verify_password
from common import db, check_worker_auth

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


def check_volunteer_auth(auth: str | None, web_only: bool = False) -> dict:
    """
    Autentikasi endpoint dashboard relawan. Menerima sesi web (hpc_ws_...) dan, kecuali
    web_only, juga token worker pribadi (hpc_w_...) agar skrip CLI lama tetap jalan.
    Mengembalikan {"type": "individual", "worker": {...}, "via": "web" | "cli"}.
    """
    w = worker_from_session(auth)
    if w:
        return {"type": "individual", "worker": w, "via": "web"}
    if web_only:
        raise HTTPException(401, "Butuh login website (email + password).")
    info = check_worker_auth(auth)
    info["via"] = "cli"
    return info


def _new_session(c, worker_id: str, request: Request, user_agent: str | None) -> tuple[str, datetime]:
    token = SESSION_PREFIX + secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    c.execute("DELETE FROM worker_sessions WHERE expires_at < now()")
    c.execute("""INSERT INTO worker_sessions (token_hash, worker_id, expires_at, ip, user_agent)
                 VALUES (%s, %s, %s, %s, %s)""",
              (hash_token(token), worker_id, expires,
               request.client.host if request.client else None, (user_agent or "")[:200]))
    return token, expires


class LoginBody(BaseModel):
    email: str | None = None
    password: str | None = None
    token: str | None = None   # hanya untuk akun lama yang belum punya password


@router.post("/api/auth/login")
def volunteer_login(body: LoginBody, request: Request, user_agent: str = Header(None)):
    ip = request.client.host if request.client else "?"
    if body.token:
        # Akun yang dibuat lewat './hpc.sh worker-login' belum punya password:
        # masuk sekali dengan token worker, lalu buat password di dashboard.
        info = check_worker_auth(f"Bearer {body.token.strip()}")
        if info["type"] != "individual":
            raise HTTPException(401, "Token bersama (WORKER_TOKEN contoh) tidak punya akun relawan.")
        w = info["worker"]
    else:
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
            raise HTTPException(401, "Email atau password salah. Akun dari './hpc.sh worker-login' "
                                     "yang belum punya password: pilih 'Masuk dengan token worker'.")
        for k in keys:
            _fails.pop(k, None)
        if w["status"] != "active":
            raise HTTPException(403, f"Akun relawan '{w['name']}' ditangguhkan admin ({w['status']}).")
    with db() as c:
        token, expires = _new_session(c, w["id"], request, user_agent)
        has_pw = c.execute("SELECT password_hash IS NOT NULL AS x FROM workers WHERE id = %s",
                           (w["id"],)).fetchone()["x"]
    print(f"[RELAWAN] Login web: {w['name']} (@{w['github_username']}) dari {ip}", flush=True)
    return {"session": token, "expires_at": expires.isoformat(), "worker_name": w["name"],
            "github_username": w["github_username"], "has_password": has_pw}


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
    w = check_volunteer_auth(authorization, web_only=False)["worker"]
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

        if body.email is not None and body.email.strip():
            updates.append("email = %s")
            params.append(body.email.strip()[:100])
        if body.github_username is not None and body.github_username.strip():
            updates.append("github_username = %s")
            params.append(body.github_username.strip().lstrip("@")[:60])
        if updates:
            params.append(w["id"])
            c.execute(f"UPDATE workers SET {', '.join(updates)} WHERE id = %s", tuple(params))
    return {"ok": True, "message": "Profil berhasil diperbarui."}


@router.get("/api/me/cli-token")
def get_cli_token(authorization: str = Header(None)):
    """Token worker untuk file .env repo worker. Hanya lewat sesi web (bukan token itu sendiri)."""
    w = check_volunteer_auth(authorization, web_only=True)["worker"]
    with db() as c:
        r = c.execute("SELECT auth_token FROM workers WHERE id = %s", (w["id"],)).fetchone()
    return {"worker_id": w["id"], "worker_token": r["auth_token"]}


@router.post("/api/me/cli-token/rotate")
def rotate_cli_token(authorization: str = Header(None)):
    """Token baru (mis. token lama bocor / dicabut admin). Worker yang memakai token lama berhenti."""
    w = check_volunteer_auth(authorization, web_only=True)["worker"]
    token = f"hpc_w_{uuid.uuid4().hex}"
    with db() as c:
        c.execute("UPDATE workers SET auth_token = %s WHERE id = %s", (token, w["id"]))
    print(f"[RELAWAN] Token worker baru untuk {w['name']} (@{w['github_username']})", flush=True)
    return {"worker_id": w["id"], "worker_token": token}
