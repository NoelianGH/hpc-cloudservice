import os, time
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from schema import migrate
from jobs import advance_jobs, canonical_hash
from publisher import publish_job, publish_pending
import project
import watch

QUORUM = 2        # minimal 2 hasil yang sama agar diterima
MAX_REPLICAS = 4  # kalau tidak sepakat, tambah replika sampai batas ini
MAX_TASK_FAILURES = int(os.environ.get("MAX_TASK_FAILURES", "2") or 2)  # gagal oleh N worker berbeda -> invalid
TICK = float(os.environ.get("VALIDATOR_TICK_SECONDS", "1") or 1)


def log(msg):
    print(msg, flush=True)


def backfill_hashes(c):
    """Isi result_hash untuk data dari versi lama (sebelum validasi berbasis hash)."""
    n = 0
    for table in ("assignments", "tasks"):
        rows = c.execute(f"SELECT id, result FROM {table} WHERE result IS NOT NULL AND result_hash IS NULL").fetchall()
        for r in rows:
            c.execute(f"UPDATE {table} SET result_hash = %s WHERE id = %s", (canonical_hash(r["result"]), r["id"]))
        n += len(rows)
    if n:
        log(f"{n} hash hasil lama diisi")


def validate(c):
    # 1. Lease yang habis (worker mati/keluar) -> tugas bisa diambil worker lain
    expired = c.execute("""UPDATE assignments SET status = 'expired'
                           WHERE status = 'running' AND lease_until < now()
                           RETURNING worker_id, task_id""").fetchall()
    if expired:
        log(f"{len(expired)} lease habis, tugas dikembalikan ke antrean")
        watch.on_lease_expired(c, expired)

    # 1b. Tugas yang terus gagal dijalankan (program job error/timeout) -> invalid
    bad = c.execute("""
        UPDATE tasks t SET status = 'invalid' WHERE t.status = 'pending'
          AND (SELECT count(*) FROM assignments a WHERE a.task_id = t.id
               AND a.status = 'failed') >= %s
        RETURNING t.id""", (MAX_TASK_FAILURES,)).fetchall()
    for b in bad:
        log(f"tugas {b['id']} gagal dijalankan {MAX_TASK_FAILURES}x, ditandai invalid")

    # 2. Tugas yang hasilnya sudah cukup -> bandingkan hash SHA-256 hasil tiap replika.
    #    Hash dihitung koordinator saat submit (bukan dikirim worker), jadi worker curang
    #    tidak bisa "meniru" hash tanpa benar-benar menghasilkan angka yang sama.
    tasks = c.execute("""
        SELECT t.id, t.replicas, t.credit FROM tasks t
        WHERE t.status = 'pending'
          AND (SELECT count(*) FROM assignments a
               WHERE a.task_id = t.id AND a.status = 'submitted') >= t.replicas""").fetchall()
    for t in tasks:
        subs = c.execute("""SELECT worker_id, result, result_hash FROM assignments
                            WHERE task_id = %s AND status = 'submitted' ORDER BY id""", (t["id"],)).fetchall()
        groups: dict[str, list] = {}
        for s in subs:
            s["result_hash"] = s["result_hash"] or canonical_hash(s["result"])  # data versi lama
            groups.setdefault(s["result_hash"], []).append(s)
        best = max(groups.values(), key=len)
        with c.transaction():
            if len(best) >= QUORUM:
                c.execute("UPDATE tasks SET status = 'done', result = %s, result_hash = %s WHERE id = %s",
                          (Jsonb(best[0]["result"]), best[0]["result_hash"], t["id"]))
                for w in best:
                    c.execute("UPDATE workers SET credits = credits + %s WHERE id = %s",
                              (t["credit"], w["worker_id"]))
                log(f"tugas {t['id']} valid ({len(best)}/{len(subs)} sepakat)")
            elif t["replicas"] < MAX_REPLICAS:
                c.execute("UPDATE tasks SET replicas = replicas + 1 WHERE id = %s", (t["id"],))
                log(f"tugas {t['id']} tidak sepakat, tambah replika")
            else:
                c.execute("UPDATE tasks SET status = 'invalid' WHERE id = %s", (t["id"],))
                log(f"tugas {t['id']} ditandai invalid")

    # 3. Kemajuan job: tahap berikutnya (multi-tahap) atau job selesai -> publikasi hasil
    for job_id in advance_jobs(c, log):
        project.on_job_finished(c, job_id)   # CI repo proyek: status jobdesk + centang di GitHub
        publish_job(c, job_id, log)

    # 4. Repo proyek (repo B): cek push baru lewat polling -> job CI (bila webhook tidak dipakai)
    # 5. Jobdesk: assign jobdesk antrean (FIFO) ke relawan online yang belum punya jobdesk.
    #    Jobdesk tidak pernah dicabut dari relawan; bila compute node mati, tugas komputasinya
    #    yang pindah ke node lain (langkah 1, lease habis).
    # Kesalahan di bagian proyek tidak boleh menghentikan validasi tugas komputasi.
    for step in (project.poll, project.auto_assign):
        try:
            step(c)
        except psycopg.OperationalError:
            raise
        except Exception as e:
            log(f"{step.__name__} gagal: {e}")
            watch.on_step_error(c, step.__name__, e)

    # 6. Watch: cek per branch repo B, hasil worker, CI, backup -> peringatan admin (+ email)
    watch.check(c)


if __name__ == "__main__":
    log("validator jalan")
    while True:
        try:
            with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row, autocommit=True) as c:
                migrate(c)
                backfill_hashes(c)
                publish_pending(c, log)
                while True:
                    validate(c)
                    time.sleep(TICK)
        except psycopg.OperationalError as e:
            log(f"database belum siap: {e}")
            time.sleep(3)
        except psycopg.errors.UndefinedTable as e:
            log(f"tabel belum dibuat (menunggu init.sql/koordinator): {e}")
            time.sleep(3)
