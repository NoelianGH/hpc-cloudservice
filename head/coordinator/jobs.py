"""
Logika job di sisi head node (dipakai app.py dan validator.py).

Jenis job:
  montecarlo_pi  bag-of-tasks, 1 tahap (seperti sebelumnya)
  mandelbrot     bag-of-tasks, 1 tahap (strip horizontal)
  heat2d         MULTI-TAHAP: simulasi panas 2D (persamaan difusi, skema eksplisit).
                 Grid N x N dibagi menjadi B blok baris. Satu tahap = 1 tugas per blok,
                 masing-masing menghitung K langkah waktu. Setelah semua blok satu tahap
                 tervalidasi, koordinator menyusun grid, mengirim baris tepi (halo, K baris)
                 dari blok tetangga ke tugas tahap berikutnya.
                 Siklus: compute (worker) -> communicate (lewat koordinator) -> compute.
  repo           kode dari REPO JOB yang dipatok ke satu commit SHA; bag-of-tasks.
  ci             MULTI-TAHAP: build + test terdistribusi untuk SATU commit SHA di repo
                 proyek (repo B) yang dikerjakan relawan (lihat project.py).
                 Tahap 0 (compute)  : 1 tugas ci_build -> build + daftar file test (shard).
                 communicate        : koordinator membuat 1 tugas ci_test per shard.
                 Tahap 1 (compute)  : tugas ci_test paralel di banyak node.
                 communicate        : koordinator menggabungkan laporan lulus/gagal per branch.

Semua jenis bisa memakai kode dari repo job (field "code"), sehingga yang dijalankan
worker selalu bisa diaudit: repo + SHA yang sama = kode yang sama.
"""
import hashlib
import json
import os
import re
import struct
import zlib

from psycopg.types.json import Jsonb

SHA_RE = re.compile(r"^[0-9a-f]{40}$")

# Repo job bawaan (boleh kosong; diisi setelah repo job diberikan)
JOB_REPO_URL = os.environ.get("JOB_REPO_URL", "").strip()
JOB_REPO_ENTRY = os.environ.get("JOB_REPO_ENTRY", "python3 run.py").strip()
# Hanya repo dengan awalan ini yang boleh dipakai job (cegah file://, ssh://, host lain)
JOB_REPO_ALLOWLIST = [p.strip() for p in os.environ.get(
    "JOB_REPO_ALLOWLIST", "https://github.com/").split(",") if p.strip()]

DEFAULT_RESOURCES = {"cpus": 1, "memory_mb": 256, "timeout_s": 120}
MAX_RESOURCES = {"cpus": 4, "memory_mb": 4096, "timeout_s": 3600}

HEAT_DEFAULTS = {"n": 160, "blocks": 8, "stages": 10, "steps": 20, "alpha": 0.2,
                 "t_hot": 100.0, "t_cold": 0.0, "verify_serial": False}


class JobError(ValueError):
    pass


def canonical_hash(obj) -> str:
    """SHA-256 dari JSON kanonik (kunci urut, tanpa spasi). Dipakai untuk membandingkan replika."""
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# =============================================================================
# Validasi spesifikasi job
# =============================================================================

def parse_resources(r: dict | None) -> dict:
    out = dict(DEFAULT_RESOURCES)
    for k, v in (r or {}).items():
        if k not in out or v is None:
            continue
        try:
            v = float(v) if k == "cpus" else int(v)
        except (TypeError, ValueError):
            raise JobError(f"resources.{k} harus angka")
        if not 0 < v <= MAX_RESOURCES[k]:
            raise JobError(f"resources.{k} harus > 0 dan <= {MAX_RESOURCES[k]}")
        out[k] = v
    return out


