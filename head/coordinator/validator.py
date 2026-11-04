import os, time, math
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

QUORUM = 2        # minimal 2 hasil yang sama agar diterima
MAX_REPLICAS = 4  # kalau tidak sepakat, tambah replika sampai batas ini

def same(a, b):
    if a.keys() != b.keys():
        return False
    for k in a:
        x, y = a[k], b[k]
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            if not math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-9):
                return False
        elif x != y:
            return False
    return True

def validate(c):
    # 1. Lease yang habis (worker mati/keluar) -> tugas bisa diambil worker lain
    n = c.execute("""UPDATE assignments SET status = 'expired'
                     WHERE status = 'running' AND lease_until < now()""").rowcount
    if n:
        print(f"{n} lease habis, tugas dikembalikan ke antrean", flush=True)

    # 2. Tugas yang hasilnya sudah cukup -> bandingkan
    tasks = c.execute("""
        SELECT t.id, t.replicas FROM tasks t
        WHERE t.status = 'pending'
          AND (SELECT count(*) FROM assignments a
               WHERE a.task_id = t.id AND a.status = 'submitted') >= t.replicas""").fetchall()
    for t in tasks:
        subs = c.execute("""SELECT worker_id, result FROM assignments
                            WHERE task_id = %s AND status = 'submitted'""", (t["id"],)).fetchall()
        best = []
        for s in subs:
            group = [x for x in subs if same(x["result"], s["result"])]
            if len(group) > len(best):
                best = group
        with c.transaction():
            if len(best) >= QUORUM:
                c.execute("UPDATE tasks SET status = 'done', result = %s WHERE id = %s",
                          (Jsonb(best[0]["result"]), t["id"]))
                for w in best:
                    c.execute("UPDATE workers SET credits = credits + 1 WHERE id = %s", (w["worker_id"],))
                print(f"tugas {t['id']} valid ({len(best)}/{len(subs)} sepakat)", flush=True)
            elif t["replicas"] < MAX_REPLICAS:
                c.execute("UPDATE tasks SET replicas = replicas + 1 WHERE id = %s", (t["id"],))
                print(f"tugas {t['id']} tidak sepakat, tambah replika", flush=True)
            else:
                c.execute("UPDATE tasks SET status = 'invalid' WHERE id = %s", (t["id"],))
                print(f"tugas {t['id']} ditandai invalid", flush=True)

if __name__ == "__main__":
    print("validator jalan", flush=True)
    while True:
        try:
            with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row, autocommit=True) as c:
                while True:
                    validate(c)
                    time.sleep(2)
        except psycopg.OperationalError as e:
            print("database belum siap:", e, flush=True)
            time.sleep(3)