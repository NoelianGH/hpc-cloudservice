"""
Publikasi hasil job ke GitHub: SATU commit per job di branch tersendiri
(bawaan: results/job-<id>), dibuat HANYA oleh head node dengan token miliknya.
Worker relawan tidak pernah memegang token GitHub dan tidak pernah push.

Repo tujuan:
  RESULTS_REPO_URL  (mis. https://github.com/org/hpc-results), atau bila kosong
  repo job itu sendiri (code.repo_url), sehingga branch hasil berinduk tepat pada
  commit SHA kode yang menghasilkannya (jejak asal/provenance jelas).
Token: RESULTS_GIT_TOKEN (fine-grained token, izin Contents: read & write pada repo itu saja).
Bila token kosong, publikasi dilewati (hasil tetap tersimpan di database dan bisa diunduh
lewat /api/jobs/<id>/result).

Memakai GitHub REST API (Git Data API) via urllib, tanpa binary git di kontainer.
"""
import base64
import json
import os
import re
import urllib.error
import urllib.request


RESULTS_REPO_URL = os.environ.get("RESULTS_REPO_URL", "").strip()
RESULTS_GIT_TOKEN = os.environ.get("RESULTS_GIT_TOKEN", "").strip()
RESULTS_BRANCH_PREFIX = os.environ.get("RESULTS_BRANCH_PREFIX", "results/job-").strip() or "results/job-"
GITHUB_API = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")

_REPO_RE = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")


class PublishError(Exception):
    pass


def parse_repo(url: str) -> tuple[str, str]:
    m = _REPO_RE.match(url or "")
    if not m:
        raise PublishError(f"URL repo GitHub tidak valid: {url!r}")
    return m.group(1), m.group(2)


def _api(method: str, path: str, body=None, token: str = ""):
    req = urllib.request.Request(
        GITHUB_API + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={**({"Authorization": f"Bearer {token}"} if token else {}),
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "hpc-coordinator",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or "null")
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read() or "null")
        except Exception:
            data = None
        return e.code, data


def _ok(status, data, what):
    if status >= 300:
        msg = (data or {}).get("message") if isinstance(data, dict) else None
        raise PublishError(f"{what} gagal (HTTP {status}): {msg or data}")
    return data


def commit_files(repo_url: str, branch: str, files: dict[str, bytes], message: str,
                 base_sha: str | None = None, token: str = "") -> str:
    """Buat satu commit berisi `files` di `branch` (dibuat bila belum ada). Mengembalikan SHA commit."""
    owner, repo = parse_repo(repo_url)
    r = f"/repos/{owner}/{repo}"
    # 1. Commit induk: SHA kode job (bila ada di repo ini), atau ujung branch hasil, atau branch default
    parent = None
    st, ref = _api("GET", f"{r}/git/ref/heads/{branch}", token=token)
    if st == 200:
        parent = ref["object"]["sha"]
    elif base_sha:
        st, data = _api("GET", f"{r}/git/commits/{base_sha}", token=token)
        if st == 200:
            parent = base_sha
    if parent is None:
        info = _ok(*_api("GET", r, token=token), "membaca info repo")
        head = _ok(*_api("GET", f"{r}/git/ref/heads/{info['default_branch']}", token=token), "membaca branch default")
        parent = head["object"]["sha"]
    base_tree = _ok(*_api("GET", f"{r}/git/commits/{parent}", token=token), "membaca commit induk")["tree"]["sha"]
    # 2. Blob + tree + commit
    tree = []
    for path, content in files.items():
        blob = _ok(*_api("POST", f"{r}/git/blobs", {"content": base64.b64encode(content).decode(),
                                                     "encoding": "base64"}, token), f"upload {path}")
        tree.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    new_tree = _ok(*_api("POST", f"{r}/git/trees", {"base_tree": base_tree, "tree": tree}, token), "membuat tree")
    commit = _ok(*_api("POST", f"{r}/git/commits", {"message": message, "tree": new_tree["sha"],
                                                   "parents": [parent]}, token), "membuat commit")
    # 3. Arahkan branch ke commit baru
    st, data = _api("POST", f"{r}/git/refs", {"ref": f"refs/heads/{branch}", "sha": commit["sha"]}, token)
    if st == 422:  # branch sudah ada -> maju (fast-forward, karena induknya ujung branch)
        _ok(*_api("PATCH", f"{r}/git/refs/heads/{branch}", {"sha": commit["sha"], "force": False}, token),
            "memperbarui branch")
    else:
        _ok(st, data, "membuat branch")
    return commit["sha"]


