import glob, hashlib, json, os, random, re, resource, shlex, shutil, socket, subprocess, tempfile, threading, time
import urllib.request, urllib.error

URL   = os.environ["COORDINATOR_URL"].rstrip("/")
TOKEN = os.environ["WORKER_TOKEN"]
NAME  = os.environ.get("WORKER_NAME", "worker") + "-" + socket.gethostname()[:4]  # beda per kontainer
CHEAT = os.environ.get("CHEAT") == "1"   # hanya untuk menguji validator

# Kapasitas sandbox ini (harus sama dengan batas di compute/docker-compose.yml).
# Koordinator hanya memberi tugas yang spesifikasi resource job-nya muat di sini.
CAPACITY = {"cpus": float(os.environ.get("WORKER_CPUS", "1") or 1),
            "memory_mb": int(os.environ.get("WORKER_MEMORY_MB", "512") or 512)}

# Kode dari repo job: hanya URL dengan awalan ini yang mau di-clone worker,
# walaupun koordinator memintanya (lapisan pertahanan kedua).
ALLOWED_REPO_PREFIXES = [p.strip() for p in os.environ.get(
    "ALLOWED_REPO_PREFIXES", "https://github.com/").split(",") if p.strip()]
JOB_CACHE = os.environ.get("JOB_CACHE_DIR", "/tmp/jobs")

# ---------------------------------------------------------------------------
# WORKER_ID pra-terisi dari env (opsional)
# ---------------------------------------------------------------------------
# Jika worker sudah melalui proses autentikasi CLI (worker_auth_cli.py), nilai
# WORKER_ID di .env akan terisi otomatis sehingga worker tidak perlu
# melakukan /api/register ulang. Jika kosong, worker akan register normal.
_ENV_WORKER_ID = os.environ.get("WORKER_ID", "").strip()

def call(path, body=None, method="POST"):
    """Wrapper HTTP ke koordinator; selalu kirim Bearer token."""
    data = json.dumps(body).encode() if body is not None else None
    req  = urllib.request.Request(
        URL + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type":  "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or "null") if r.status != 204 else None

# --------------------------------------------------------------------------
# jenis tugas bawaan
# --------------------------------------------------------------------------
def montecarlo_pi(p):
    rng = random.Random(p["seed"])
    inside = 0
    for _ in range(p["samples"]):
        x, y = rng.random(), rng.random()
        if x * x + y * y <= 1.0:
            inside += 1
    return {"inside": inside}

def mandelbrot(p):
    w, h, m = p["width"], p["height"], p["max_iter"]
    inside = iter_sum = 0
    for row in range(p["row_start"], p["row_end"]):
        ci = -1.5 + 3.0 * row / h
        for col in range(w):
            cr = -2.0 + 3.0 * col / w
            zr = zi = 0.0
            n  = 0
            while n < m and zr * zr + zi * zi <= 4.0:
                zr, zi = zr * zr - zi * zi + cr, 2 * zr * zi + ci
                n += 1
            iter_sum += n
            inside   += n == m
    return {"inside": inside, "iter_sum": iter_sum}

