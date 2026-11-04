import json, os, random, socket, threading, time, urllib.request, urllib.error

URL   = os.environ["COORDINATOR_URL"].rstrip("/")
TOKEN = os.environ["WORKER_TOKEN"]
NAME  = os.environ.get("WORKER_NAME", "worker") + "-" + socket.gethostname()[:4]  # beda per kontainer
CHEAT = os.environ.get("CHEAT") == "1"   # hanya untuk menguji validator

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
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read() or "null") if r.status != 204 else None

# --------------------------------------------------------------------------
# jenis tugas
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

KINDS = {"montecarlo_pi": montecarlo_pi, "mandelbrot": mandelbrot}

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
    # Jika WORKER_ID sudah tersedia dari env (diisi oleh worker_auth_cli.py),
    # gunakan langsung tanpa request ke /api/register.
    # Ini menghindari duplikasi entri di database untuk worker terverifikasi.
    if _ENV_WORKER_ID:
        print(f"[auth] Menggunakan WORKER_ID dari env: {_ENV_WORKER_ID}", flush=True)
        # Tetap panggil /api/register agar last_seen di-update dan server
        # mengkonfirmasi token masih valid.

    resp = call("/api/register", {"name": NAME})
    return resp["worker_id"]

def main():
    # Fase 1: register (dengan retry sampai koordinator siap)
    while True:
        try:
            wid = register()
            break
        except Exception as e:
            print("belum bisa daftar ke koordinator:", e, flush=True)
            time.sleep(5)
    print(f"terdaftar sebagai {NAME} ({wid})", flush=True)

    # Fase 2: loop utama — ambil tugas, kerjakan, kirim hasil
    while True:
        try:
            task = call("/api/tasks/claim", {"worker_id": wid})   # ambil tugas
            if task is None:
                time.sleep(5)
                continue

            stop = threading.Event()
            threading.Thread(
                target=heartbeat,
                args=(wid, task["assignment_id"], stop),
                daemon=True,
            ).start()

            t0     = time.time()
            result = KINDS[task["kind"]](task["payload"])           # kerjakan

            stop.set()

            # Mode cheat: untuk menguji validator (env CHEAT=1)
            if CHEAT:
                result = {k: v + random.randint(1, 1000) for k, v in result.items()}

            call("/api/tasks/submit", {                             # kirim hasil
                "worker_id":     wid,
                "assignment_id": task["assignment_id"],
                "result":        result,
            })
            print(f"tugas {task['task_id']} selesai dalam {time.time() - t0:.1f} s", flush=True)

        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print("ditolak koordinator:", e.code, body, flush=True)
            # Jika token dicabut / kadaluarsa, hentikan proses agar Docker dapat restart
            if e.code in (401, 403):
                print("[auth] Token tidak valid. Hentikan worker — jalankan ulang setelah login.", flush=True)
                raise SystemExit(1)
            time.sleep(2)

        except Exception as e:
            print("koneksi gagal, coba lagi:", e, flush=True)
            time.sleep(5)

if __name__ == "__main__":
    main()