def parse_code(code: dict | None, required: bool) -> dict | None:
    """Kode dari repo job: wajib commit SHA lengkap (40 hex), bukan nama branch."""
    if not code:
        if required:
            raise JobError("Job 'repo' butuh code.repo_url dan code.sha")
        return None
    repo = (code.get("repo_url") or JOB_REPO_URL).strip()
    sha = (code.get("sha") or "").strip().lower()
    entry = (code.get("entry") or JOB_REPO_ENTRY).strip()
    if not repo:
        raise JobError("code.repo_url kosong dan JOB_REPO_URL belum diisi di .env")
    if not any(repo.startswith(p) for p in JOB_REPO_ALLOWLIST):
        raise JobError(f"Repo tidak diizinkan. Awalan yang diizinkan: {', '.join(JOB_REPO_ALLOWLIST)}")
    if not re.fullmatch(r"https://[A-Za-z0-9._/-]+?(\.git)?", repo) or ".." in repo:
        raise JobError("code.repo_url harus URL https tanpa karakter khusus")
    if not SHA_RE.match(sha):
        raise JobError("code.sha harus commit SHA lengkap 40 karakter hex (bukan nama branch)")
    if not entry or len(entry) > 200 or any(ch in entry for ch in ";&|`$<>\n"):
        raise JobError("code.entry tidak valid (contoh: 'python3 run.py')")
    return {"repo_url": repo, "sha": sha, "entry": entry}


def _int(spec, key, lo, hi, default):
    v = spec.get(key, default)
    try:
        v = int(v)
    except (TypeError, ValueError):
        raise JobError(f"{key} harus bilangan bulat")
    if not lo <= v <= hi:
        raise JobError(f"{key} harus {lo}-{hi}")
    return v


# =============================================================================
# heat2d: kernel, inisialisasi, pembagian blok + halo, penyusunan grid
# =============================================================================

def heat_initial(n: int, t_hot: float, t_cold: float) -> list[list[float]]:
    """Kondisi awal: tepi atas panas (tetap), sisanya dingin, plus satu titik panas di tengah."""
    g = [[t_cold] * n for _ in range(n)]
    g[0] = [t_hot] * n
    c, r = n // 2, max(1, n // 12)
    for i in range(c - r, c + r):
        for j in range(c - r, c + r):
            g[i][j] = t_hot
    return g


def heat_step_block(p: dict) -> dict:
    """
    Kernel yang SAMA PERSIS dengan worker (compute/worker.py dan job-template/run.py).
    Input: baris blok + halo (ext_start..ext_end). Output: baris blok sendiri setelah K langkah.
    Baris halo terluar tidak diperbarui; setelah K langkah baris blok tetap tepat karena
    halo setebal K baris.
    """
    n, alpha, steps = p["n"], p["alpha"], p["steps"]
    rows = [list(r) for r in p["rows"]]
    m = len(rows)
    for _ in range(steps):
        new = [r[:] for r in rows]
        for li in range(1, m - 1):
            up, cur, dn, nr = rows[li - 1], rows[li], rows[li + 1], new[li]
            for j in range(1, n - 1):
                c = cur[j]
                nr[j] = c + alpha * (up[j] + dn[j] + cur[j - 1] + cur[j + 1] - 4.0 * c)
        rows = new
    a = p["row_start"] - p["ext_start"]
    b = p["row_end"] - p["ext_start"]
    return {"rows": rows[a:b]}


def heat_serial(spec: dict) -> list[list[float]]:
    """Referensi serial (1 proses) untuk membuktikan hasil terdistribusi identik."""
    n = spec["n"]
    g = heat_initial(n, spec["t_hot"], spec["t_cold"])
    p = {"n": n, "alpha": spec["alpha"], "steps": spec["steps"] * spec["stages"],
         "rows": g, "row_start": 0, "row_end": n, "ext_start": 0}
    return heat_step_block(p)["rows"]


def heat_block_bounds(n: int, blocks: int, b: int) -> tuple[int, int]:
    return b * n // blocks, (b + 1) * n // blocks


def heat_payloads(spec: dict, grid: list[list[float]], stage: int) -> list[dict]:
    """Potong grid menjadi payload per blok, masing-masing dengan halo K baris dari tetangga."""
    n, blocks, k = spec["n"], spec["blocks"], spec["steps"]
    out = []
    for b in range(blocks):
        r0, r1 = heat_block_bounds(n, blocks, b)
        e0, e1 = max(0, r0 - k), min(n, r1 + k)
        out.append({"n": n, "alpha": spec["alpha"], "steps": k, "stage": stage, "block": b,
                    "row_start": r0, "row_end": r1, "ext_start": e0, "ext_end": e1,
                    "rows": grid[e0:e1]})
    return out


def heat_assemble(block_results: list[dict]) -> list[list[float]]:
    grid = []
    for r in block_results:
        grid.extend(r["rows"])
    return grid