def heat2d(p):
    """
    Satu tahap simulasi panas 2D untuk SATU blok baris (tugas berbutir halus).
    Payload berisi baris blok + halo (K baris dari blok tetangga, dikirim koordinator).
    Setelah K langkah, baris blok sendiri dikirim balik; koordinator menyusun grid dan
    meneruskan tepi baru ke tetangga pada tahap berikutnya (compute -> communicate -> compute).
    Rumus dan urutan operasi HARUS sama persis dengan head/coordinator/jobs.py agar hasil
    antar-replika identik bit-per-bit (dibandingkan lewat hash SHA-256).
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

KINDS = {"montecarlo_pi": montecarlo_pi, "mandelbrot": mandelbrot, "heat2d": heat2d}

# --------------------------------------------------------------------------
# kode dari repo job (dipatok ke commit SHA)
# --------------------------------------------------------------------------
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_clone_lock = threading.Lock()

def checkout(repo_url, sha):
    """
    Clone repo job ke cache lokal di dalam sandbox lalu checkout TEPAT pada commit `sha`.
    Bila commit tidak ada / HEAD tidak sama dengan sha, tugas ditolak.
    Cache per SHA: tugas berikutnya dari job yang sama tidak perlu clone ulang.
    """
    if not _SHA_RE.match(sha or ""):
        raise RuntimeError("SHA tidak valid")
    if not any(repo_url.startswith(p) for p in ALLOWED_REPO_PREFIXES):
        raise RuntimeError(f"repo {repo_url} tidak ada di ALLOWED_REPO_PREFIXES")
    dest = os.path.join(JOB_CACHE, hashlib.sha256(repo_url.encode()).hexdigest()[:12] + "-" + sha[:12])
    ok_marker = os.path.join(dest, ".hpc-verified")
    with _clone_lock:
        if os.path.exists(ok_marker):
            return dest
        shutil.rmtree(dest, ignore_errors=True)
        os.makedirs(dest, exist_ok=True)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": "/tmp",
               "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"}
        def git(*args):
            return subprocess.run(["git", "-c", "protocol.allow=never", "-c", "protocol.https.allow=always",
                                   *args], cwd=dest, env=env, check=True, timeout=120, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()
        try:
            git("init", "-q")
            git("remote", "add", "origin", repo_url)
            try:  # ambil commit itu saja (GitHub mengizinkan fetch per SHA)
                git("fetch", "-q", "--depth", "1", "origin", sha)
            except subprocess.CalledProcessError:
                git("fetch", "-q", "origin")
            git("-c", "advice.detachedHead=false", "checkout", "-q", sha)
            head = git("rev-parse", "HEAD")
            if head != sha:
                raise RuntimeError(f"HEAD {head} != SHA {sha}")
        except Exception as e:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"gagal mengambil {repo_url} @ {sha[:10]}: {e}")
        open(ok_marker, "w").close()  # .hpc-verified tidak ikut ter-commit (di luar index git)
        print(f"[repo] {repo_url} @ {sha[:10]} siap di {dest}", flush=True)
        return dest

def run_repo_task(task):
    """
    Jalankan program dari repo job: JSON {"kind", "payload"} lewat stdin,
    hasil berupa satu objek JSON di baris terakhir stdout. Batas waktu & memori
    mengikuti resources job (di dalam batas sandbox kontainer).
    """
    code, res = task["code"], task.get("resources") or {}
    workdir = checkout(code["repo_url"], code["sha"])
    timeout = int(res.get("timeout_s", 120))
    mem = int(res.get("memory_mb", 256)) * 1024 * 1024

    def limits():
        resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout + 5))
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        resource.setrlimit(resource.RLIMIT_FSIZE, (16 << 20, 16 << 20))

    p = subprocess.run(shlex.split(code["entry"]), cwd=workdir, preexec_fn=limits,
                       input=json.dumps({"kind": task["kind"], "payload": task["payload"]}),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout,
                       env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": "/tmp",
                            "PYTHONDONTWRITEBYTECODE": "1", "HPC_TASK_ID": str(task["task_id"])})
    if p.returncode != 0:
        raise RuntimeError(f"program job keluar dengan kode {p.returncode}: {p.stderr[-500:]}")
    lines = [l for l in p.stdout.strip().splitlines() if l.strip()]
    if not lines:
        raise RuntimeError("program job tidak mencetak hasil JSON")
    result = json.loads(lines[-1])
    if not isinstance(result, dict):
        raise RuntimeError("hasil program job harus objek JSON")
    return result

# --------------------------------------------------------------------------
# CI repo proyek (repo B): build lalu test per file, di dalam sandbox
# --------------------------------------------------------------------------
# Repo B wajib punya hpc.json di root, contoh:
#   {"build": "python3 -m compileall -q app",
#    "test": {"files": "tests/test_*.py", "command": "python3 -m unittest -v {file}"}}
# Hasil yang dikirim (dan di-hash untuk quorum) hanya data yang deterministik:
# lulus/gagal, kode keluar, jumlah test. Output lengkap dikirim terpisah sebagai log.
CI_MAX_SHARDS = 200
_SHARD_RE = re.compile(r"^[A-Za-z0-9_./-]{1,200}$")

def _ci_workspace(task):
    """Salinan bersih checkout per tugas, supaya file yang ditulis test tidak memengaruhi shard lain."""
    src = checkout(task["code"]["repo_url"], task["code"]["sha"])
    dst = tempfile.mkdtemp(prefix="ci-", dir=JOB_CACHE)
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git", ".hpc-verified"))
    return dst

def _ci_config(workdir):
    path = os.path.join(workdir, "hpc.json")
    if not os.path.isfile(path):
        return None, "hpc.json tidak ditemukan di root repo"
    try:
        cfg = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        return None, f"hpc.json tidak valid: {e}"
    test = cfg.get("test") if isinstance(cfg, dict) else None
    if not isinstance(test, dict) or not isinstance(test.get("files"), str) \
            or "{file}" not in str(test.get("command", "")):
        return None, 'hpc.json harus punya "test": {"files": "<pola glob>", "command": "... {file} ..."}'
    return cfg, None

def _sh(cmd, workdir, timeout):
    """Jalankan perintah dari hpc.json (sh -c) tanpa token worker di environment-nya."""
    def limits():
        resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout + 5))
        resource.setrlimit(resource.RLIMIT_FSIZE, (64 << 20, 64 << 20))
    p = subprocess.run(["sh", "-c", cmd], cwd=workdir, preexec_fn=limits, timeout=timeout,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
                       env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": workdir, "CI": "true",
                            "TMPDIR": workdir, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"})
    return p.returncode, p.stdout

def _test_counts(out):
    """Jumlah test & gagal dari ringkasan unittest / pytest / jest (bila ada)."""
    m = re.search(r"^Ran (\d+) tests? in", out, re.M)
    if m:  # unittest
        bad = re.search(r"^FAILED \(([^)]*)\)", out, re.M)
        n_bad = sum(int(x) for x in re.findall(r"(?:failures|errors)=(\d+)", bad.group(1))) if bad else 0
        return {"tests": int(m.group(1)), "failures": n_bad}
    m = re.search(r"^=+ (.*?) in [\d.]+s", out, re.M)
    if m:  # pytest
        nums = dict((k, int(v)) for v, k in re.findall(r"(\d+) (passed|failed|errors?)", m.group(1)))
        bad = nums.get("failed", 0) + nums.get("error", 0) + nums.get("errors", 0)
        return {"tests": nums.get("passed", 0) + bad, "failures": bad}
    m = re.search(r"^Tests:\s+(.*?)(\d+) total", out, re.M)
    if m:  # jest
        bad = re.search(r"(\d+) failed", m.group(1))
        return {"tests": int(m.group(2)), "failures": int(bad.group(1)) if bad else 0}
    return {"tests": None, "failures": None}

def ci_build(task):
    timeout = int((task.get("resources") or {}).get("timeout_s", 300))
    work = _ci_workspace(task)
    try:
        cfg, err = _ci_config(work)
        if err:
            return {"build_ok": False, "error": err, "shards": []}
        code, out = (0, "")
        if cfg.get("build"):
            code, out = _sh(str(cfg["build"]), work, timeout)
        files = sorted(os.path.relpath(f, work) for f in glob.glob(os.path.join(work, cfg["test"]["files"]),
                                                                    recursive=True) if os.path.isfile(f))
        shards = [f.replace(os.sep, "/") for f in files if _SHARD_RE.match(f) and ".." not in f][:CI_MAX_SHARDS]
        return {"build_ok": code == 0, "exit_code": code, "shards": shards if code == 0 else [],
                "test_command": cfg["test"]["command"], "_log": out[-4000:]}
    finally:
        shutil.rmtree(work, ignore_errors=True)

def ci_test(task):
    f = task["payload"]["file"]
    if not _SHARD_RE.match(f) or ".." in f:
        raise RuntimeError("nama file test tidak valid")
    timeout = int((task.get("resources") or {}).get("timeout_s", 300))
    work = _ci_workspace(task)
    try:
        cfg, err = _ci_config(work)
        if err:
            raise RuntimeError(err)
        out = ""
        if cfg.get("before_test"):  # mis. build ulang di node ini bila test butuh hasil build
            code, out = _sh(str(cfg["before_test"]), work, timeout)
            if code != 0:
                return {"file": f, "passed": False, "exit_code": code, "stage": "before_test",
                        "tests": None, "failures": None, "_log": out[-4000:]}
        code, out2 = _sh(cfg["test"]["command"].replace("{file}", shlex.quote(f)), work, timeout)
        return {"file": f, "passed": code == 0, "exit_code": code, **_test_counts(out2),
                "_log": (out + out2)[-4000:]}
    finally:
        shutil.rmtree(work, ignore_errors=True)

CI_KINDS = {"ci_build": ci_build, "ci_test": ci_test}

def execute(task):
    if task["kind"] in CI_KINDS:
        if not task.get("code"):
            raise RuntimeError("tugas CI tanpa repo/SHA")
        return CI_KINDS[task["kind"]](task)
    if task.get("code"):
        return run_repo_task(task)
    if task["kind"] not in KINDS:
        raise RuntimeError(f"jenis tugas '{task['kind']}' butuh kode dari repo job")
    return KINDS[task["kind"]](task["payload"])

# --------------------------------------------------------------------------
# heartbeat: perpanjang lease selama menghitung
# --------------------------------------------------------------------------
def heartbeat(wid, aid, stop):
    while not stop.wait(10):
        try:
            call("/api/heartbeat", {"worker_id": wid, "assignment_id": aid})
        except Exception as e:
            print("heartbeat gagal:", e, flush=True)

# --------------------------------------------------------------------------
# register: ambil worker_id dari koordinator
# --------------------------------------------------------------------------
def register() -> str:
    """
    Mendaftarkan worker ke koordinator dan mengembalikan worker_id.

    Jika WORKER_TOKEN adalah token individual hasil autentikasi CLI
    (format: hpc_w_<hex>), koordinator mengenali worker dari token tersebut
    dan menggunakan worker_id yang sudah ada di database.

    Jika WORKER_TOKEN adalah token global dari .env, koordinator akan membuat
    entri worker baru setiap kali kontainer naik (perilaku lama / backward-compat).
    """
    if _ENV_WORKER_ID:
        print(f"[auth] Menggunakan WORKER_ID dari env: {_ENV_WORKER_ID}", flush=True)
        # Tetap panggil /api/register agar last_seen di-update dan server
        # mengkonfirmasi token masih valid.

    resp = call("/api/register", {"name": NAME, "capacity": CAPACITY})
    return resp["worker_id"]

def harden():
    """
    Tandai proses worker 'non-dumpable': program dari repo yang dijalankan worker (test,
    build) tidak bisa membaca /proc/<pid>/environ atau memori proses ini, jadi
    WORKER_TOKEN tidak bocor walau berjalan dengan user yang sama.
    """
    try:
        import ctypes
        ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0)   # PR_SET_DUMPABLE = 4
    except Exception as e:
        print("peringatan: prctl gagal:", e, flush=True)

def main():
    harden()
    os.makedirs(JOB_CACHE, exist_ok=True)
    # Fase 1: register (dengan retry sampai koordinator siap)
    while True:
        try:
            wid = register()
            break
        except Exception as e:
            print("belum bisa daftar ke koordinator:", e, flush=True)
            time.sleep(5)
    print(f"terdaftar sebagai {NAME} ({wid}), kapasitas {CAPACITY}", flush=True)

    # Fase 2: loop utama — ambil tugas, kerjakan, kirim hasil
    idle = 0.5
    while True:
        try:
            task = call("/api/tasks/claim", {"worker_id": wid, "capacity": CAPACITY})   # ambil tugas
            if task is None:
                # tidak ada tugas: tunggu sebentar (naik bertahap 0.5 s -> 5 s).
                # Pada job multi-tahap, tahap berikutnya muncul ~1 s setelah tahap ini tervalidasi.
                time.sleep(idle)
                idle = min(idle * 2, 5)
                continue
            idle = 0.5

            stop = threading.Event()
            threading.Thread(
                target=heartbeat,
                args=(wid, task["assignment_id"], stop),
                daemon=True,
            ).start()

            t0 = time.time()
            try:
                result = execute(task)                               # kerjakan
            except Exception as e:
                stop.set()
                print(f"tugas {task['task_id']} gagal dijalankan: {e}", flush=True)
                try:  # lapor agar tugas segera kembali ke antrean
                    call("/api/tasks/fail", {"worker_id": wid, "assignment_id": task["assignment_id"],
                                             "error": str(e)[:1000]})
                except Exception:
                    pass
                time.sleep(2)
                continue
            stop.set()
            log = result.pop("_log", None)   # output build/test: disimpan, tidak ikut di-hash

            # Mode cheat: untuk menguji validator (env CHEAT=1)
            if CHEAT:
                result = {"cheat": random.randint(1, 10**9), **{k: v for k, v in result.items() if k != "rows"}}

            call("/api/tasks/submit", {                             # kirim hasil
                "worker_id":     wid,
                "assignment_id": task["assignment_id"],
                "result":        result,
                "log":           log,
            })
            stage = f" tahap {task['stage'] + 1}/{task['n_stages']}" if task.get("n_stages", 1) > 1 else ""
            print(f"tugas {task['task_id']} ({task['kind']}{stage}) selesai dalam {time.time() - t0:.2f} s",
                  flush=True)

        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print("ditolak koordinator:", e.code, body, flush=True)
            # Jika token dicabut / kadaluarsa, hentikan proses agar Docker dapat restart
            if e.code in (401, 403):
                print("[auth] Token ditolak. Lihat / buat token di dashboard relawan (kartu 'Token Worker "
                      "untuk CLI'), lalu jalankan './hpc.sh setup' dan './hpc.sh up' lagi.", flush=True)
                raise SystemExit(1)
            time.sleep(2)

        except Exception as e:
            print("tugas gagal / koneksi gagal, coba lagi:", e, flush=True)
            time.sleep(3)

if __name__ == "__main__":
    main()
