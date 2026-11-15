"""
Proyek perangkat lunak (repo B) yang dikerjakan relawan + CI terdistribusi di compute node.

Dua peran relawan:
  1. DEVELOPER: admin membuat jobdesk (fitur / bug repo B). SISTEM meng-assign jobdesk
     otomatis secara FIFO ke relawan yang compute node-nya online (tanpa klik). Jobdesk tetap
     milik relawan itu sampai selesai, walau compute node-nya mati: yang dipindah sistem ke
     compute node lain adalah TUGAS komputasinya (lease habis -> diambil node lain). Relawan
     bekerja di branch  task/<id>-<judul>  di repo B. Setiap push = commit SHA baru (id versi).
     Ajukan review -> sistem membuka Pull Request; admin menyetujui -> sistem me-merge PR.
  2. COMPUTE NODE: setiap push ke repo B otomatis menjadi job 'ci' (lihat jobs.py):
     build -> test terpecah per file (tugas kecil, paralel di banyak node) -> laporan.
     Tugas dibagikan FIFO, divalidasi replikasi + quorum, pindah node bila node mati.

Status jobdesk:  open -> in_progress -> review -> done
                 (revisi: review -> in_progress;  batal: cancelled)

Deteksi push repo B (pilih salah satu atau keduanya):
  - webhook GitHub  POST /api/webhooks/github  (butuh koordinator bisa diakses publik +
    PROJECT_WEBHOOK_SECRET), atau
  - polling daftar branch tiap PROJECT_POLL_SECONDS detik oleh validator (tanpa URL publik).

Variabel lingkungan:
  PROJECT_REPO_URL        https://github.com/<org>/<repo-B>   (kosong = fitur proyek mati)
  PROJECT_APP_NAME        nama aplikasi yang dibangun (tampil di web)
  PROJECT_DEFAULT_BRANCH  bawaan main
  PROJECT_BRANCH_PREFIX   bawaan task/  (branch jobdesk; hanya branch ini + default yang di-CI)
  PROJECT_GIT_TOKEN       opsional, fine-grained token repo B: Contents R/W, Commit statuses R/W,
                          Pull requests R/W, Administration R/W (undang collaborator). Tanpa token:
                          branch, PR, merge, status commit & undangan dilakukan manual.
  PROJECT_WEBHOOK_SECRET  rahasia webhook GitHub (wajib bila webhook dipakai)
  PROJECT_POLL_SECONDS    bawaan 90 (0 = mati)
  JOBDESK_MAX_ACTIVE      jobdesk aktif maksimal per relawan, bawaan 1
  REQUIRE_CI_PASS         1 = jobdesk hanya bisa diajukan review bila CI commit terakhir lulus
  CI_REPLICAS, CI_TIMEOUT_S, CI_MEMORY_MB, CI_CPUS
"""
import hashlib
import hmac
import json
import os
import re
import time

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from psycopg.types.json import Jsonb

from admin import get_admin_session
from common import db, check_worker_auth
from jobs import JobError, create_job
from publisher import _api, parse_repo, PublishError
import watch

PROJECT_REPO_URL = os.environ.get("PROJECT_REPO_URL", "").strip().rstrip("/")
PROJECT_APP_NAME = os.environ.get("PROJECT_APP_NAME", "").strip() or "Aplikasi proyek (repo B)"
DEFAULT_BRANCH = os.environ.get("PROJECT_DEFAULT_BRANCH", "main").strip() or "main"
BRANCH_PREFIX = os.environ.get("PROJECT_BRANCH_PREFIX", "task/").strip() or "task/"
GIT_TOKEN = os.environ.get("PROJECT_GIT_TOKEN", "").strip()
WEBHOOK_SECRET = os.environ.get("PROJECT_WEBHOOK_SECRET", "").strip()
POLL_SECONDS = float(os.environ.get("PROJECT_POLL_SECONDS", "90") or 0)
MAX_ACTIVE = int(os.environ.get("JOBDESK_MAX_ACTIVE", "1") or 1)
ONLINE_SECONDS = 60   # worker dianggap online bila claim/heartbeat terakhir < 60 detik lalu
REQUIRE_CI_PASS = os.environ.get("REQUIRE_CI_PASS", "1") != "0"
CI_REPLICAS = int(os.environ.get("CI_REPLICAS", "2") or 2)
CI_RESOURCES = {"cpus": float(os.environ.get("CI_CPUS", "1") or 1),
                "memory_mb": int(os.environ.get("CI_MEMORY_MB", "512") or 512),
                "timeout_s": int(os.environ.get("CI_TIMEOUT_S", "300") or 300)}
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
STATUS_CONTEXT = "hpc-cloudservice/ci"

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]{1,100}$")
KINDS = ("fitur", "bug", "lainnya")

router = APIRouter(tags=["proyek"])


def log(msg):
    print(msg, flush=True)


# =============================================================================
# GitHub (repo B)
# =============================================================================

def enabled() -> bool:
    return bool(PROJECT_REPO_URL)