def _summary_md(job: dict, result: dict) -> str:
    lines = [f"# Hasil job #{job['id']} ({job['kind']})", "",
             f"- Status: **{job['status']}**",
             f"- Dibuat: {job['created_at']}", f"- Selesai: {job['finished_at']}",
             f"- Tahap: {job['n_stages']}",
             f"- Resource per tugas: `{json.dumps(job['resources'])}`"]
    if job.get("code"):
        lines.append(f"- Kode: {job['code']['repo_url']} @ `{job['code']['sha']}` (`{job['code']['entry']}`)")
    lines += ["", "Hasil divalidasi dengan replikasi tugas + quorum (hash SHA-256 hasil replika harus sama).",
              "", "```json", json.dumps({k: v for k, v in result.items() if k != "grid"}, indent=2, default=str),
              "```", ""]
    return "\n".join(lines)


def publish_job(c, job_id: int, log=print) -> str:
    """Publikasikan hasil job yang sudah selesai. Mengembalikan status singkat."""
    job = c.execute("""SELECT id, kind, status, spec, n_stages, code, resources, result,
                              created_at, finished_at FROM jobs WHERE id = %s""", (job_id,)).fetchone()
    if not job or job["status"] not in ("done", "failed"):
        return "not_finished"
    target = RESULTS_REPO_URL or (job["code"] or {}).get("repo_url", "")
    if job["kind"] == "ci" and not RESULTS_REPO_URL:
        # CI repo proyek: hasil sudah tampil sebagai status commit di GitHub + dashboard,
        # jangan membuat branch results/job-* di repo proyek untuk setiap push.
        target = ""
    if not RESULTS_GIT_TOKEN or not target:
        status = "skipped: RESULTS_GIT_TOKEN/RESULTS_REPO_URL belum diisi"
        c.execute("UPDATE jobs SET publish_status = %s WHERE id = %s", (status, job_id))
        return status
    branch = f"{RESULTS_BRANCH_PREFIX}{job_id}"
    result = job["result"] or {}
    files = {
        f"results/job-{job_id}/result.json": json.dumps(result, indent=1, default=str).encode(),
        f"results/job-{job_id}/README.md": _summary_md(job, result).encode(),
    }
    if job["kind"] == "heat2d" and result.get("grid"):
        from jobs import heatmap_png
        files[f"results/job-{job_id}/heatmap.png"] = heatmap_png(result["grid"])
    base = (job["code"] or {}).get("sha") if job["code"] and job["code"].get("repo_url") == target else None
    try:
        sha = commit_files(target, branch, files,
                           f"results: job {job_id} ({job['kind']}, {job['status']})", base, RESULTS_GIT_TOKEN)
        c.execute("""UPDATE jobs SET publish_status = 'published', result_branch = %s, result_commit = %s
                     WHERE id = %s""", (branch, sha, job_id))
        log(f"job {job_id}: hasil di-commit ke {target} branch {branch} ({sha[:10]})")
        return "published"
    except Exception as e:  # jangan hentikan validator karena GitHub bermasalah
        status = f"failed: {str(e)[:300]}"
        c.execute("UPDATE jobs SET publish_status = %s WHERE id = %s", (status, job_id))
        log(f"job {job_id}: publikasi gagal: {e}")
        return status


def publish_pending(c, log=print) -> None:
    """Coba publikasikan job yang selesai tapi belum pernah dicoba (mis. setelah validator restart)."""
    rows = c.execute("""SELECT id FROM jobs WHERE status IN ('done', 'failed') AND publish_status IS NULL
                        ORDER BY id LIMIT 5""").fetchall()
    for r in rows:
        publish_job(c, r["id"], log)

