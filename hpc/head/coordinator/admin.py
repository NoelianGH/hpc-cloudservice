"""
API admin: login email + password, sesi admin, dan data dashboard admin.

Semua endpoint di bawah /api/admin/* (kecuali /login) wajib membawa header
  Authorization: Bearer <token sesi admin>
Token sesi didapat dari POST /api/admin/login dan disimpan di tabel
admin_sessions dalam bentuk hash SHA-256 (token asli tidak pernah disimpan).

Variabel lingkungan:
  ADMIN_EMAIL           email admin
  ADMIN_PASSWORD_HASH   hasil "./hpc.sh admin-setup" (PBKDF2-SHA256)
  ADMIN_SESSION_HOURS   umur sesi dalam jam (bawaan 8)
"""
import hmac
import os
import time
from datetime import datetime, timezone, timedelta

import psycopg
from psycopg.rows import dict_row
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from admin_auth import DUMMY_HASH, hash_token, new_session_token, verify_password
from common import client_ip

DB_URL = os.environ["DATABASE_URL"]
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").strip().lower()
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "").strip()
SESSION_HOURS = float(os.environ.get("ADMIN_SESSION_HOURS", "8") or 8)

# Batas percobaan login dalam jendela 15 menit: 5 gagal per email, 20 gagal per IP.
# (Lewat web, semua login datang dari IP server Next.js, jadi batas per IP dibuat longgar.)
MAX_FAILS_EMAIL = 5
MAX_FAILS_IP = 20
LOCK_SECONDS = 15 * 60
_fails: dict[str, list[float]] = {}

router = APIRouter(prefix="/api/admin", tags=["admin"])


def db():
    return psycopg.connect(DB_URL, row_factory=dict_row, autocommit=True)


def admin_configured() -> bool:
    return bool(ADMIN_EMAIL and ADMIN_PASSWORD_HASH)