def _gh(method: str, path: str, body=None):
    owner, name = parse_repo(PROJECT_REPO_URL)
    return _api(method, f"/repos/{owner}/{name}{path}", body, GIT_TOKEN)


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40].strip("-") or "tugas"


def ci_branch(branch: str) -> bool:
    return branch == DEFAULT_BRANCH or branch.startswith(BRANCH_PREFIX)


def create_branch(branch: str) -> str:
    """Buat branch jobdesk dari ujung branch default (butuh PROJECT_GIT_TOKEN)."""
    if not (enabled() and GIT_TOKEN):
        return "manual"
    try:
        st, ref = _gh("GET", f"/git/ref/heads/{DEFAULT_BRANCH}")
        if st != 200:
            return f"gagal: branch {DEFAULT_BRANCH} tidak terbaca (HTTP {st})"
        st, data = _gh("POST", "/git/refs", {"ref": f"refs/heads/{branch}", "sha": ref["object"]["sha"]})
        return "dibuat" if st == 201 else ("sudah ada" if st == 422 else f"gagal (HTTP {st})")
    except PublishError as e:
        return f"gagal: {e}"


def invite_collaborator(username: str | None) -> str:
    """Undang relawan sebagai collaborator repo B (izin push) agar bisa push ke branch-nya."""
    if not (enabled() and GIT_TOKEN and username):
        return "manual"
    try:
        st, _ = _gh("PUT", f"/collaborators/{username}", {"permission": "push"})
        return {201: "undangan dikirim", 204: "sudah collaborator"}.get(st, f"gagal (HTTP {st})")
    except PublishError as e:
        return f"gagal: {e}"


def commit_status(sha: str, state: str, description: str) -> None:
    """Tanda centang/silang di GitHub pada commit itu (best effort)."""
    if not (enabled() and GIT_TOKEN):
        return
    try:
        _gh("POST", f"/statuses/{sha}", {"state": state, "context": STATUS_CONTEXT,
                                         "description": description[:140]})
    except Exception as e:
        log(f"status commit {sha[:7]} gagal: {e}")


def open_pull_request(d: dict, w: dict) -> dict:
    """Buka PR branch jobdesk -> branch default (atau pakai PR terbuka yang sudah ada)."""
    if not (enabled() and GIT_TOKEN and d.get("branch")):
        return {"status": "manual"}
    body = (f"Jobdesk #{d['id']} ({d['kind']}, {d['credit']} kredit) oleh {w['name']} (@{w.get('github_username')}).\n\n"
            f"{d.get('description') or ''}\n\nCI terdistribusi HPC: LULUS pada {(d.get('last_sha') or '')[:7]}.\n"
            "Dibuka otomatis oleh hpc-cloudservice saat relawan mengajukan review.")
    try:
        st, pr = _gh("POST", "/pulls", {"title": f"#{d['id']} {d['title']}", "head": d["branch"],
                                        "base": DEFAULT_BRANCH, "body": body})
        if st == 422:  # PR untuk branch ini sudah ada -> pakai yang terbuka
            owner, _ = parse_repo(PROJECT_REPO_URL)
            st2, lst = _gh("GET", f"/pulls?state=open&head={owner}:{d['branch']}")
            if st2 == 200 and isinstance(lst, list) and lst:
                return {"status": "sudah ada", "number": lst[0]["number"], "url": lst[0]["html_url"]}
            return {"status": f"gagal (HTTP 422): {(pr or {}).get('message')}"}
        if st == 201:
            return {"status": "dibuka", "number": pr["number"], "url": pr["html_url"]}
        return {"status": f"gagal (HTTP {st})"}
    except PublishError as e:
        return {"status": f"gagal: {e}"}


def merge_pull_request(d: dict) -> str | None:
    """
    Merge PR jobdesk saat admin menyetujui. Dipatok ke commit yang lulus CI (sha = last_sha):
    bila relawan push lagi setelah review, GitHub menolak (409) dan admin harus meninjau ulang.
    Mengembalikan SHA merge, None bila tidak ada token/PR (merge manual di GitHub).
    """
    if not (enabled() and GIT_TOKEN and d.get("pr_number")):
        return None
    st, r = _gh("PUT", f"/pulls/{d['pr_number']}/merge",
                {"merge_method": "squash", "sha": d["last_sha"],
                 "commit_title": f"#{d['id']} {d['title']} (#{d['pr_number']})"})
    if st == 200 and isinstance(r, dict) and r.get("merged"):
        return r.get("sha") or "merged"
    msg = (r or {}).get("message") if isinstance(r, dict) else r
    reason = {405: "PR tidak bisa di-merge (konflik dengan main?). Minta revisi agar relawan memperbarui branch.",
              409: "Ada push baru setelah diajukan. Tunggu CI lalu tinjau ulang."}.get(st, f"HTTP {st}")
    raise HTTPException(409, f"Merge PR #{d['pr_number']} gagal: {reason} ({msg})")


