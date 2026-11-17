import hmac
import re
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from psycopg.types.json import Jsonb
from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from github_verifier import check_github_worker
from email_service import generate_otp, send_otp_email
from admin import router as admin_router, get_admin_session
from common import db, check_worker_auth, check_worker_owner
from schema import migrate
from jobs import JobError, canonical_hash, create_job, heatmap_png
from volunteer import router as volunteer_router
from volunteer_auth import router as volunteer_auth_router, check_password_rule
from admin_auth import hash_password
from project import router as project_router
from watch import router as watch_router

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")  # token lama untuk CLI (./hpc.sh job)
LEASE_SECONDS = 30
OTP_EXPIRY_MINUTES = 10
MAX_RESULT_BYTES = 2_000_000  # batas ukuran hasil satu tugas

def init_db_schema():
    """
    Inisialisasi atau migrasi skema database secara otomatis dan aman (idempotent).
    Daftar perubahan skema ada di schema.py (dipakai juga oleh validator).
    """
    try:
        with db() as c:
            migrate(c)
            print("[DB] Skema database berhasil diinisialisasi / dimigrasi.", flush=True)
    except Exception as e:
        print(f"[DB WARN] Inisialisasi skema tertunda (db mungkin belum siap): {e}", flush=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db_schema()
    yield

app = FastAPI(title="HPC Coordinator", lifespan=lifespan)
app.include_router(admin_router)
app.include_router(volunteer_router)
app.include_router(volunteer_auth_router)
app.include_router(project_router)
app.include_router(watch_router)

def check_admin(auth: str | None):
    """
    Akses admin sah bila:
    1. Token sesi dari login dashboard admin (email + password), atau
    2. ADMIN_TOKEN dari .env (dipakai CLI seperti './hpc.sh job').
    """
    if ADMIN_TOKEN and auth and hmac.compare_digest(auth.encode(), f"Bearer {ADMIN_TOKEN}".encode()):
        return
    if get_admin_session(auth):
        return
    raise HTTPException(401, "Akses admin ditolak. Login ke dashboard admin atau pakai ADMIN_TOKEN.")

# =============================================================================
# MODEL REQUEST & ENDPOINTS AUTENTIKASI CLI WORKER
# =============================================================================

class AuthRegisterRequest(BaseModel):
    worker_name: str
    github_username: str
    email: str
    # Password login WEBSITE (wajib dari halaman Register; boleh kosong dari CLI lama,
    # lalu dibuat belakangan di dashboard). Disimpan sebagai hash PBKDF2, tidak pernah teks asli.
    password: str | None = None
    # PREFERRED USERNAME dari halaman Register (nama tampilan di navbar). Kosong = pakai username GitHub.
    username: str | None = None

class AuthVerifyRequest(BaseModel):
    session_id: str
    otp: str

@app.post("/api/auth/register-request")
def auth_register_request(body: AuthRegisterRequest):
    """
    Langkah 1 Autentikasi CLI:
    Worker mengirimkan worker_name, github_username, dan email.
    Koordinator akan:
    1. Mengecek akun GitHub menggunakan github_verifier (anti-fake worker).
    2. Jika lolos, membuat token OTP 6-digit dan menyimpannya di DB (berlaku 10 menit).
    3. Mengirimkan OTP ke email user.
    """
    worker_name = body.worker_name.strip()[:50]
    github_user = body.github_username.strip()
    email = body.email.strip()

    if not worker_name or not github_user or not email:
        raise HTTPException(400, "worker_name, github_username, dan email wajib diisi.")
    if "@" not in email or "." not in email:
        raise HTTPException(400, "Format alamat email tidak valid.")
    username = re.sub(r"[^A-Za-z0-9_.-]", "", (body.username or "").strip())[:30] or None
    password_hash = None
    if body.password:
        check_password_rule(body.password)
        password_hash = hash_password(body.password)
    # Satu email = satu akun relawan (email dipakai untuk login website)
    with db() as c:
        taken = c.execute("""SELECT 1 FROM workers WHERE lower(email) = lower(%s)
                               AND lower(coalesce(github_username, '')) <> lower(%s) LIMIT 1""",
                          (email, github_user)).fetchone()
    if taken:
        raise HTTPException(400, "Email ini sudah dipakai akun relawan lain. Gunakan email lain atau login.")

    # 1. Pengecekan Reputasi GitHub (Anti-Fake Worker)
    gh_check = check_github_worker(github_user)
    if not gh_check["passed"]:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Verifikasi GitHub gagal. Akun '@{github_user}' tidak memenuhi syarat anti-fake worker.",
                "reasons": gh_check["reasons"],
                "factors": gh_check["factors"],
                "score": gh_check["score"],
            }
        )

    # 2. Pembuatan OTP dan Sesi Autentikasi
    otp = generate_otp(6)
    session_id = uuid.uuid4().hex
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)

    for attempt in range(2):
        try:
            with db() as c:
                c.execute("""
                    INSERT INTO worker_auth_sessions 
                        (session_id, worker_name, github_username, email, otp, otp_expires_at, github_metrics,
                         password_hash, username)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    session_id,
                    worker_name,
                    github_user,
                    email,
                    otp,
                    expires_at,
                    Jsonb(gh_check["factors"]),
                    password_hash,
                    username,
                ))
            break
        except Exception as e:
            if attempt == 0:
                print(f"[DB AUTO-MIGRATE] Tabel belum siap, menjalankan migrasi skema: {e}", flush=True)
                init_db_schema()
            else:
                print(f"[DB ERROR] Gagal menyimpan sesi: {e}", flush=True)
                raise HTTPException(500, f"Gagal menyimpan sesi verifikasi ke database: {str(e)}")

    # 3. Pengiriman Email OTP
    mail_result = send_otp_email(
        to_email=email,
        otp=otp,
        worker_name=worker_name,
        github_username=github_user
    )

    response_data = {
        "status": "pending_otp",
        "session_id": session_id,
        "worker_name": worker_name,
        "github_username": github_user,
        "email": email,
        "github_score": gh_check["score"],
        "factors": gh_check["factors"],
        "message": f"Akun GitHub lolos verifikasi. Kode OTP telah dikirimkan ke {email}.",
    }

    # Jika sedang dalam dev mode / simulasi email, sertakan info dev_otp agar mudah diuji
    if mail_result.get("dev_mode") and "dev_otp" in mail_result:
        response_data["dev_mode"] = True
        response_data["dev_otp"] = mail_result["dev_otp"]

    return response_data

@app.post("/api/auth/verify-otp")
def auth_verify_otp(body: AuthVerifyRequest):
    """
    Langkah 2 Autentikasi CLI:
    Worker menginputkan kode OTP yang diterima melalui email.
    Jika cocok dan belum kadaluarsa, koordinator menerbitkan worker_token permanen.
    Worker kemudian resmi terdaftar dan siap diassign ke jobdesk.
    """
    session_id = body.session_id.strip()
    otp_input = body.otp.strip()

    with db() as c:
        session = c.execute("""
            SELECT * FROM worker_auth_sessions WHERE session_id = %s
        """, (session_id,)).fetchone()

        if not session:
            raise HTTPException(404, "Sesi autentikasi tidak ditemukan")

        if session["verified"]:
            raise HTTPException(400, "Sesi autentikasi ini sudah pernah diverifikasi sebelumnya")

        if session["attempts"] >= 5:
            raise HTTPException(400, "Batas percobaan OTP terlampaui (maksimal 5 kali). Silakan request ulang.")

        now_utc = datetime.now(timezone.utc)
        if now_utc > session["otp_expires_at"]:
            raise HTTPException(400, "Kode OTP sudah kadaluarsa (melewati 10 menit). Silakan minta kode baru.")

        # Cocokkan OTP
        if session["otp"] != otp_input:
            c.execute("""
                UPDATE worker_auth_sessions SET attempts = attempts + 1 WHERE session_id = %s
            """, (session_id,))
            remaining = 5 - (session["attempts"] + 1)
            raise HTTPException(400, f"Kode OTP salah. Sisa percobaan: {max(0, remaining)}")

        # OTP Benar: Terbitkan token worker dan daftarkan ke database
        c.execute("""
            UPDATE worker_auth_sessions SET verified = TRUE WHERE session_id = %s
        """, (session_id,))

        # Periksa apakah worker dengan github_username yang sama sudah pernah ada
        existing_worker = c.execute("""
            SELECT id FROM workers WHERE github_username = %s LIMIT 1
        """, (session["github_username"],)).fetchone()

        worker_token = f"hpc_w_{uuid.uuid4().hex}"

        if existing_worker:
            wid = existing_worker["id"]
            # Password lama dipertahankan bila daftar ulang lewat CLI (tanpa password)
            c.execute("""
                UPDATE workers 
                SET name = %s, email = %s, auth_token = %s, status = 'active', last_seen = now(),
                    password_hash = coalesce(%s, password_hash), username = coalesce(%s, username)
                WHERE id = %s
            """, (session["worker_name"], session["email"], worker_token, session.get("password_hash"),
                  session.get("username"), wid))
        else:
            wid = f"w-{uuid.uuid4().hex[:8]}"
            c.execute("""
                INSERT INTO workers (id, name, github_username, email, auth_token, status, password_hash, username)
                VALUES (%s, %s, %s, %s, %s, 'active', %s, %s)
            """, (wid, session["worker_name"], session["github_username"], session["email"], worker_token,
                  session.get("password_hash"), session.get("username")))

    return {
        "status": "authenticated",
        "worker_id": wid,
        "worker_name": session["worker_name"],
        "github_username": session["github_username"],
        "worker_token": worker_token,
        "message": "Autentikasi berhasil! Worker kini terverifikasi dan siap diassign ke jobdesk.",
    }

# =============================================================================
# ENDPOINTS WORKER & JOBS (OPERASIONAL)
# =============================================================================

class Capacity(BaseModel):
    cpus: float = 1
    memory_mb: int = 512

class Register(BaseModel):
    name: str
    capacity: Capacity | None = None

class Claim(BaseModel):
    worker_id: str
    capacity: Capacity | None = None

class Beat(BaseModel):
    worker_id: str
    assignment_id: int

class Submit(BaseModel):
    worker_id: str
    assignment_id: int
    result: dict
    log: str | None = None   # potongan output (build/test); disimpan tapi TIDAK ikut di-hash

class NewJob(BaseModel):
    kind: str = "montecarlo_pi"   # montecarlo_pi | mandelbrot | heat2d | repo
    n_tasks: int | None = None    # heat2d: jumlah blok baris
    size: int | None = None       # sampel per tugas (montecarlo) / lebar gambar (mandelbrot)
    replicas: int = 2
    params: dict | None = None    # heat2d: n, blocks, stages, steps, alpha, ... ; repo: parameter bebas
    task_kind: str | None = None  # repo: diteruskan ke program di repo job
    code: dict | None = None      # {repo_url, sha (40 hex), entry} -> kode dari repo job
    resources: dict | None = None # {cpus, memory_mb, timeout_s} per tugas
    credit_per_task: int | None = None

def _save_capacity(c, wid: str, cap: Capacity | None):
    if cap:
        c.execute("UPDATE workers SET cpus = %s, memory_mb = %s WHERE id = %s",
                  (max(0.1, min(cap.cpus, 64)), max(64, min(cap.memory_mb, 1 << 20)), wid))

@app.post("/api/register")
def register(body: Register, authorization: str = Header(None)):
    auth_info = check_worker_auth(authorization)
    
    # Jika worker menggunakan token individual dari hasil autentikasi CLI
    if auth_info["type"] == "individual":
        wid = auth_info["worker"]["id"]
        with db() as c:
            c.execute("UPDATE workers SET name = %s, last_seen = now() WHERE id = %s", (body.name[:50], wid))
            _save_capacity(c, wid, body.capacity)
        return {"worker_id": wid, "lease_seconds": LEASE_SECONDS}

    # Jika worker menggunakan WORKER_TOKEN global
    wid = uuid.uuid4().hex[:12]
    with db() as c:
        c.execute("INSERT INTO workers (id, name) VALUES (%s, %s)", (wid, body.name[:50]))
        _save_capacity(c, wid, body.capacity)
    return {"worker_id": wid, "lease_seconds": LEASE_SECONDS}

@app.post("/api/tasks/claim")
def claim(body: Claim, authorization: str = Header(None)):
    """
    Pull model + FIFO: worker meminta satu tugas dan mendapat tugas tertua di antrean
    (urut id). Tugas tahap berikutnya pada job multi-tahap baru masuk antrean setelah
    tahap sebelumnya selesai, jadi ikut antre di belakang. Hanya tugas yang spesifikasi resource job-nya
    muat di sandbox worker (cpus, memory_mb) yang diberikan. Worker tidak pernah mendapat
    dua replika dari tugas yang sama (syarat validasi replikasi).
    """
    auth_info = check_worker_auth(authorization)
    with db() as c:
        check_worker_owner(auth_info, body.worker_id, c)
        c.execute("UPDATE workers SET last_seen = now() WHERE id = %s", (body.worker_id,))
        _save_capacity(c, body.worker_id, body.capacity)
        cap = c.execute("SELECT coalesce(cpus, 1) AS cpus, coalesce(memory_mb, 512) AS memory_mb "
                        "FROM workers WHERE id = %s", (body.worker_id,)).fetchone()
        with c.transaction():
            t = c.execute("""
                SELECT t.id, t.kind, t.payload, t.stage, t.job_id, j.code, j.resources, j.n_stages
                FROM tasks t JOIN jobs j ON j.id = t.job_id
                WHERE t.status = 'pending' AND j.status = 'running'
                  AND coalesce((j.resources->>'cpus')::real, 1) <= %s
                  AND coalesce((j.resources->>'memory_mb')::int, 256) <= %s
                  AND (SELECT count(*) FROM assignments a
                       WHERE a.task_id = t.id AND a.status IN ('running','submitted')) < t.replicas
                  AND NOT EXISTS (SELECT 1 FROM assignments a
                       WHERE a.task_id = t.id AND a.worker_id = %s)
                ORDER BY t.id   -- FIFO: tugas yang lebih dulu masuk antrean diambil lebih dulu
                LIMIT 1
                FOR UPDATE OF t SKIP LOCKED""", (cap["cpus"], cap["memory_mb"], body.worker_id)).fetchone()
            if not t:
                return Response(status_code=204)
            a = c.execute("""
                INSERT INTO assignments (task_id, worker_id, lease_until)
                VALUES (%s, %s, now() + make_interval(secs => %s)) RETURNING id""",
                (t["id"], body.worker_id, LEASE_SECONDS)).fetchone()
    return {"assignment_id": a["id"], "task_id": t["id"], "job_id": t["job_id"], "kind": t["kind"],
            "stage": t["stage"], "n_stages": t["n_stages"], "payload": t["payload"],
            "code": t["code"], "resources": t["resources"]}

@app.post("/api/heartbeat")
def heartbeat(body: Beat, authorization: str = Header(None)):
    """Perpanjang lease. Ditolak bila tugas sudah melewati batas waktu (resources.timeout_s) job."""
    auth_info = check_worker_auth(authorization)
    with db() as c:
        check_worker_owner(auth_info, body.worker_id, c)
        c.execute("UPDATE workers SET last_seen = now() WHERE id = %s", (body.worker_id,))
        r = c.execute("""
            UPDATE assignments a SET lease_until = now() + make_interval(secs => %s)
            FROM tasks t JOIN jobs j ON j.id = t.job_id
            WHERE a.id = %s AND a.worker_id = %s AND a.status = 'running' AND t.id = a.task_id
              AND now() < a.started_at + make_interval(secs => coalesce((j.resources->>'timeout_s')::int, 120))
            RETURNING a.id""",
            (LEASE_SECONDS, body.assignment_id, body.worker_id)).fetchone()
    if not r:
        raise HTTPException(410, "lease sudah habis atau batas waktu tugas terlampaui")
    return {"ok": True}

@app.post("/api/tasks/submit")
def submit(body: Submit, authorization: str = Header(None)):
    auth_info = check_worker_auth(authorization)
    result_hash = canonical_hash(body.result)  # dihitung koordinator, bukan dipercaya dari worker
    if len(str(body.result)) > MAX_RESULT_BYTES:
        raise HTTPException(413, "Hasil tugas terlalu besar")
    with db() as c:
        check_worker_owner(auth_info, body.worker_id, c)
        r = c.execute("""
            UPDATE assignments a SET status = 'submitted', result = %s, result_hash = %s, finished_at = now(),
                   log = %s
            FROM tasks t JOIN jobs j ON j.id = t.job_id
            WHERE a.id = %s AND a.worker_id = %s AND a.status = 'running' AND t.id = a.task_id
              AND now() < a.started_at + make_interval(secs => coalesce((j.resources->>'timeout_s')::int, 120) + 5)
            RETURNING a.id""",
            (Jsonb(body.result), result_hash, (body.log or None) and body.log[-8000:],
             body.assignment_id, body.worker_id)).fetchone()
    if not r:
        raise HTTPException(410, "lease habis atau batas waktu tugas (resources.timeout_s) terlampaui, hasil ditolak")
    return {"ok": True, "result_hash": result_hash}

class Fail(BaseModel):
    worker_id: str
    assignment_id: int
    error: str = ""

@app.post("/api/tasks/fail")
def fail(body: Fail, authorization: str = Header(None)):
    """
    Worker melapor tugas gagal dijalankan (mis. program di repo job error / timeout).
    Tugas langsung kembali ke antrean; setelah MAX_TASK_FAILURES kegagalan oleh worker
    berbeda, validator menandai tugas invalid agar job rusak tidak berputar selamanya.
    """
    auth_info = check_worker_auth(authorization)
    with db() as c:
        check_worker_owner(auth_info, body.worker_id, c)
        r = c.execute("""
            UPDATE assignments SET status = 'failed', finished_at = now(), result = %s
            WHERE id = %s AND worker_id = %s AND status = 'running' RETURNING id""",
            (Jsonb({"error": body.error[:1000]}), body.assignment_id, body.worker_id)).fetchone()
    if not r:
        raise HTTPException(410, "assignment tidak aktif")
    return {"ok": True}

class AuthResendBody(BaseModel):
    session_id: str


@app.post("/api/auth/resend-otp")
def auth_resend_otp(body: AuthResendBody):
    """
    Langkah 1b Autentikasi CLI (opsional):
    Meminta ulang kode OTP baru untuk sesi yang sudah ada.
    Berguna jika OTP pertama kadaluarsa atau tidak diterima.
    Sesi harus belum verified dan session_id harus valid.
    """
    session_id = body.session_id.strip()

    with db() as c:
        session = c.execute(
            "SELECT * FROM worker_auth_sessions WHERE session_id = %s", (session_id,)
        ).fetchone()

        if not session:
            raise HTTPException(404, "Sesi autentikasi tidak ditemukan.")
        if session["verified"]:
            raise HTTPException(400, "Sesi ini sudah terverifikasi, tidak bisa resend.")

        # Generate OTP baru dan reset hitungan percobaan
        new_otp     = generate_otp(6)
        new_expires = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)

        c.execute("""
            UPDATE worker_auth_sessions
               SET otp = %s, otp_expires_at = %s, attempts = 0
             WHERE session_id = %s
        """, (new_otp, new_expires, session_id))

    mail_result = send_otp_email(
        to_email=session["email"],
        otp=new_otp,
        worker_name=session["worker_name"],
        github_username=session["github_username"],
    )

    response = {
        "status":     "otp_resent",
        "session_id": session_id,
        "message":    f"Kode OTP baru telah dikirimkan ke {session['email']}.",
    }
    if mail_result.get("dev_mode") and "dev_otp" in mail_result:
        response["dev_mode"] = True
        response["dev_otp"]  = mail_result["dev_otp"]
    return response


@app.get("/api/auth/me")
def auth_me(authorization: str = Header(None)):
    """
    Endpoint untuk worker mengecek status token-nya sendiri.
    Digunakan oleh CLI command './hpc.sh worker-status' maupun worker.py saat startup.
    Mengembalikan identitas worker jika token valid.
    """
    auth_info = check_worker_auth(authorization)

    if auth_info["type"] == "global":
        # Token global tidak memiliki profil individual
        return {
            "type":     "global_token",
            "verified": False,
            "message":  "Menggunakan token global. Jalankan './hpc.sh worker-login' untuk autentikasi individual.",
        }

    w = auth_info["worker"]
    return {
        "type":             "individual",
        "verified":         True,
        "worker_id":        w["id"],
        "worker_name":      w["name"],
        "github_username":  w["github_username"],
        "email":            w["email"],
        "status":           w["status"],
    }


class WorkerSuspendBody(BaseModel):
    status: str   # 'active' | 'suspended'
    reason: str = ""


@app.post("/api/workers/{worker_id}/status")
@app.post("/api/admin/workers/{worker_id}/status")
def set_worker_status(worker_id: str, body: WorkerSuspendBody, authorization: str = Header(None)):
    """
    Endpoint admin: mengubah status worker (active / suspended).
    Berguna untuk menonaktifkan worker yang terbukti curang atau bermasalah.
    Status 'suspended' menyebabkan worker ditolak saat mencoba claim tugas.
    """
    check_admin(authorization)

    if body.status not in ("active", "suspended"):
        raise HTTPException(400, "Status harus 'active' atau 'suspended'.")

    with db() as c:
        r = c.execute(
            "UPDATE workers SET status = %s WHERE id = %s RETURNING id, name, github_username",
            (body.status, worker_id),
        ).fetchone()

    if not r:
        raise HTTPException(404, f"Worker '{worker_id}' tidak ditemukan.")

    action = "diaktifkan" if body.status == "active" else "ditangguhkan"
    print(
        f"[ADMIN] Worker {r['name']} (@{r['github_username']}) {action}."
        + (f" Alasan: {body.reason}" if body.reason else ""),
        flush=True,
    )
    return {
        "ok":               True,
        "worker_id":        worker_id,
        "worker_name":      r["name"],
        "github_username":  r["github_username"],
        "new_status":       body.status,
        "message":          f"Worker berhasil {action}.",
    }


@app.post("/api/jobs")
@app.post("/api/admin/jobs")
def new_job(body: NewJob, authorization: str = Header(None)):
    check_admin(authorization)
    try:
        with db() as c, c.transaction():
            return create_job(c, body.model_dump(exclude_none=True))
    except JobError as e:
        raise HTTPException(400, str(e))


def _job_public(j: dict) -> dict:
    res = dict(j.get("result") or {})
    res.pop("grid", None)
    res.pop("results", None)
    j["result"] = res or None
    return j


@app.get("/api/jobs")
def public_jobs(limit: int = 20):
    """Daftar job (publik): progres per tahap, resource, kode (repo + SHA), dan branch hasil."""
    limit = max(1, min(limit, 100))
    with db() as c:
        rows = c.execute("""
            SELECT j.id, j.kind, j.status, j.n_stages, j.current_stage, j.code, j.resources,
                   j.result, j.result_branch, j.result_commit, j.publish_status, j.created_at, j.finished_at,
                   count(t.id) AS total, count(t.id) FILTER (WHERE t.status = 'done') AS done,
                   EXTRACT(EPOCH FROM (coalesce(j.finished_at, now()) - j.created_at)) AS seconds
            FROM jobs j LEFT JOIN tasks t ON t.job_id = j.id
            GROUP BY j.id ORDER BY j.id DESC LIMIT %s""", (limit,)).fetchall()
    return {"jobs": [_job_public(r) for r in rows]}


@app.get("/api/jobs/{job_id}/result")
def job_result(job_id: int, full: bool = False):
    """Hasil akhir job. full=true menyertakan grid lengkap (heat2d) / semua hasil tugas (repo)."""
    with db() as c:
        j = c.execute("""SELECT id, kind, status, spec, n_stages, current_stage, code, resources, result,
                                result_branch, result_commit, publish_status, created_at, finished_at
                         FROM jobs WHERE id = %s""", (job_id,)).fetchone()
    if not j:
        raise HTTPException(404, "Job tidak ditemukan")
    return j if full else _job_public(j)


@app.get("/api/jobs/{job_id}/heatmap.png")
def job_heatmap(job_id: int):
    with db() as c:
        j = c.execute("SELECT kind, result FROM jobs WHERE id = %s", (job_id,)).fetchone()
    if not j or j["kind"] != "heat2d" or not (j["result"] or {}).get("grid"):
        raise HTTPException(404, "Heatmap hanya ada untuk job heat2d yang sudah selesai")
    return Response(heatmap_png(j["result"]["grid"]), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=300"})

@app.get("/api/stats")
def stats():
    """
    Statistik PUBLIK (tanpa login). Sengaja tidak memuat email maupun worker_id
    relawan; data lengkap hanya ada di /api/admin/* (wajib login admin).
    """
    with db() as c:
        tasks = c.execute("SELECT status, count(*) AS n FROM tasks GROUP BY status").fetchall()
        workers = c.execute("""
            SELECT name, github_username, status, credits,
                   (now() - last_seen) < interval '60 seconds' AS online,
                   (SELECT count(*) FROM assignments a WHERE a.worker_id = w.id AND a.status = 'running') AS running
            FROM workers w ORDER BY credits DESC""").fetchall()
        jobs = c.execute("""
            SELECT j.id, j.kind, j.status, j.n_stages, j.current_stage,
                   count(*) AS total,
                   count(*) FILTER (WHERE t.status = 'done') AS done,
                   sum((t.result->>'inside')::bigint) FILTER (WHERE t.status = 'done' AND j.kind = 'montecarlo_pi') AS inside,
                   sum((t.payload->>'samples')::bigint) FILTER (WHERE t.status = 'done' AND j.kind = 'montecarlo_pi') AS samples,
                   (j.result->>'mean')::float AS mean_temp,
                   EXTRACT(EPOCH FROM (coalesce(j.finished_at, (SELECT max(a.finished_at) FROM assignments a
                       JOIN tasks t2 ON t2.id = a.task_id WHERE t2.job_id = j.id)) - j.created_at)) AS seconds
            FROM jobs j JOIN tasks t ON t.job_id = j.id
            GROUP BY j.id ORDER BY j.id DESC LIMIT 10""").fetchall()
    for j in jobs:
        if j["kind"] == "montecarlo_pi" and j["samples"]:
            j["pi"] = 4 * j["inside"] / j["samples"]
        j.pop("inside", None)
    return {"tasks": {r["status"]: r["n"] for r in tasks}, "workers": workers, "jobs": jobs}

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return DASHBOARD

DASHBOARD = """<!doctype html><html><head><meta charset="utf-8"><title>HPC Dashboard</title>
<style>body{font-family:sans-serif;margin:2em}table{border-collapse:collapse;margin-bottom:1.5em}
td,th{border:1px solid #ccc;padding:4px 10px}
.verified{color:green;font-weight:bold}
.unverified{color:#888}
</style></head><body>
<h1>HPC Dashboard</h1>
<p>Portal relawan (daftar, leaderboard, sertifikat) ada di web Next.js (<code>./hpc.sh web-dev</code>, port 3000).
API: <a href="/api/leaderboard">/api/leaderboard</a> &middot; <a href="/api/jobs">/api/jobs</a></p>
<div id="d">memuat...</div>
<script>
const e = x => String(x ?? '').replace(/[&<>"']/g, c => '&#' + c.charCodeAt(0) + ';');
async function load(){
  const s = await (await fetch('/api/stats')).json();
  const lb = await (await fetch('/api/leaderboard?limit=10')).json();
  let h = '<h3>Tugas</h3><pre>' + e(JSON.stringify(s.tasks)) + '</pre>';
  h += '<h3>Leaderboard relawan</h3><table><tr><th>#</th><th>Nama</th><th>GitHub</th><th>Lencana</th><th>Kredit</th><th>Tervalidasi</th><th>Ditolak</th><th>Online</th></tr>';
  for (const w of lb.leaderboard) {
    const gh = w.github_username ? `<a href="https://github.com/${e(w.github_username)}" target="_blank">@${e(w.github_username)}</a>` : '<span class="unverified">anonim</span>';
    h += `<tr><td>${w.rank}</td><td>${e(w.name)}</td><td>${gh}</td><td>${e(w.badge || '-')}</td><td>${w.credits}</td><td>${w.tasks_validated}</td><td>${w.reject_pct}%</td><td>${w.online?'ya':'tidak'}</td></tr>`;
  }
  h += '</table><h3>Job</h3><table><tr><th>ID</th><th>Jenis</th><th>Status</th><th>Tahap</th><th>Tugas selesai</th><th>Durasi (s)</th><th>Hasil</th></tr>';
  for (const j of s.jobs) {
    let res = j.pi ? ('pi = ' + j.pi.toFixed(6)) : '';
    if (j.kind === 'heat2d' && j.status === 'done') res = `suhu rata-rata ${j.mean_temp.toFixed(3)} &middot; <a href="/api/jobs/${j.id}/heatmap.png" target="_blank">heatmap</a>`;
    h += `<tr><td>${j.id}</td><td>${e(j.kind)}</td><td>${e(j.status)}</td><td>${Math.min(j.current_stage + 1, j.n_stages)}/${j.n_stages}</td><td>${j.done}/${j.total}</td><td>${Math.round(j.seconds||0)}</td><td>${res}</td></tr>`;
  }
  document.getElementById('d').innerHTML = h + '</table>';
}
load(); setInterval(load, 3000);
</script></body></html>"""
