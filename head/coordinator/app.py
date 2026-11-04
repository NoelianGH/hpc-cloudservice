import os, uuid
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

DB_URL = os.environ["DATABASE_URL"]
WORKER_TOKEN = os.environ["WORKER_TOKEN"]
ADMIN_TOKEN = os.environ["ADMIN_TOKEN"]
LEASE_SECONDS = 30

app = FastAPI(title="HPC Coordinator")

def db():
    return psycopg.connect(DB_URL, row_factory=dict_row, autocommit=True)

def check(auth, token):
    if auth != f"Bearer {token}":
        raise HTTPException(401, "token salah")

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
    check(authorization, WORKER_TOKEN)
    wid = uuid.uuid4().hex[:12]
    with db() as c:
        c.execute("INSERT INTO workers (id, name) VALUES (%s, %s)", (wid, body.name[:50]))
    return {"worker_id": wid, "lease_seconds": LEASE_SECONDS}

@app.post("/api/tasks/claim")
def claim(body: Claim, authorization: str = Header(None)):
    check(authorization, WORKER_TOKEN)
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
    check(authorization, WORKER_TOKEN)
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
    check(authorization, WORKER_TOKEN)
    with db() as c:
        r = c.execute("""
            UPDATE assignments SET status = 'submitted', result = %s, finished_at = now()
            WHERE id = %s AND worker_id = %s AND status = 'running' RETURNING id""",
            (Jsonb(body.result), body.assignment_id, body.worker_id)).fetchone()
    if not r:
        raise HTTPException(410, "lease sudah habis, hasil ditolak")
    return {"ok": True}

@app.post("/api/jobs")
def new_job(body: NewJob, authorization: str = Header(None)):
    check(authorization, ADMIN_TOKEN)
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
            SELECT name, credits, (now() - last_seen) < interval '60 seconds' AS online,
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
td,th{border:1px solid #ccc;padding:4px 10px}</style></head><body>
<h1>HPC Dashboard</h1><div id="d">memuat...</div>
<script>
const e = x => String(x).replace(/[&<>"']/g, c => '&#' + c.charCodeAt(0) + ';');
async function load(){
  const s = await (await fetch('/api/stats')).json();
  let h = '<h3>Tugas</h3><pre>' + JSON.stringify(s.tasks) + '</pre>';
  h += '<h3>Worker</h3><table><tr><th>Nama</th><th>Online</th><th>Sedang jalan</th><th>Kredit</th></tr>';
  for (const w of s.workers) h += `<tr><td>${e(w.name)}</td><td>${w.online?'ya':'tidak'}</td><td>${w.running}</td><td>${w.credits}</td></tr>`;
  h += '</table><h3>Job</h3><table><tr><th>ID</th><th>Jenis</th><th>Selesai</th><th>Durasi (s)</th><th>Hasil</th></tr>';
  for (const j of s.jobs) h += `<tr><td>${j.id}</td><td>${j.kind}</td><td>${j.done}/${j.total}</td><td>${Math.round(j.seconds||0)}</td><td>${j.pi?('pi = '+j.pi.toFixed(6)):''}</td></tr>`;
  document.getElementById('d').innerHTML = h + '</table>';
}
load(); setInterval(load, 3000);
</script></body></html>"""