def branch_head(branch: str) -> str | None:
    st, data = _gh("GET", f"/branches/{branch}")
    if st == 200 and isinstance(data, dict):
        return data.get("commit", {}).get("sha")
    return None


def list_branches() -> list[tuple[str, str]]:
    out, page = [], 1
    while page <= 5:
        st, data = _gh("GET", f"/branches?per_page=100&page={page}")
        if st != 200 or not isinstance(data, list):
            raise PublishError(f"daftar branch gagal (HTTP {st}): {data}")
        out += [(b["name"], b["commit"]["sha"]) for b in data]
        if len(data) < 100:
            break
        page += 1
    return out


# =============================================================================
# Push -> job CI
# =============================================================================

def _event(c, jobdesk_id: int, actor: str, event: str, detail: str = "") -> None:
    c.execute("INSERT INTO jobdesk_events (jobdesk_id, actor, event, detail) VALUES (%s, %s, %s, %s)",
              (jobdesk_id, actor[:80], event, detail[:500]))


def note_push(c, branch: str, sha: str, source: str, pusher: str | None = None, forced: bool = False) -> None:
    """Catat push ke branch yang TIDAK di-CI (mis. branch di luar aturan) agar tetap dicek watch."""
    sha = (sha or "").lower()
    if SHA_RE.match(sha) and BRANCH_RE.match(branch or ""):
        c.execute("""INSERT INTO repo_pushes (branch, sha, source, pusher, forced) VALUES (%s, %s, %s, %s, %s)
                     ON CONFLICT DO NOTHING""", (branch, sha, source, pusher, forced))


def register_push(c, branch: str, sha: str, source: str, force: bool = False,
                  pusher: str | None = None, forced: bool = False) -> int | None:
    """
    Catat push (branch, sha). Bila baru: batalkan CI lama branch itu yang masih berjalan
    (sudah usang), lalu buat job CI untuk commit ini. Mengembalikan job_id atau None.
    """
    sha = (sha or "").lower()
    if not enabled() or not SHA_RE.match(sha) or not BRANCH_RE.match(branch or "") or ".." in branch:
        return None
    with c.transaction():
        new = c.execute("""INSERT INTO repo_pushes (branch, sha, source, pusher, forced)
                           VALUES (%s, %s, %s, %s, %s)
                           ON CONFLICT DO NOTHING RETURNING sha""", (branch, sha, source, pusher, forced)).fetchone()
        if not new and not force:
            return None
        if not force and branch != DEFAULT_BRANCH and c.execute(
                "SELECT 1 FROM repo_pushes WHERE branch = %s AND sha = %s", (DEFAULT_BRANCH, sha)).fetchone():
            return None  # branch baru yang belum punya commit sendiri (sama dengan main): tidak perlu CI
        old = c.execute("""UPDATE jobs SET status = 'cancelled', finished_at = now(),
                                  result = jsonb_build_object('ci_status', 'cancelled',
                                      'reason', 'digantikan push baru ' || %s::text)
                           WHERE kind = 'ci' AND status = 'running' AND spec->>'branch' = %s
                           RETURNING id, spec->>'sha' AS sha""", (sha[:7], branch)).fetchall()
        if old:
            c.execute("UPDATE tasks SET status = 'cancelled' WHERE job_id = ANY(%s) AND status = 'pending'",
                      ([o["id"] for o in old],))
        jd = c.execute("""SELECT id FROM jobdesks WHERE branch = %s AND status IN ('in_progress', 'review')
                          ORDER BY id DESC LIMIT 1""", (branch,)).fetchone()
        job = create_job(c, {"kind": "ci", "replicas": CI_REPLICAS, "resources": CI_RESOURCES,
                             "code": {"repo_url": PROJECT_REPO_URL, "sha": sha, "entry": "hpc.json"},
                             "params": {"branch": branch, "source": source,
                                        "jobdesk_id": jd["id"] if jd else None}})
        c.execute("UPDATE repo_pushes SET job_id = %s WHERE branch = %s AND sha = %s",
                  (job["job_id"], branch, sha))
        if jd:
            c.execute("""UPDATE jobdesks SET last_sha = %s, last_ci_job = %s, last_ci_status = 'running',
                                updated_at = now() WHERE id = %s""", (sha, job["job_id"], jd["id"]))
            _event(c, jd["id"], source, "push", f"{sha[:7]} -> CI job #{job['job_id']}")
    log(f"push {branch}@{sha[:7]} ({source}) -> CI job #{job['job_id']}"
        + (f", {len(old)} CI lama dibatalkan" if old else ""))
    for o in old:
        commit_status(o["sha"], "error", f"Dibatalkan: digantikan push {sha[:7]}")
    commit_status(sha, "pending", f"Build & test terdistribusi (job #{job['job_id']})")
    return job["job_id"]