def heat_summary(grid: list[list[float]]) -> dict:
    flat = [v for row in grid for v in row]
    return {"mean": sum(flat) / len(flat), "max": max(flat), "min": min(flat),
            "grid_sha256": canonical_hash(grid)}


# =============================================================================
# Pembuatan job dan tugas
# =============================================================================

def _insert_tasks(c, job_id: int, kind: str, payloads: list[dict], replicas: int,
                  stage: int, credit: int) -> None:
    for i, p in enumerate(payloads):
        c.execute("""INSERT INTO tasks (job_id, kind, payload, replicas, stage, block, credit)
                     VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                  (job_id, kind, Jsonb(p), replicas, stage, p.get("block", i), credit))


def create_job(c, body: dict) -> dict:
    """Validasi lalu buat job + tugas tahap pertama. Dipanggil di dalam transaksi."""
    kind = body.get("kind", "montecarlo_pi")
    if kind not in ("montecarlo_pi", "mandelbrot", "heat2d", "repo", "ci"):
        raise JobError("kind tidak dikenal (montecarlo_pi | mandelbrot | heat2d | repo | ci)")
    replicas = _int(body, "replicas", 1, 4, 2)
    resources = parse_resources(body.get("resources"))
    code = parse_code(body.get("code"), required=(kind in ("repo", "ci")))
    task_kind = kind
    size = body.get("size")

    if kind == "heat2d":
        spec = dict(HEAT_DEFAULTS)
        spec.update({k: v for k, v in (body.get("params") or {}).items() if k in HEAT_DEFAULTS})
        spec["n"] = _int(spec, "n", 8, 1024, 160)
        spec["blocks"] = _int(spec, "blocks", 1, 128, 8)
        if body.get("n_tasks"):  # n_tasks pada heat2d = jumlah blok
            spec["blocks"] = _int(body, "n_tasks", 1, 128, 8)
        spec["stages"] = _int(spec, "stages", 1, 200, 10)
        spec["steps"] = _int(spec, "steps", 1, 500, 20)
        spec["alpha"] = float(spec["alpha"])
        if not 0 < spec["alpha"] <= 0.25:
            raise JobError("alpha harus 0 < alpha <= 0.25 (syarat stabil skema eksplisit 2D)")
        if spec["n"] // spec["blocks"] < 1:
            raise JobError("blocks terlalu banyak untuk ukuran grid")
        spec["t_hot"], spec["t_cold"] = float(spec["t_hot"]), float(spec["t_cold"])
        spec["verify_serial"] = bool(spec["verify_serial"])
        n_stages = spec["stages"]
        payloads = heat_payloads(spec, heat_initial(spec["n"], spec["t_hot"], spec["t_cold"]), 0)
    elif kind == "ci":
        params = body.get("params") or {}
        spec = {"repo_url": code["repo_url"], "sha": code["sha"],
                "branch": str(params.get("branch") or "")[:100],
                "jobdesk_id": params.get("jobdesk_id"), "source": str(params.get("source") or "manual")[:20]}
        n_stages = 2
        task_kind = "ci_build"
        payloads = [{"step": "build"}]
    elif kind == "repo":
        n_tasks = _int(body, "n_tasks", 1, 1000, 10)
        params = body.get("params") or {}
        if not isinstance(params, dict) or len(json.dumps(params)) > 20_000:
            raise JobError("params harus objek JSON (maks 20 KB)")
        repo_kind = str(body.get("task_kind") or params.get("task_kind") or "default")[:50]
        spec = {"n_tasks": n_tasks, "task_kind": repo_kind, "params": params}
        n_stages = 1
        payloads = [{"task_kind": repo_kind, "task_index": i, "n_tasks": n_tasks, **params}
                    for i in range(n_tasks)]
    else:
        n_tasks = _int(body, "n_tasks", 1, 1000, 20)
        limit = 1_000_000_000 if kind == "montecarlo_pi" else 10_000
        if size is not None and not 1 <= int(size) <= limit:
            raise JobError("size di luar batas")
        if size is None:  # bawaan: kira-kira 5-15 detik per tugas di laptop biasa
            size = 30_000_000 if kind == "montecarlo_pi" else 2000
        size = int(size)
        spec = {"n_tasks": n_tasks, "size": size}
        n_stages = 1
        payloads = []  # seed butuh job_id -> diisi setelah INSERT

    credit = _int(body, "credit_per_task", 1, 100, 1)
    job = c.execute("""INSERT INTO jobs (kind, status, spec, n_stages, current_stage, code, resources)
                       VALUES (%s, 'running', %s, %s, 0, %s, %s) RETURNING id""",
                    (kind, Jsonb(spec), n_stages, Jsonb(code) if code else None,
                     Jsonb(resources))).fetchone()
    jid = job["id"]
    if kind == "montecarlo_pi":
        payloads = [{"seed": jid * 100000 + i, "samples": size} for i in range(n_tasks)]
    elif kind == "mandelbrot":  # gambar dibagi jadi n_tasks strip horizontal
        payloads = [{"width": size, "height": size, "row_start": i * size // n_tasks,
                     "row_end": (i + 1) * size // n_tasks, "max_iter": 500} for i in range(n_tasks)]
    _insert_tasks(c, jid, task_kind, payloads, replicas, 0, credit)
    return {"job_id": jid, "kind": kind, "tasks": len(payloads), "stages": n_stages,
            "replicas": replicas, "resources": resources, "code": code}


# =============================================================================
# Kemajuan job (dipanggil validator setiap putaran)
# =============================================================================

def advance_jobs(c, log=print) -> list[int]:
    """
    Untuk setiap job yang masih berjalan:
      - ada tugas tahap ini yang invalid -> job gagal;
      - semua tugas tahap ini 'done' -> buat tahap berikutnya (heat2d) atau selesaikan job.
    Mengembalikan daftar job_id yang baru selesai (untuk dipublikasikan).
    """
    finished = []
    jobs = c.execute("""
        SELECT j.id, j.kind, j.spec, j.n_stages, j.current_stage,
               count(t.id) AS total,
               count(t.id) FILTER (WHERE t.status = 'done') AS done,
               count(t.id) FILTER (WHERE t.status = 'invalid') AS invalid
        FROM jobs j JOIN tasks t ON t.job_id = j.id AND t.stage = j.current_stage
        WHERE j.status = 'running'
        GROUP BY j.id""").fetchall()
    for j in jobs:
        if j["invalid"] and j["kind"] == "heat2d":
            with c.transaction():
                c.execute("""UPDATE jobs SET status = 'failed', finished_at = now(),
                             result = %s WHERE id = %s AND status = 'running'""",
                          (Jsonb({"error": f"{j['invalid']} tugas tahap {j['current_stage']} invalid"}), j["id"]))
                # tugas sisa tahap ini tidak perlu dikerjakan lagi
                c.execute("UPDATE tasks SET status = 'cancelled' WHERE job_id = %s AND status = 'pending'",
                          (j["id"],))
            log(f"job {j['id']} gagal: ada tugas invalid di tahap {j['current_stage']}")
            finished.append(j["id"])
            continue
        if j["done"] + j["invalid"] < j["total"]:
            continue
        with c.transaction():
            # kunci baris job agar tahap tidak dibuat dua kali bila ada 2 validator
            locked = c.execute("SELECT id FROM jobs WHERE id = %s AND status = 'running' "
                               "AND current_stage = %s FOR UPDATE SKIP LOCKED",
                               (j["id"], j["current_stage"])).fetchone()
            if not locked:
                continue
            if j["kind"] == "heat2d":
                done = _advance_heat(c, j, log)
            elif j["kind"] == "ci":
                done = _advance_ci(c, j, log)
            else:
                done = _finish_bag(c, j)
            if done:
                finished.append(j["id"])
    return finished


def _stage_results(c, job_id: int, stage: int) -> list[dict]:
    rows = c.execute("SELECT result FROM tasks WHERE job_id = %s AND stage = %s ORDER BY block, id",
                     (job_id, stage)).fetchall()
    return [r["result"] for r in rows]


def _advance_heat(c, j, log) -> bool:
    spec, s = j["spec"], j["current_stage"]
    grid = heat_assemble(_stage_results(c, j["id"], s))
    if s + 1 < j["n_stages"]:
        # communicate: halo dari blok tetangga dikirim lewat payload tahap berikutnya
        replicas = c.execute("SELECT min(replicas) AS r, min(credit) AS cr FROM tasks "
                             "WHERE job_id = %s AND stage = 0", (j["id"],)).fetchone()
        _insert_tasks(c, j["id"], "heat2d", heat_payloads(spec, grid, s + 1),
                      replicas["r"] or 2, s + 1, replicas["cr"] or 1)
        c.execute("UPDATE jobs SET current_stage = %s WHERE id = %s", (s + 1, j["id"]))
        log(f"job {j['id']} heat2d: tahap {s} selesai -> tahap {s + 1}/{j['n_stages'] - 1} dibuat")
        return False
    result = {"n": spec["n"], "blocks": spec["blocks"], "stages": j["n_stages"],
              "steps_per_stage": spec["steps"], "total_steps": spec["steps"] * j["n_stages"],
              **heat_summary(grid)}
    if spec.get("verify_serial"):
        result["serial_match"] = canonical_hash(heat_serial(spec)) == result["grid_sha256"]
    result["grid"] = grid
    c.execute("UPDATE jobs SET status = 'done', finished_at = now(), result = %s WHERE id = %s",
              (Jsonb(result), j["id"]))
    log(f"job {j['id']} heat2d selesai ({j['n_stages']} tahap), mean={result['mean']:.4f}"
        + (f", sama dengan serial: {result['serial_match']}" if "serial_match" in result else ""))
    return True


CI_MAX_SHARDS = int(os.environ.get("CI_MAX_SHARDS", "200") or 200)
_SHARD_RE = re.compile(r"^[A-Za-z0-9_./-]{1,200}$")


def _advance_ci(c, j, log) -> bool:
    """
    Tahap 0 selesai -> communicate: daftar shard hasil build (sudah divalidasi quorum)
    diubah jadi tugas ci_test, satu per file test. Tahap 1 selesai -> laporan gabungan.
    """
    spec, s = j["spec"], j["current_stage"]
    if s == 0:
        t = c.execute("SELECT status, result, replicas, credit FROM tasks WHERE job_id = %s AND stage = 0",
                      (j["id"],)).fetchone()
        if t["status"] != "done":
            return _finish_ci(c, j, "error", {"error": "build tidak bisa dijalankan (gagal di beberapa node)"}, log)
        build = t["result"] or {}
        if not build.get("build_ok"):
            return _finish_ci(c, j, "failed", {"build": build}, log)
        shards = [f for f in (build.get("shards") or []) if isinstance(f, str) and _SHARD_RE.match(f)
                  and ".." not in f][:CI_MAX_SHARDS]
        if not shards:
            return _finish_ci(c, j, "passed", {"build": build, "note": "tidak ada file test"}, log)
        _insert_tasks(c, j["id"], "ci_test", [{"step": "test", "file": f, "block": i} for i, f in enumerate(shards)],
                      t["replicas"], 1, t["credit"])
        c.execute("UPDATE jobs SET current_stage = 1 WHERE id = %s", (j["id"],))
        log(f"job {j['id']} ci {spec.get('branch')}@{spec['sha'][:7]}: build lulus -> {len(shards)} shard test dibuat")
        return False
    build = c.execute("SELECT result FROM tasks WHERE job_id = %s AND stage = 0", (j["id"],)).fetchone()["result"]
    rows = c.execute("SELECT status, payload, result FROM tasks WHERE job_id = %s AND stage = 1 ORDER BY block",
                     (j["id"],)).fetchall()
    shards = []
    for r in rows:
        res = r["result"] or {}
        st = "error" if r["status"] != "done" else ("passed" if res.get("passed") else "failed")
        shards.append({"file": r["payload"]["file"], "status": st, "tests": res.get("tests"),
                       "failures": res.get("failures"), "exit_code": res.get("exit_code")})
    if any(x["status"] == "error" for x in shards):
        verdict = "error"
    else:
        verdict = "passed" if all(x["status"] == "passed" for x in shards) else "failed"
    return _finish_ci(c, j, verdict, {"build": build, "shards": shards}, log)


def _finish_ci(c, j, verdict: str, extra: dict, log) -> bool:
    spec = j["spec"]
    m = c.execute("""
        SELECT count(DISTINCT a.worker_id) AS nodes,
               EXTRACT(EPOCH FROM (max(a.finished_at) - min(a.started_at))) AS wall_s
        FROM jobs j JOIN tasks t ON t.job_id = j.id
        JOIN assignments a ON a.task_id = t.id AND a.status = 'submitted'
        WHERE j.id = %s""", (j["id"],)).fetchone()
    # Waktu komputasi bila dikerjakan 1 node saja: jumlah durasi satu replika per tugas
    cpu = c.execute("""
        SELECT coalesce(sum(d), 0) AS s FROM (
            SELECT min(EXTRACT(EPOCH FROM (a.finished_at - a.started_at))) AS d
            FROM tasks t JOIN assignments a ON a.task_id = t.id AND a.status = 'submitted'
            WHERE t.job_id = %s GROUP BY t.id) x""", (j["id"],)).fetchone()["s"]
    shards = extra.get("shards") or []
    result = {"ci_status": verdict, "branch": spec.get("branch"), "sha": spec["sha"],
              "repo_url": spec.get("repo_url"), "jobdesk_id": spec.get("jobdesk_id"),
              "tests_total": sum(x["tests"] or 0 for x in shards),
              "tests_failed": sum(x["failures"] or 0 for x in shards),
              "shards_total": len(shards),
              "shards_failed": [x["file"] for x in shards if x["status"] != "passed"],
              "nodes": m["nodes"] or 0, "wall_s": round(float(m["wall_s"] or 0), 2),
              "compute_s": round(float(cpu or 0), 2), **extra}
    result["speedup_est"] = round(result["compute_s"] / result["wall_s"], 2) if result["wall_s"] else None
    status = "failed" if verdict == "error" else "done"
    c.execute("UPDATE jobs SET status = %s, finished_at = now(), result = %s WHERE id = %s",
              (status, Jsonb(result), j["id"]))
    c.execute("UPDATE tasks SET status = 'cancelled' WHERE job_id = %s AND status = 'pending'", (j["id"],))
    log(f"job {j['id']} ci {spec.get('branch')}@{spec['sha'][:7]}: {verdict.upper()} "
        f"({result['shards_total']} shard, {result['nodes']} node, {result['wall_s']} s)")
    return True


def _finish_bag(c, j) -> bool:
    rows = c.execute("SELECT payload, result FROM tasks WHERE job_id = %s AND status = 'done' ORDER BY id",
                     (j["id"],)).fetchall()
    result: dict = {"tasks": j["total"], "tasks_done": len(rows), "tasks_invalid": j["invalid"]}
    if j["kind"] == "montecarlo_pi":
        inside = sum(int(r["result"].get("inside", 0)) for r in rows)
        samples = sum(int(r["payload"].get("samples", 0)) for r in rows)
        result.update({"inside": inside, "samples": samples, "pi": 4 * inside / samples if samples else None})
    elif j["kind"] == "mandelbrot":
        result.update({"inside": sum(int(r["result"].get("inside", 0)) for r in rows),
                       "iter_sum": sum(int(r["result"].get("iter_sum", 0)) for r in rows)})
    else:
        result["results"] = [r["result"] for r in rows]
    result["results_sha256"] = canonical_hash([r["result"] for r in rows])
    status = "done" if rows else "failed"  # semua tugas invalid -> job gagal
    c.execute("UPDATE jobs SET status = %s, finished_at = now(), result = %s WHERE id = %s",
              (status, Jsonb(result), j["id"]))
    return True


# =============================================================================
# Heatmap PNG (tanpa library tambahan)
# =============================================================================

def _png(width: int, height: int, rgb_rows: list[bytes]) -> bytes:
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + r for r in rgb_rows)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def heatmap_png(grid: list[list[float]], scale: int = 3) -> bytes:
    lo = min(min(r) for r in grid)
    hi = max(max(r) for r in grid)
    span = (hi - lo) or 1.0

    def color(v):  # biru -> merah -> kuning
        t = (v - lo) / span
        if t < 0.5:
            u = t / 0.5
            return int(30 + 200 * u), int(40 * (1 - u)), int(120 * (1 - u) + 30)
        u = (t - 0.5) / 0.5
        return 230 + int(25 * u), int(220 * u), int(40 * u)

    rows = []
    for r in grid:
        line = b"".join(bytes(color(v)) * scale for v in r)
        rows.extend([line] * scale)
    return _png(len(grid[0]) * scale, len(grid) * scale, rows)
