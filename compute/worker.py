import json, os, random, socket, threading, time, urllib.request, urllib.error

URL = os.environ["COORDINATOR_URL"].rstrip("/")
TOKEN = os.environ["WORKER_TOKEN"]
NAME = os.environ.get("WORKER_NAME", "worker") + "-" + socket.gethostname()[:4]  # beda per kontainer
CHEAT = os.environ.get("CHEAT") == "1"   # hanya untuk menguji validator

def call(path, body):
    req = urllib.request.Request(URL + path, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read() or "null") if r.status != 204 else None

# ---------- jenis tugas ----------
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
            n = 0
            while n < m and zr * zr + zi * zi <= 4.0:
                zr, zi = zr * zr - zi * zi + cr, 2 * zr * zi + ci
                n += 1
            iter_sum += n
            inside += n == m
    return {"inside": inside, "iter_sum": iter_sum}

KINDS = {"montecarlo_pi": montecarlo_pi, "mandelbrot": mandelbrot}

# ---------- heartbeat: perpanjang lease selama menghitung ----------
def heartbeat(wid, aid, stop):
    while not stop.wait(10):
        try:
            call("/api/heartbeat", {"worker_id": wid, "assignment_id": aid})
        except Exception as e:
            print("heartbeat gagal:", e, flush=True)

def main():
    while True:
        try:
            wid = call("/api/register", {"name": NAME})["worker_id"]
            break
        except Exception as e:
            print("belum bisa daftar ke koordinator:", e, flush=True)
            time.sleep(5)
    print(f"terdaftar sebagai {NAME} ({wid})", flush=True)

    while True:
        try:
            task = call("/api/tasks/claim", {"worker_id": wid})          # komunikasi
            if task is None:
                time.sleep(5)
                continue
            stop = threading.Event()
            threading.Thread(target=heartbeat, args=(wid, task["assignment_id"], stop), daemon=True).start()
            t0 = time.time()
            result = KINDS[task["kind"]](task["payload"])                # komputasi
            stop.set()
            if CHEAT:
                result = {k: v + random.randint(1, 1000) for k, v in result.items()}
            call("/api/tasks/submit", {"worker_id": wid,                 # komunikasi
                 "assignment_id": task["assignment_id"], "result": result})
            print(f"tugas {task['task_id']} selesai dalam {time.time() - t0:.1f} s", flush=True)
        except urllib.error.HTTPError as e:
            print("ditolak koordinator:", e.code, e.read().decode(), flush=True)
            time.sleep(2)
        except Exception as e:
            print("koneksi gagal, coba lagi:", e, flush=True)
            time.sleep(5)

if __name__ == "__main__":
    main()