def on_job_finished(c, job_id: int) -> None:
    """Dipanggil validator setelah job selesai: sinkron status jobdesk + status commit GitHub."""
    j = c.execute("SELECT kind, status, spec, result FROM jobs WHERE id = %s", (job_id,)).fetchone()
    if not j or j["kind"] != "ci":
        return
    r = j["result"] or {}
    verdict = r.get("ci_status") or ("error" if j["status"] == "failed" else "passed")
    c.execute("UPDATE jobdesks SET last_ci_status = %s, updated_at = now() WHERE last_ci_job = %s",
              (verdict, job_id))
    jd = c.execute("SELECT id FROM jobdesks WHERE last_ci_job = %s", (job_id,)).fetchone()
    if jd:
        _event(c, jd["id"], "ci", f"ci_{verdict}", f"job #{job_id}: {r.get('shards_total', 0)} shard, "
               f"{r.get('nodes', 0)} node, {r.get('wall_s')} s")
    state = {"passed": "success", "failed": "failure"}.get(verdict, "error")
    desc = (f"{r.get('shards_total', 0)} file test, {r.get('tests_total', 0)} test, "
            f"{r.get('nodes', 0)} node, {r.get('wall_s')} s") if verdict != "error" else "CI error"
    if verdict == "failed" and not r.get("build", {}).get("build_ok", True):
        desc = "build gagal"
    commit_status(j["spec"]["sha"], state, desc)


_last_poll = 0.0


def poll(c) -> None:
    """Dipanggil validator tiap putaran; cek branch repo B tiap POLL_SECONDS detik."""
    global _last_poll
    if not enabled() or POLL_SECONDS <= 0 or time.time() - _last_poll < POLL_SECONDS:
        return
    _last_poll = time.time()
    try:
        branches = list_branches()
    except Exception as e:
        log(f"polling repo proyek gagal: {e}")
        return
    branches.sort(key=lambda b: b[0] != DEFAULT_BRANCH)  # branch default dulu (lihat register_push)
    for name, sha in branches:
        if ci_branch(name):
            try:
                register_push(c, name, sha, "poll")
            except JobError as e:
                log(f"CI {name}@{sha[:7]} tidak dibuat: {e}")
        else:
            note_push(c, name, sha, "poll")   # tidak di-CI, tetapi dicek watch (branch di luar aturan)


# =============================================================================
# Otorisasi
# =============================================================================

def _admin(auth: str | None) -> str:
    if ADMIN_TOKEN and auth and hmac.compare_digest(auth.encode(), f"Bearer {ADMIN_TOKEN}".encode()):
        return "admin-cli"
    s = get_admin_session(auth)
    if s:
        return s.get("email") or "admin"
    raise HTTPException(401, "Akses admin ditolak.")


def _volunteer(auth: str | None) -> dict:
    info = check_worker_auth(auth)
    if info["type"] != "individual":
        raise HTTPException(403, "Butuh token pribadi relawan (hpc_w_...), bukan token global.")
    return info["worker"]


def _need_project():
    if not enabled():
        raise HTTPException(503, "PROJECT_REPO_URL (repo B) belum diisi di .env koordinator.")


# =============================================================================
# Data
# =============================================================================

_JD_SQL = """
    SELECT d.id, d.title, d.description, d.kind, d.credit, d.status, d.worker_id, d.branch, d.note,
           d.last_sha, d.last_ci_job, d.last_ci_status, d.created_at, d.assigned_at, d.submitted_at,
           d.done_at, d.updated_at, d.pr_number, d.pr_url, d.merged_sha,
           w.name AS worker_name, w.github_username, w.last_seen AS worker_last_seen,
           coalesce((now() - w.last_seen) < interval '60 seconds', false) AS worker_online
    FROM jobdesks d LEFT JOIN workers w ON w.id = d.worker_id
"""


def project_info() -> dict:
    return {"enabled": enabled(), "repo_url": PROJECT_REPO_URL or None, "app_name": PROJECT_APP_NAME,
            "default_branch": DEFAULT_BRANCH, "branch_prefix": BRANCH_PREFIX,
            "github_token": bool(GIT_TOKEN), "webhook": bool(WEBHOOK_SECRET),
            "poll_seconds": POLL_SECONDS, "require_ci_pass": REQUIRE_CI_PASS,
            "max_active": MAX_ACTIVE, "ci_resources": CI_RESOURCES, "ci_replicas": CI_REPLICAS}