def init_admin_schema(c) -> None:
    c.execute("""
        CREATE TABLE IF NOT EXISTS admin_sessions (
            token_hash   TEXT PRIMARY KEY,
            email        TEXT NOT NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at   TIMESTAMPTZ NOT NULL,
            last_used_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            ip           TEXT,
            user_agent   TEXT
        );
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_admin_sessions_expires ON admin_sessions (expires_at);")


# =============================================================================
# Sesi admin
# =============================================================================

def _bearer(auth: str | None) -> str | None:
    if auth and auth.startswith("Bearer "):
        return auth[7:].strip() or None
    return None


def get_admin_session(auth: str | None) -> dict | None:
    """Mengembalikan data sesi bila token sesi admin valid, selain itu None."""
    token = _bearer(auth)
    if not token or not token.startswith("hpc_adm_"):
        return None
    with db() as c:
        s = c.execute("""
            UPDATE admin_sessions SET last_used_at = now()
            WHERE token_hash = %s AND expires_at > now()
            RETURNING email, created_at, expires_at""", (hash_token(token),)).fetchone()
    # Sesi hanya sah untuk email admin yang sedang dikonfigurasi
    if not s or not admin_configured() or s["email"] != ADMIN_EMAIL:
        return None
    return s


def require_admin_session(auth: str | None) -> dict:
    s = get_admin_session(auth)
    if not s:
        raise HTTPException(401, "Sesi admin tidak valid atau sudah habis. Silakan login ulang.")
    return s


def _client_ip(request: Request) -> str:
    return client_ip(request)


def _locked(key: str) -> bool:
    now = time.time()
    recent = [t for t in _fails.get(key, []) if now - t < LOCK_SECONDS]
    if recent:
        _fails[key] = recent
    else:
        _fails.pop(key, None)
    limit = MAX_FAILS_EMAIL if key.startswith("email:") else MAX_FAILS_IP
    return len(recent) >= limit


def _record_fail(key: str) -> None:
    if len(_fails) > 10_000:  # cegah memori membengkak
        _fails.clear()
    _fails.setdefault(key, []).append(time.time())


class AdminLogin(BaseModel):
    email: str
    password: str


@router.post("/login")
def admin_login(body: AdminLogin, request: Request, user_agent: str = Header(None)):
    if not admin_configured():
        raise HTTPException(503, "Login admin belum dikonfigurasi. Jalankan './hpc.sh admin-setup' "
                                 "lalu './hpc.sh head-up'.")
    email = body.email.strip().lower()
    ip = _client_ip(request)
    keys = [f"email:{email}", f"ip:{ip}"]
    if any(_locked(k) for k in keys):
        raise HTTPException(429, "Terlalu banyak percobaan login gagal. Coba lagi 15 menit lagi.")

    email_ok = hmac.compare_digest(email.encode(), ADMIN_EMAIL.encode())
    # Selalu hitung PBKDF2 agar waktu respons sama walau email salah
    pw_ok = verify_password(body.password, ADMIN_PASSWORD_HASH if email_ok else DUMMY_HASH)
    if not (email_ok and pw_ok):
        for k in keys:
            _record_fail(k)
        print(f"[ADMIN] Login gagal untuk '{email[:80]}' dari {ip}", flush=True)
        locked = [k for k in keys if _locked(k)]
        if locked:
            import watch
            watch.alert_now(f"login_lock:{ip}:{watch._hour()}", "critical", "suspicious",
                            "Login admin dikunci: terlalu banyak password salah",
                            f"IP {ip}, email dicoba '{email[:80]}'. Dikunci {LOCK_SECONDS // 60} menit "
                            f"({', '.join(k.split(':')[0] for k in locked)}).", {"ip": ip}, repeat=True)
        raise HTTPException(401, "Email atau password admin salah.")

    for k in keys:
        _fails.pop(k, None)
    token = new_session_token()
    expires = datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)
    with db() as c:
        c.execute("DELETE FROM admin_sessions WHERE expires_at < now()")
        c.execute("""INSERT INTO admin_sessions (token_hash, email, expires_at, ip, user_agent)
                     VALUES (%s, %s, %s, %s, %s)""",
                  (hash_token(token), email, expires, ip, (user_agent or "")[:200]))
    print(f"[ADMIN] Login berhasil: {email} dari {ip}", flush=True)
    return {"token": token, "email": email, "expires_at": expires.isoformat()}


@router.post("/logout")
def admin_logout(authorization: str = Header(None)):
    token = _bearer(authorization)
    if token:
        with db() as c:
            c.execute("DELETE FROM admin_sessions WHERE token_hash = %s", (hash_token(token),))
    return {"ok": True}


@router.get("/me")
def admin_me(authorization: str = Header(None)):
    s = require_admin_session(authorization)
    return {"email": s["email"], "expires_at": s["expires_at"]}


# =============================================================================
# Data dashboard (semua wajib sesi admin)
# =============================================================================

@router.get("/overview")
def overview(authorization: str = Header(None)):
    require_admin_session(authorization)
    with db() as c:
        tasks = c.execute("SELECT status, count(*) AS n FROM tasks GROUP BY status").fetchall()
        w = c.execute("""
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE (now() - last_seen) < interval '60 seconds') AS online,
                   count(*) FILTER (WHERE status = 'active') AS active,
                   count(*) FILTER (WHERE status = 'suspended') AS suspended,
                   count(*) FILTER (WHERE github_username IS NOT NULL) AS verified,
                   coalesce(sum(credits), 0) AS credits
            FROM workers""").fetchone()
        a = c.execute("""
            SELECT count(*) FILTER (WHERE status = 'running') AS running,
                   count(*) FILTER (WHERE status = 'expired') AS expired,
                   count(*) FILTER (WHERE status = 'submitted') AS submitted,
                   count(*) FILTER (WHERE status = 'submitted'
                                    AND finished_at > now() - interval '5 minutes') AS submitted_5m,
                   count(*) FILTER (WHERE status = 'expired'
                                    AND lease_until > now() - interval '5 minutes') AS expired_5m
            FROM assignments""").fetchone()
        jobs = c.execute("SELECT count(*) AS n FROM jobs").fetchone()
        # Tugas tervalidasi per menit (10 menit terakhir), dipakai untuk grafik throughput
        series = c.execute("""
            WITH done AS (
                SELECT t.id, max(a.finished_at) AS at
                FROM tasks t JOIN assignments a ON a.task_id = t.id AND a.status = 'submitted'
                WHERE t.status = 'done'
                GROUP BY t.id)
            SELECT m.minute, count(done.id) AS n
            FROM generate_series(date_trunc('minute', now()) - interval '9 minutes',
                                 date_trunc('minute', now()), interval '1 minute') AS m(minute)
            LEFT JOIN done ON date_trunc('minute', done.at) = m.minute
            GROUP BY m.minute ORDER BY m.minute""").fetchall()
        regs = c.execute("""
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE verified) AS verified,
                   count(*) FILTER (WHERE created_at > now() - interval '24 hours') AS last_24h
            FROM worker_auth_sessions""").fetchone()
        alerts = c.execute("""
            SELECT count(*) FILTER (WHERE acked_at IS NULL) AS open,
                   count(*) FILTER (WHERE acked_at IS NULL AND level = 'critical') AS critical
            FROM alerts""").fetchone()
        backup = c.execute("""SELECT max(at) FILTER (WHERE ok) AS last_ok,
                                     bool_or(NOT ok) FILTER (WHERE at > now() - interval '2 hours') AS recent_fail
                              FROM backups""").fetchone()
    task_counts = {r["status"]: r["n"] for r in tasks}
    return {
        "tasks": {
            "pending": task_counts.get("pending", 0),
            "done": task_counts.get("done", 0),
            "invalid": task_counts.get("invalid", 0),
            "total": sum(task_counts.values()),
        },
        "workers": w,
        "assignments": a,
        "jobs": jobs["n"],
        "registrations": regs,
        "alerts": alerts,
        "backup": backup,
        "throughput_per_min": [{"minute": r["minute"], "n": r["n"]} for r in series],
    }


@router.get("/workers")
def list_workers(authorization: str = Header(None)):
    require_admin_session(authorization)
    with db() as c:
        rows = c.execute("""
            SELECT w.id, w.name, w.github_username, w.email, w.status, w.credits,
                   w.last_seen, w.created_at,
                   (w.auth_token IS NOT NULL) AS has_token,
                   (now() - w.last_seen) < interval '60 seconds' AS online,
                   count(a.id) FILTER (WHERE a.status = 'running') AS running,
                   count(a.id) FILTER (WHERE a.status = 'submitted') AS submitted,
                   count(a.id) FILTER (WHERE a.status = 'expired') AS expired
            FROM workers w LEFT JOIN assignments a ON a.worker_id = w.id
            GROUP BY w.id
            ORDER BY online DESC, w.credits DESC, w.created_at DESC""").fetchall()
        # Hasil yang ditolak: worker mengirim hasil ke tugas yang sudah final tapi hasilnya beda
        rejected = c.execute("""
            SELECT a.worker_id, count(*) AS n
            FROM assignments a JOIN tasks t ON t.id = a.task_id
            WHERE a.status = 'submitted' AND t.status IN ('done', 'invalid')
              AND (t.result IS NULL OR a.result IS DISTINCT FROM t.result)
            GROUP BY a.worker_id""").fetchall()
    rej = {r["worker_id"]: r["n"] for r in rejected}
    for r in rows:
        r["rejected"] = rej.get(r["id"], 0)
    return {"workers": rows}


@router.post("/workers/{worker_id}/revoke-token")
def revoke_worker_token(worker_id: str, authorization: str = Header(None)):
    """Cabut token individual worker: relawan membuat token baru di dashboard (login website tetap bisa)."""
    s = require_admin_session(authorization)
    with db() as c:
        r = c.execute("UPDATE workers SET auth_token = NULL WHERE id = %s RETURNING id, name",
                      (worker_id,)).fetchone()
    if not r:
        raise HTTPException(404, f"Worker '{worker_id}' tidak ditemukan.")
    print(f"[ADMIN] {s['email']} mencabut token worker {r['name']} ({worker_id})", flush=True)
    return {"ok": True, "worker_id": worker_id, "message": "Token worker dicabut."}


@router.get("/jobs")
def list_jobs(authorization: str = Header(None)):
    require_admin_session(authorization)
    with db() as c:
        jobs = c.execute("""
            SELECT j.id, j.kind, j.created_at, j.status, j.n_stages, j.current_stage, j.code, j.resources,
                   j.result_branch, j.result_commit, j.publish_status, j.finished_at,
                   (j.result->>'pi')::float AS result_pi, (j.result->>'mean')::float AS mean_temp,
                   (j.result->>'serial_match')::boolean AS serial_match,
                   count(t.id) AS total,
                   count(t.id) FILTER (WHERE t.status = 'done') AS done,
                   count(t.id) FILTER (WHERE t.status = 'invalid') AS invalid,
                   count(t.id) FILTER (WHERE t.status = 'pending') AS pending,
                   sum((t.result->>'inside')::bigint) FILTER (WHERE t.status = 'done' AND j.kind = 'montecarlo_pi') AS inside,
                   sum((t.payload->>'samples')::bigint) FILTER (WHERE t.status = 'done' AND j.kind = 'montecarlo_pi') AS samples,
                   EXTRACT(EPOCH FROM (coalesce(j.finished_at, (SELECT max(a.finished_at) FROM assignments a
                       JOIN tasks t2 ON t2.id = a.task_id WHERE t2.job_id = j.id)) - j.created_at)) AS seconds
            FROM jobs j LEFT JOIN tasks t ON t.job_id = j.id
            GROUP BY j.id ORDER BY j.id DESC LIMIT 50""").fetchall()
    for j in jobs:
        j["pi"] = 4 * j["inside"] / j["samples"] if j["kind"] == "montecarlo_pi" and j["samples"] else j.pop("result_pi", None)
        j.pop("result_pi", None)
        j.pop("inside", None)
        j.pop("samples", None)
    return {"jobs": jobs}


def _compact(obj):
    """Ringkas data besar (mis. baris grid heat2d) agar detail tugas tetap ringan di dashboard."""
    if isinstance(obj, dict) and isinstance(obj.get("rows"), list) and obj["rows"]:
        rows = obj["rows"]
        out = {k: v for k, v in obj.items() if k != "rows"}
        out["rows"] = f"[{len(rows)} baris x {len(rows[0]) if isinstance(rows[0], list) else '?'} kolom]"
        return out
    return obj


@router.get("/tasks")
def list_tasks(authorization: str = Header(None), status: str | None = None,
               job_id: int | None = None, limit: int = 100):
    require_admin_session(authorization)
    limit = max(1, min(limit, 500))
    where, params = [], []
    if status:
        where.append("t.status = %s")
        params.append(status)
    if job_id is not None:
        where.append("t.job_id = %s")
        params.append(job_id)
    sql = f"""
        SELECT t.id, t.job_id, t.kind, t.status, t.replicas, t.stage, t.block,
               count(a.id) FILTER (WHERE a.status = 'running') AS running,
               count(a.id) FILTER (WHERE a.status = 'submitted') AS submitted,
               count(a.id) FILTER (WHERE a.status = 'expired') AS expired,
               max(a.finished_at) AS last_result_at
        FROM tasks t LEFT JOIN assignments a ON a.task_id = t.id
        {"WHERE " + " AND ".join(where) if where else ""}
        GROUP BY t.id ORDER BY t.id DESC LIMIT %s"""
    with db() as c:
        rows = c.execute(sql, (*params, limit)).fetchall()
    return {"tasks": rows}


@router.get("/tasks/{task_id}")
def task_detail(task_id: int, authorization: str = Header(None)):
    """Detail validasi satu tugas: semua replika, hasilnya, dan apakah sepakat dengan hasil final."""
    require_admin_session(authorization)
    with db() as c:
        t = c.execute("SELECT id, job_id, kind, status, replicas, stage, block, credit, payload, result, "
                      "result_hash FROM tasks WHERE id = %s",
                      (task_id,)).fetchone()
        if not t:
            raise HTTPException(404, "Tugas tidak ditemukan.")
        reps = c.execute("""
            SELECT a.id, a.worker_id, w.name AS worker_name, w.github_username, a.status,
                   a.result, a.result_hash, a.started_at, a.finished_at, a.lease_until
            FROM assignments a JOIN workers w ON w.id = a.worker_id
            WHERE a.task_id = %s ORDER BY a.id""", (task_id,)).fetchall()
    for r in reps:
        r["agrees"] = (r["result_hash"] == t["result_hash"]) if (t["result_hash"] and r["status"] == "submitted") else None
        r["result"] = _compact(r["result"])
    t["payload"], t["result"] = _compact(t["payload"]), _compact(t["result"])
    return {"task": t, "assignments": reps}


@router.get("/activity")
def activity(authorization: str = Header(None), limit: int = 40):
    require_admin_session(authorization)
    limit = max(1, min(limit, 200))
    with db() as c:
        rows = c.execute("""
            SELECT a.id, a.task_id, t.job_id, t.kind, a.status, a.worker_id, w.name AS worker_name,
                   a.started_at, a.finished_at,
                   EXTRACT(EPOCH FROM (a.finished_at - a.started_at)) AS seconds
            FROM assignments a JOIN tasks t ON t.id = a.task_id JOIN workers w ON w.id = a.worker_id
            ORDER BY coalesce(a.finished_at, a.started_at) DESC LIMIT %s""", (limit,)).fetchall()
    return {"activity": rows}


@router.get("/registrations")
def registrations(authorization: str = Header(None), limit: int = 50):
    """Riwayat pendaftaran relawan (GitHub + OTP). Kode OTP tidak pernah dikirim ke dashboard."""
    require_admin_session(authorization)
    limit = max(1, min(limit, 200))
    with db() as c:
        rows = c.execute("""
            SELECT session_id, worker_name, github_username, email, verified, attempts,
                   otp_expires_at < now() AS expired, github_metrics, created_at
            FROM worker_auth_sessions ORDER BY created_at DESC LIMIT %s""", (limit,)).fetchall()
    for r in rows:
        r["session_id"] = r["session_id"][:8]  # cukup untuk identifikasi, tidak bisa dipakai verifikasi
    return {"registrations": rows}
