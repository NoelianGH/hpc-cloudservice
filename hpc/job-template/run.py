"""
Contoh isi REPO JOB untuk Cloud Service HPC.

Kontrak dengan worker:
  - Worker meng-clone repo ini di dalam sandbox pada commit SHA yang ditulis di job,
    lalu menjalankan perintah `entry` (bawaan: python3 run.py) dari root repo.
  - stdin : satu objek JSON {"kind": "<jenis tugas>", "payload": {...}}
  - stdout: baris TERAKHIR berisi satu objek JSON hasil tugas.
  - Hasil harus DETERMINISTIK (input sama -> output sama persis), karena koordinator
    membandingkan hash SHA-256 hasil dari 2+ worker (replikasi + quorum).
  - Hanya pustaka standar Python; tanpa akses jaringan, tanpa menulis di luar /tmp.

Uji lokal:
  echo '{"kind":"montecarlo_pi","payload":{"seed":1,"samples":100000}}' | python3 run.py
"""
import json
import random
import sys


def montecarlo_pi(p):
    rng = random.Random(p["seed"])
    inside = 0
    for _ in range(p["samples"]):
        x, y = rng.random(), rng.random()
        if x * x + y * y <= 1.0:
            inside += 1
    return {"inside": inside}


def heat2d(p):
    """Satu tahap simulasi panas 2D untuk satu blok baris (rumus sama dengan worker bawaan)."""
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


def prime_count(p):
    """Contoh job 'repo' bag-of-tasks: hitung bilangan prima di rentang milik tugas ini."""
    lo = p["task_index"] * p.get("chunk", 200_000)
    hi = lo + p.get("chunk", 200_000)
    count = 0
    for k in range(max(lo, 2), hi):
        if all(k % d for d in range(2, int(k ** 0.5) + 1)):
            count += 1
    return {"lo": lo, "hi": hi, "primes": count}


KINDS = {"montecarlo_pi": montecarlo_pi, "heat2d": heat2d, "prime_count": prime_count}


def main():
    req = json.load(sys.stdin)
    kind = req["kind"]
    payload = req["payload"]
    if kind == "repo":  # job 'repo': jenis sebenarnya ada di payload.task_kind
        kind = payload.get("task_kind", "")
    if kind not in KINDS:
        print(f"jenis tugas tidak dikenal: {kind}", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(KINDS[kind](payload), separators=(",", ":")))


if __name__ == "__main__":
    main()