def _ci_rows(c, where: str = "TRUE", args: tuple = (), limit: int = 30) -> list[dict]:
    rows = c.execute(f"""
        SELECT j.id, j.status, j.current_stage, j.created_at, j.finished_at, j.spec, j.result,
               count(t.id) FILTER (WHERE t.stage = 1) AS shards,
               count(t.id) FILTER (WHERE t.stage = 1 AND t.status = 'done') AS shards_done,
               (SELECT count(DISTINCT a.worker_id) FROM assignments a JOIN tasks t2 ON t2.id = a.task_id
                 WHERE t2.job_id = j.id AND a.status IN ('running', 'submitted')) AS nodes
        FROM jobs j LEFT JOIN tasks t ON t.job_id = j.id
        WHERE j.kind = 'ci' AND {where}
        GROUP BY j.id ORDER BY j.id DESC LIMIT %s""", (*args, limit)).fetchall()
    out = []
    for r in rows:
        res, spec = r["result"] or {}, r["spec"] or {}
        verdict = res.get("ci_status") or ("running" if r["status"] == "running" else r["status"])
        step = ("build" if r["current_stage"] == 0 else "test") if r["status"] == "running" else "selesai"
        out.append({"job_id": r["id"], "branch": spec.get("branch"), "sha": spec.get("sha"),
                    "source": spec.get("source"), "jobdesk_id": spec.get("jobdesk_id"),
                    "status": verdict, "step": step, "shards": r["shards"], "shards_done": r["shards_done"],
                    "nodes": res.get("nodes", r["nodes"]), "wall_s": res.get("wall_s"),
                    "compute_s": res.get("compute_s"), "speedup_est": res.get("speedup_est"),
                    "tests_total": res.get("tests_total"), "tests_failed": res.get("tests_failed"),
                    "shards_failed": res.get("shards_failed"), "created_at": r["created_at"],
                    "finished_at": r["finished_at"], "build_error": (res.get("build") or {}).get("error")
                    or res.get("error")})
    return out


def _git_help(branch: str | None) -> list[str]:
    if not (PROJECT_REPO_URL and branch):
        return []
    return [f"git clone {PROJECT_REPO_URL}.git", f"cd {PROJECT_REPO_URL.rsplit('/', 1)[-1]}",
            "git fetch origin", f"git switch {branch} 2>/dev/null || git switch -c {branch} origin/{DEFAULT_BRANCH}",
            "# ... ngoding di VS Code, lalu:", "git add -A && git commit -m \"<pesan>\"",
            f"git push -u origin {branch}"]


# =============================================================================
# Endpoint publik
# =============================================================================

@router.get("/api/project")
def public_project():
    with db() as c:
        counts = {r["status"]: r["n"] for r in c.execute(
            "SELECT status, count(*) AS n FROM jobdesks GROUP BY status").fetchall()}
        ci = _ci_rows(c, limit=10)
    info = project_info()
    return {"project": {k: info[k] for k in ("enabled", "repo_url", "app_name", "default_branch")},
            "jobdesks": counts, "ci": [{k: x[k] for k in ("job_id", "branch", "sha", "status", "step", "shards",
                                                           "shards_done", "nodes", "wall_s")} for x in ci]}


# =============================================================================
# Relawan (token pribadi)
# =============================================================================

@router.get("/api/me/jobdesk")
def my_jobdesk(authorization: str = Header(None)):
    w = _volunteer(authorization)
    with db() as c:
        mine = c.execute(_JD_SQL + " WHERE d.worker_id = %s ORDER BY d.id DESC LIMIT 30", (w["id"],)).fetchall()
        queue = c.execute("SELECT count(*) AS n FROM jobdesks WHERE status = 'open'").fetchone()["n"]
        me = c.execute("SELECT (now() - last_seen) < make_interval(secs => %s) AS online, last_seen "
                       "FROM workers WHERE id = %s", (ONLINE_SECONDS, w["id"])).fetchone()
        branches = [d["branch"] for d in mine if d["branch"]]
        ci = _ci_rows(c, "spec->>'branch' = ANY(%s)", (branches,), 10) if branches else []
    active = [d for d in mine if d["status"] in ("in_progress", "review")]
    for d in active:
        d["git"] = _git_help(d["branch"])
    return {"project": project_info(), "active": active,
            "history": [d for d in mine if d["status"] not in ("in_progress", "review")],
            "queue_open": queue, "online": me["online"], "last_seen": me["last_seen"], "ci": ci}


def _my_active(c, w: dict, jid: int) -> dict:
    d = c.execute(_JD_SQL + " WHERE d.id = %s FOR UPDATE OF d", (jid,)).fetchone()
    if not d or d["worker_id"] != w["id"]:
        raise HTTPException(404, "Jobdesk tidak ditemukan atau bukan milik Anda.")
    return d


@router.post("/api/me/jobdesk/{jid}/submit")
def submit_jobdesk(jid: int, authorization: str = Header(None)):
    """
    Ajukan review. Bila REQUIRE_CI_PASS, CI commit terakhir di branch harus lulus.
    Dengan PROJECT_GIT_TOKEN, sistem membuka Pull Request branch jobdesk -> branch default.
    """
    w = _volunteer(authorization)
    with db() as c:
        with c.transaction():
            d = _my_active(c, w, jid)
            if d["status"] != "in_progress":
                raise HTTPException(409, f"Jobdesk berstatus '{d['status']}', tidak bisa diajukan.")
            if not d["last_sha"]:
                raise HTTPException(409, "Belum ada commit baru di branch Anda. Push kode dulu.")
            if REQUIRE_CI_PASS and d["last_ci_status"] != "passed":
                raise HTTPException(409, "Push kode ke branch Anda dan tunggu CI terdistribusi LULUS "
                                         f"(status CI terakhir: {d['last_ci_status'] or 'belum ada push'}).")
            c.execute("UPDATE jobdesks SET status = 'review', submitted_at = now(), updated_at = now() "
                      "WHERE id = %s", (jid,))
            _event(c, jid, w["name"], "review", f"diajukan @ {(d['last_sha'] or '-')[:7]}")
        pr = open_pull_request(d, w)
        if pr.get("number"):
            c.execute("UPDATE jobdesks SET pr_number = %s, pr_url = %s WHERE id = %s",
                      (pr["number"], pr["url"], jid))
        _event(c, jid, "sistem", "pull_request", pr.get("url") or pr["status"])
    return {"ok": True, "pull_request": pr}


