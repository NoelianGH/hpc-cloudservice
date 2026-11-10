import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from github_verifier import check_github_worker
from email_service import generate_otp, send_otp_email

DB_URL = os.environ["DATABASE_URL"]
WORKER_TOKEN = os.environ["WORKER_TOKEN"]
ADMIN_TOKEN = os.environ["ADMIN_TOKEN"]
LEASE_SECONDS = 30
OTP_EXPIRY_MINUTES = 10

def db():
    return psycopg.connect(DB_URL, row_factory=dict_row, autocommit=True)

def init_db_schema():
    """
    Inisialisasi atau migrasi skema database secara otomatis dan aman (idempotent),
    agar tabel worker_auth_sessions dan kolom baru di workers langsung tersedia.
    """
    try:
        with db() as c:
            # Pastikan tabel sesi autentikasi CLI tersedia
            c.execute("""
                CREATE TABLE IF NOT EXISTS worker_auth_sessions (
                    session_id      TEXT PRIMARY KEY,
                    worker_name     TEXT NOT NULL,
                    github_username TEXT NOT NULL,
                    email           TEXT NOT NULL,
                    otp             TEXT NOT NULL,
                    otp_expires_at  TIMESTAMPTZ NOT NULL,
                    verified        BOOLEAN NOT NULL DEFAULT FALSE,
                    attempts        INT NOT NULL DEFAULT 0,
                    github_metrics  JSONB,
                    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)
            # Tambahkan kolom autentikasi baru pada tabel workers jika belum ada
            c.execute("ALTER TABLE workers ADD COLUMN IF NOT EXISTS github_username TEXT;")
            c.execute("ALTER TABLE workers ADD COLUMN IF NOT EXISTS email TEXT;")
            c.execute("ALTER TABLE workers ADD COLUMN IF NOT EXISTS auth_token TEXT UNIQUE;")
            c.execute("ALTER TABLE workers ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active';")
            c.execute("ALTER TABLE workers ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();")
            c.execute("CREATE INDEX IF NOT EXISTS idx_workers_auth_token ON workers (auth_token);")
            print("[DB] Skema database berhasil diinisialisasi / dimigrasi.", flush=True)
    except Exception as e:
        print(f"[DB WARN] Inisialisasi skema tertunda (db mungkin belum siap): {e}", flush=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db_schema()
    yield

app = FastAPI(title="HPC Coordinator", lifespan=lifespan)

def check_admin(auth: str | None):
    if auth != f"Bearer {ADMIN_TOKEN}":
        raise HTTPException(401, "Token admin salah")

def check_worker_auth(auth: str | None) -> dict:
    """
    Memvalidasi otentikasi worker. Mendukung dua mode:
    1. Token individual: Token unik yang didapat worker setelah verifikasi GitHub + OTP.
    2. Token global: WORKER_TOKEN dari .env (untuk backward-compatibility).
    """
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(401, "Header Authorization (Bearer token) diperlukan")
    
    token = auth.split("Bearer ", 1)[1].strip()
    
    # Cek apakah cocok dengan WORKER_TOKEN global
    if token == WORKER_TOKEN:
        return {"type": "global", "token": token}
    
    # Cek apakah cocok dengan token individual worker yang tersimpan di DB
    with db() as c:
        w = c.execute(
            "SELECT id, name, github_username, email, status FROM workers WHERE auth_token = %s",
            (token,)
        ).fetchone()
        if w:
            if w["status"] != "active":
                raise HTTPException(403, f"Status worker '{w['name']}' ditangguhkan ({w['status']})")
            return {"type": "individual", "worker": w}
            
    raise HTTPException(401, "Token worker tidak sah atau belum terdaftar")

# =============================================================================
# MODEL REQUEST & ENDPOINTS AUTENTIKASI CLI WORKER
# =============================================================================

class AuthRegisterRequest(BaseModel):
    worker_name: str
    github_username: str
    email: str

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
                        (session_id, worker_name, github_username, email, otp, otp_expires_at, github_metrics)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    session_id,
                    worker_name,
                    github_user,
                    email,
                    otp,
                    expires_at,
                    Jsonb(gh_check["factors"])
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
            c.execute("""
                UPDATE workers 
                SET name = %s, email = %s, auth_token = %s, status = 'active', last_seen = now()
                WHERE id = %s
            """, (session["worker_name"], session["email"], worker_token, wid))
        else:
            wid = f"w-{uuid.uuid4().hex[:8]}"
            c.execute("""
                INSERT INTO workers (id, name, github_username, email, auth_token, status)
                VALUES (%s, %s, %s, %s, %s, 'active')
            """, (wid, session["worker_name"], session["github_username"], session["email"], worker_token))

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

class Register(BaseModel):
    name: str

class Claim(BaseModel):
    worker_id: str

class Beat(BaseModel):
    worker_id: str
    assignment_id: int

class Submit(BaseModel):
    worker_id: str
    assignment_id: int
    result: dict

class NewJob(BaseModel):
    kind: str = "montecarlo_pi"   # atau "mandelbrot"
    n_tasks: int = 20
    size: int | None = None       # sampel per tugas (montecarlo) / lebar gambar (mandelbrot)
    replicas: int = 2

@app.post("/api/register")
def register(body: Register, authorization: str = Header(None)):
    auth_info = check_worker_auth(authorization)
    
    # Jika worker menggunakan token individual dari hasil autentikasi CLI
    if auth_info["type"] == "individual":
        wid = auth_info["worker"]["id"]
        with db() as c:
            c.execute("UPDATE workers SET name = %s, last_seen = now() WHERE id = %s", (body.name[:50], wid))
        return {"worker_id": wid, "lease_seconds": LEASE_SECONDS}

    # Jika worker menggunakan WORKER_TOKEN global
    wid = uuid.uuid4().hex[:12]
    with db() as c:
        c.execute("INSERT INTO workers (id, name) VALUES (%s, %s)", (wid, body.name[:50]))
    return {"worker_id": wid, "lease_seconds": LEASE_SECONDS}

@app.post("/api/tasks/claim")
def claim(body: Claim, authorization: str = Header(None)):
    check_worker_auth(authorization)
    with db() as c:
        c.execute("UPDATE workers SET last_seen = now() WHERE id = %s", (body.worker_id,))
        with c.transaction():
            t = c.execute("""
                SELECT t.id, t.kind, t.payload FROM tasks t
                WHERE t.status = 'pending'
                  AND (SELECT count(*) FROM assignments a
                       WHERE a.task_id = t.id AND a.status IN ('running','submitted')) < t.replicas
                  AND NOT EXISTS (SELECT 1 FROM assignments a
                       WHERE a.task_id = t.id AND a.worker_id = %s)
                ORDER BY t.id
                LIMIT 1
                FOR UPDATE SKIP LOCKED""", (body.worker_id,)).fetchone()
            if not t:
                return Response(status_code=204)
            a = c.execute("""
                INSERT INTO assignments (task_id, worker_id, lease_until)
                VALUES (%s, %s, now() + make_interval(secs => %s)) RETURNING id""",
                (t["id"], body.worker_id, LEASE_SECONDS)).fetchone()
    return {"assignment_id": a["id"], "task_id": t["id"], "kind": t["kind"], "payload": t["payload"]}

@app.post("/api/heartbeat")
def heartbeat(body: Beat, authorization: str = Header(None)):
    check_worker_auth(authorization)
    with db() as c:
        c.execute("UPDATE workers SET last_seen = now() WHERE id = %s", (body.worker_id,))
        r = c.execute("""
            UPDATE assignments SET lease_until = now() + make_interval(secs => %s)
            WHERE id = %s AND worker_id = %s AND status = 'running' RETURNING id""",
            (LEASE_SECONDS, body.assignment_id, body.worker_id)).fetchone()
    if not r:
        raise HTTPException(410, "lease sudah habis")
    return {"ok": True}

@app.post("/api/tasks/submit")
def submit(body: Submit, authorization: str = Header(None)):
    check_worker_auth(authorization)
    with db() as c:
        r = c.execute("""
            UPDATE assignments SET status = 'submitted', result = %s, finished_at = now()
            WHERE id = %s AND worker_id = %s AND status = 'running' RETURNING id""",
            (Jsonb(body.result), body.assignment_id, body.worker_id)).fetchone()
    if not r:
        raise HTTPException(410, "lease sudah habis, hasil ditolak")
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
def new_job(body: NewJob, authorization: str = Header(None)):
    check_admin(authorization)
    if body.kind not in ("montecarlo_pi", "mandelbrot"):
        raise HTTPException(400, "kind tidak dikenal")
    if body.size is None:  # bawaan: kira-kira 5-15 detik per tugas di laptop biasa
        body.size = 30_000_000 if body.kind == "montecarlo_pi" else 2000
    with db() as c, c.transaction():
        job = c.execute("INSERT INTO jobs (kind) VALUES (%s) RETURNING id", (body.kind,)).fetchone()
        for i in range(body.n_tasks):
            if body.kind == "montecarlo_pi":
                p = {"seed": job["id"] * 100000 + i, "samples": body.size}
            else:  # mandelbrot: gambar dibagi jadi n_tasks strip horizontal
                p = {"width": body.size, "height": body.size, "row_start": i * body.size // body.n_tasks,
                     "row_end": (i + 1) * body.size // body.n_tasks, "max_iter": 500}
            c.execute("INSERT INTO tasks (job_id, kind, payload, replicas) VALUES (%s, %s, %s, %s)",
                      (job["id"], body.kind, Jsonb(p), body.replicas))
    return {"job_id": job["id"], "tasks": body.n_tasks}

@app.get("/api/stats")
def stats():
    with db() as c:
        tasks = c.execute("SELECT status, count(*) AS n FROM tasks GROUP BY status").fetchall()
        workers = c.execute("""
            SELECT id, name, github_username, email, status, credits,
                   (now() - last_seen) < interval '60 seconds' AS online,
                   (SELECT count(*) FROM assignments a WHERE a.worker_id = w.id AND a.status = 'running') AS running
            FROM workers w ORDER BY credits DESC""").fetchall()
        jobs = c.execute("""
            SELECT j.id, j.kind,
                   count(*) AS total,
                   count(*) FILTER (WHERE t.status = 'done') AS done,
                   sum((t.result->>'inside')::bigint) FILTER (WHERE t.status = 'done') AS inside,
                   sum((t.payload->>'samples')::bigint) FILTER (WHERE t.status = 'done') AS samples,
                   EXTRACT(EPOCH FROM (SELECT max(a.finished_at) FROM assignments a
                       JOIN tasks t2 ON t2.id = a.task_id WHERE t2.job_id = j.id) - j.created_at) AS seconds
            FROM jobs j JOIN tasks t ON t.job_id = j.id
            GROUP BY j.id ORDER BY j.id DESC LIMIT 10""").fetchall()
    for j in jobs:
        if j["kind"] == "montecarlo_pi" and j["samples"]:
            j["pi"] = 4 * j["inside"] / j["samples"]
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
<h1>HPC Dashboard</h1><div id="d">memuat...</div>
<script>
const e = x => String(x || '').replace(/[&<>"']/g, c => '&#' + c.charCodeAt(0) + ';');
async function load(){
  const s = await (await fetch('/api/stats')).json();
  let h = '<h3>Tugas</h3><pre>' + JSON.stringify(s.tasks) + '</pre>';
  h += '<h3>Worker</h3><table><tr><th>Nama</th><th>GitHub</th><th>Status</th><th>Online</th><th>Sedang jalan</th><th>Kredit</th></tr>';
  for (const w of s.workers) {
    const gh = w.github_username ? `<a href="https://github.com/${e(w.github_username)}" target="_blank">@${e(w.github_username)}</a>` : '<span class="unverified">anonim</span>';
    const st = w.status === 'active' ? '<span class="verified">Terverifikasi</span>' : e(w.status);
    h += `<tr><td>${e(w.name)}</td><td>${gh}</td><td>${st}</td><td>${w.online?'ya':'tidak'}</td><td>${w.running}</td><td>${w.credits}</td></tr>`;
  }
  h += '</table><h3>Job</h3><table><tr><th>ID</th><th>Jenis</th><th>Selesai</th><th>Durasi (s)</th><th>Hasil</th></tr>';
  for (const j of s.jobs) h += `<tr><td>${j.id}</td><td>${j.kind}</td><td>${j.done}/${j.total}</td><td>${Math.round(j.seconds||0)}</td><td>${j.pi?('pi = '+j.pi.toFixed(6)):''}</td></tr>`;
  document.getElementById('d').innerHTML = h + '</table>';
}
load(); setInterval(load, 3000);
</script></body></html>"""