# =============================================================================
# Penugasan otomatis (dipanggil validator setiap putaran)
# =============================================================================

def auto_assign(c) -> None:
    """
    FIFO dua arah, tanpa klik:
      - jobdesk: yang paling lama menunggu (id terkecil) diberikan lebih dulu;
      - relawan: hanya yang compute node-nya ONLINE (worker berjalan) dan belum punya jobdesk
        aktif; yang paling lama menganggur (jobdesk terakhir selesai paling awal) didahulukan.
    """
    if not enabled():
        return
    done = []
    for _ in range(20):
        with c.transaction():
            w = c.execute("""
                SELECT w.id, w.name, w.github_username FROM workers w
                WHERE w.auth_token IS NOT NULL AND w.status = 'active' AND w.github_username IS NOT NULL
                  AND (now() - w.last_seen) < %s * interval '1 second'
                  AND (SELECT count(*) FROM jobdesks d WHERE d.worker_id = w.id
                       AND d.status IN ('in_progress', 'review')) < %s
                ORDER BY coalesce((SELECT max(d.done_at) FROM jobdesks d WHERE d.worker_id = w.id), w.created_at), w.id
                LIMIT 1 FOR UPDATE OF w SKIP LOCKED""", (ONLINE_SECONDS, MAX_ACTIVE)).fetchone()
            if not w:
                break
            d = c.execute("""SELECT id, title, branch FROM jobdesks WHERE status = 'open'
                             ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED""").fetchone()
            if not d:
                break
            branch = d["branch"] or f"{BRANCH_PREFIX}{d['id']}-{slug(d['title'])}"
            c.execute("""UPDATE jobdesks SET status = 'in_progress', worker_id = %s, branch = %s,
                                assigned_at = now(), updated_at = now() WHERE id = %s""",
                      (w["id"], branch, d["id"]))
            _event(c, d["id"], "sistem", "di-assign", f"FIFO ke {w['name']} (@{w['github_username']})"
                   + (" melanjutkan branch yang sudah ada" if d["branch"] else ""))
        done.append((d["id"], branch, w))
    for jid, branch, w in done:  # panggilan GitHub di luar transaksi
        made = create_branch(branch)
        invite = invite_collaborator(w["github_username"])
        _event(c, jid, "sistem", "branch", f"branch {branch}: {made}; collaborator: {invite}")
        log(f"jobdesk #{jid} di-assign ke {w['name']} -> {branch} (branch {made}, collaborator {invite})")


# =============================================================================
# Admin
# =============================================================================

class NewJobdesk(BaseModel):
    title: str
    description: str = ""
    kind: str = "fitur"
    credit: int = 10


class JobdeskAction(BaseModel):
    action: str          # approve | revise | cancel | reopen
    note: str = ""


class CiRequest(BaseModel):
    branch: str
    sha: str | None = None


@router.get("/api/admin/project")
def admin_project(authorization: str = Header(None)):
    _admin(authorization)
    with db() as c:
        counts = {r["status"]: r["n"] for r in c.execute(
            "SELECT status, count(*) AS n FROM jobdesks GROUP BY status").fetchall()}
        pushes = c.execute("SELECT branch, sha, source, seen_at, job_id FROM repo_pushes "
                           "ORDER BY seen_at DESC LIMIT 20").fetchall()
    return {"project": project_info(), "jobdesks": counts, "pushes": pushes}


@router.get("/api/admin/jobdesks")
def admin_jobdesks(authorization: str = Header(None), status: str | None = None):
    _admin(authorization)
    with db() as c:
        if status:
            rows = c.execute(_JD_SQL + " WHERE d.status = %s ORDER BY d.id", (status,)).fetchall()
        else:
            rows = c.execute(_JD_SQL + """ ORDER BY CASE d.status WHEN 'review' THEN 0 WHEN 'in_progress' THEN 1
                                           WHEN 'open' THEN 2 ELSE 3 END, d.id LIMIT 300""").fetchall()
        ev = c.execute("""SELECT e.jobdesk_id, e.at, e.actor, e.event, e.detail FROM jobdesk_events e
                          ORDER BY e.id DESC LIMIT 40""").fetchall()
    return {"jobdesks": rows, "events": ev, "project": project_info()}


@router.post("/api/admin/jobdesks")
def admin_new_jobdesk(body: NewJobdesk, authorization: str = Header(None)):
    who = _admin(authorization)
    title = body.title.strip()
    if not 3 <= len(title) <= 120:
        raise HTTPException(400, "Judul 3-120 karakter.")
    if body.kind not in KINDS:
        raise HTTPException(400, f"Jenis harus salah satu: {', '.join(KINDS)}")
    if not 0 <= body.credit <= 1000:
        raise HTTPException(400, "Kredit 0-1000.")
    with db() as c:
        d = c.execute("""INSERT INTO jobdesks (title, description, kind, credit) VALUES (%s, %s, %s, %s)
                         RETURNING id""", (title, body.description.strip()[:4000], body.kind, body.credit)).fetchone()
        _event(c, d["id"], who, "dibuat", title)
    return {"ok": True, "jobdesk_id": d["id"]}


@router.post("/api/admin/jobdesks/{jid}/action")
def admin_jobdesk_action(jid: int, body: JobdeskAction, authorization: str = Header(None)):
    who = _admin(authorization)
    # Tidak ada aksi "pindahkan ke relawan lain": penugasan sepenuhnya oleh sistem (FIFO),
    # termasuk pemindahan otomatis saat compute node relawan offline.
    allowed = {"approve": ("review",), "revise": ("review",),
               "cancel": ("open", "in_progress", "review"), "reopen": ("cancelled", "done")}
    if body.action not in allowed:
        raise HTTPException(400, "Aksi tidak dikenal.")
    with db() as c:
        with c.transaction():
            d = c.execute("SELECT * FROM jobdesks WHERE id = %s FOR UPDATE", (jid,)).fetchone()
            if not d:
                raise HTTPException(404, "Jobdesk tidak ditemukan.")
            if d["status"] not in allowed[body.action]:
                raise HTTPException(409, f"Aksi '{body.action}' tidak berlaku untuk status '{d['status']}'.")
            note = body.note.strip()[:1000] or None
            if body.action == "approve":
                if REQUIRE_CI_PASS and d["last_ci_status"] != "passed":
                    raise HTTPException(409, "CI commit terakhir belum lulus (ada push baru?). Tunggu CI.")
                merged = merge_pull_request(d)   # tanpa token/PR: merge manual di GitHub
                c.execute("UPDATE jobdesks SET status = 'done', done_at = now(), updated_at = now(), note = %s, "
                          "merged_sha = %s WHERE id = %s", (note, merged, jid))
                if merged:
                    _event(c, jid, "sistem", "merge", f"PR #{d['pr_number']} di-merge ke {DEFAULT_BRANCH} ({merged[:7]})")
                c.execute("UPDATE workers SET credits = credits + %s WHERE id = %s", (d["credit"], d["worker_id"]))
            elif body.action == "revise":
                c.execute("UPDATE jobdesks SET status = 'in_progress', updated_at = now(), note = %s "
                          "WHERE id = %s", (note or "Perlu revisi", jid))
            elif body.action == "cancel":
                c.execute("UPDATE jobdesks SET status = 'cancelled', updated_at = now(), note = %s WHERE id = %s",
                          (note, jid))
            else:  # reopen
                c.execute("UPDATE jobdesks SET status = 'open', worker_id = NULL, done_at = NULL, pr_number = NULL, "
                          "pr_url = NULL, merged_sha = NULL, updated_at = now(), note = %s WHERE id = %s", (note, jid))
            _event(c, jid, who, body.action, note or "")
    return {"ok": True}


@router.get("/api/admin/ci")
def admin_ci(authorization: str = Header(None), limit: int = 30):
    _admin(authorization)
    with db() as c:
        runs = _ci_rows(c, limit=max(1, min(limit, 100)))
        ids = [r["job_id"] for r in runs[:10]]
        tasks = c.execute("""
            SELECT t.job_id, t.id, t.stage, t.status, t.payload->>'file' AS file, t.result,
                   array_agg(w.name ORDER BY a.id) FILTER (WHERE a.id IS NOT NULL) AS workers,
                   array_agg(a.status ORDER BY a.id) FILTER (WHERE a.id IS NOT NULL) AS a_status
            FROM tasks t LEFT JOIN assignments a ON a.task_id = t.id LEFT JOIN workers w ON w.id = a.worker_id
            WHERE t.job_id = ANY(%s) GROUP BY t.id ORDER BY t.job_id DESC, t.stage, t.block""", (ids,)).fetchall()
    by_job: dict[int, list] = {}
    for t in tasks:
        r = t.pop("result") or {}
        t.update({"passed": r.get("passed"), "tests": r.get("tests"), "failures": r.get("failures"),
                  "build_ok": r.get("build_ok"), "error": r.get("error")})
        by_job.setdefault(t["job_id"], []).append(t)
    for r in runs:
        r["tasks"] = by_job.get(r["job_id"], [])
    return {"runs": runs, "project": project_info()}


@router.get("/api/admin/ci/{job_id}/log")
def admin_ci_log(job_id: int, authorization: str = Header(None)):
    _admin(authorization)
    with db() as c:
        rows = c.execute("""
            SELECT t.id AS task_id, t.stage, t.payload->>'file' AS file, w.name AS worker, a.status, a.log
            FROM tasks t JOIN assignments a ON a.task_id = t.id JOIN workers w ON w.id = a.worker_id
            JOIN jobs j ON j.id = t.job_id
            WHERE t.job_id = %s AND j.kind = 'ci' AND a.log IS NOT NULL ORDER BY t.stage, t.block, a.id""",
            (job_id,)).fetchall()
    return {"logs": rows}


@router.post("/api/admin/ci")
def admin_run_ci(body: CiRequest, authorization: str = Header(None)):
    """Jalankan CI manual untuk sebuah branch (SHA ujung branch diambil dari GitHub bila tidak diberikan)."""
    _admin(authorization)
    _need_project()
    branch = body.branch.strip()
    if not BRANCH_RE.match(branch) or ".." in branch:
        raise HTTPException(400, "Nama branch tidak valid.")
    sha = (body.sha or "").strip().lower() or branch_head(branch)
    if not sha or not SHA_RE.match(sha):
        raise HTTPException(404, f"Branch {branch} tidak ditemukan di repo proyek.")
    with db() as c:
        try:
            jid = register_push(c, branch, sha, "manual", force=True)
        except JobError as e:
            raise HTTPException(400, str(e))
    return {"ok": True, "job_id": jid, "branch": branch, "sha": sha}


# =============================================================================
# Webhook GitHub
# =============================================================================

@router.post("/api/webhooks/github")
async def github_webhook(request: Request, x_github_event: str = Header(None),
                         x_hub_signature_256: str = Header(None)):
    if not (enabled() and WEBHOOK_SECRET):
        raise HTTPException(503, "Webhook belum diaktifkan (PROJECT_REPO_URL / PROJECT_WEBHOOK_SECRET kosong).")
    raw = await request.body()
    expected = "sha256=" + hmac.new(WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    if not x_hub_signature_256 or not hmac.compare_digest(expected, x_hub_signature_256):
        ip = request.client.host if request.client else "?"
        watch.alert_now(f"webhook_sig:{ip}:{watch._hour()}", "warning", "suspicious",
                        "Webhook GitHub dengan tanda tangan salah ditolak",
                        f"Dari {ip}. Bisa salah isi PROJECT_WEBHOOK_SECRET, atau ada yang memalsukan push.",
                        {"ip": ip}, repeat=True)
        raise HTTPException(401, "Tanda tangan webhook tidak sah.")
    if x_github_event == "ping":
        return {"ok": True, "pong": True}
    if x_github_event != "push":
        return {"ok": True, "ignored": x_github_event}
    ev = json.loads(raw or b"{}")
    repo = (ev.get("repository") or {}).get("html_url", "").rstrip("/")
    if repo.lower() != PROJECT_REPO_URL.lower().removesuffix(".git"):
        watch.alert_now(f"webhook_repo:{repo[:100]}", "warning", "suspicious",
                        "Webhook dari repo lain ditolak", f"Repo {repo or '-'} memakai rahasia webhook proyek ini.")
        raise HTTPException(400, "Webhook bukan dari repo proyek.")
    ref, sha = ev.get("ref", ""), ev.get("after", "")
    pusher = ((ev.get("sender") or {}).get("login") or (ev.get("pusher") or {}).get("name") or "")[:100] or None
    branch = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ""
    if branch and ev.get("deleted"):
        with db() as c:
            jd = c.execute("""SELECT id FROM jobdesks WHERE branch = %s AND status IN ('in_progress', 'review')""",
                           (branch,)).fetchone()
            if jd or branch == DEFAULT_BRANCH:
                watch.alert(c, f"branch_deleted:{branch}:{ev.get('before', '')}", "critical", "branch",
                            f"Branch {branch} dihapus" + (f" (jobdesk #{jd['id']} masih aktif)" if jd else ""),
                            f"Dihapus oleh {pusher or 'tidak diketahui'}. Pulihkan dari GitHub (Branches -> Restore).",
                            {"branch": branch, "jobdesk_id": jd["id"] if jd else None})
        return {"ok": True, "ignored": "branch dihapus"}
    if not branch or set(sha) == {"0"}:
        return {"ok": True, "ignored": "bukan push branch"}
    forced = bool(ev.get("forced"))
    with db() as c:
        if not ci_branch(branch):
            note_push(c, branch, sha, "webhook", pusher, forced)
            return {"ok": True, "ignored": f"branch {branch} tidak di-CI"}
        jid = register_push(c, branch, sha, "webhook", pusher=pusher, forced=forced)
        if jid is None and (pusher or forced):   # sha sudah tercatat lewat polling: lengkapi siapa yang push
            c.execute("""UPDATE repo_pushes SET pusher = coalesce(pusher, %s), forced = forced OR %s
                         WHERE branch = %s AND sha = %s""", (pusher, forced, branch, sha.lower()))
    return {"ok": True, "job_id": jid}
