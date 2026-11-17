"""
Watch: pemantauan kejadian + PERINGATAN untuk admin.

Bukan memantau folder, tetapi memantau KEJADIAN yang berarti bagi sistem ini:

  error       CI berstatus error, CI branch main gagal, tugas invalid karena terus gagal,
              publikasi hasil gagal, langkah validator (polling/assign) gagal
  suspicious  hasil worker beda dari mayoritas (quorum), worker sering beda (indikasi curang),
              login admin dikunci, webhook dengan tanda tangan salah / dari repo lain
  branch      cek PER BRANCH repo B setiap ada push:
                - task/<id>-...: commit harus oleh relawan pemilik jobdesk itu
                - task/... tanpa jobdesk aktif, branch di luar aturan (bukan main / task/*)
                - push langsung ke main yang bukan hasil merge oleh sistem
                - force push (riwayat ditulis ulang)
  backup      backup terakhir gagal, terlambat (> BACKUP_MAX_AGE_MIN), atau salinan luar gagal
  node        compute node mati di tengah tugas (info; tugasnya otomatis pindah node)

Setiap peringatan punya "key" unik sehingga tidak dobel. Peringatan berulang (mis. login
gagal) dihitung (count) per jam. Admin melihatnya di tab PERINGATAN dan menandai "sudah
ditangani". Peringatan level >= ALERT_EMAIL_MIN_LEVEL juga dikirim ke email admin, digabung
dan dibatasi (paling sering tiap ALERT_EMAIL_COOLDOWN_MIN menit; critical paling cepat 2 menit).

Variabel lingkungan:
  ALERT_EMAIL_TO            penerima email (bawaan ADMIN_EMAIL; kosong keduanya = tanpa email)
  ALERT_EMAIL_MIN_LEVEL     info | warning | critical  (bawaan warning)
  ALERT_EMAIL_COOLDOWN_MIN  bawaan 15
  WATCH_MISMATCH_LIMIT      hasil beda per worker dalam 24 jam sebelum dianggap curang (bawaan 3)
  BACKUP_MAX_AGE_MIN        batas umur backup terakhir (bawaan 130; 0 = tidak dicek)
"""
import os
import threading
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException
from psycopg.types.json import Jsonb

from common import db

LEVELS = {"info": 0, "warning": 1, "critical": 2}
EMAIL_TO = (os.environ.get("ALERT_EMAIL_TO", "").strip() or os.environ.get("ADMIN_EMAIL", "").strip())
EMAIL_MIN = LEVELS.get(os.environ.get("ALERT_EMAIL_MIN_LEVEL", "warning").strip().lower(), 1)
EMAIL_COOLDOWN_S = 60 * float(os.environ.get("ALERT_EMAIL_COOLDOWN_MIN", "15") or 15)
EMAIL_CRITICAL_S = 120
MISMATCH_LIMIT = int(os.environ.get("WATCH_MISMATCH_LIMIT", "3") or 3)
BACKUP_MAX_AGE_MIN = float(os.environ.get("BACKUP_MAX_AGE_MIN", "130") or 0)
CHECK_SECONDS = float(os.environ.get("WATCH_CHECK_SECONDS", "20") or 20)
PUSH_SETTLE_SECONDS = 15   # tunggu sebentar: merge oleh sistem dicatat dulu sebelum push main dicek

_started = time.time()
_last_check = 0.0
_last_email = 0.0


def log(msg):
    print(f"[watch] {msg}", flush=True)


def _hour() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H")


# =============================================================================
# Mencatat peringatan
# =============================================================================

def alert(c, key: str, level: str, category: str, title: str, detail: str = "",
          ref: dict | None = None, repeat: bool = False) -> bool:
    """
    Catat peringatan. repeat=False: satu fakta = satu peringatan (key yang sama diabaikan).
    repeat=True: kejadian berulang; key yang sama menambah count dan membuka lagi peringatan
    yang sudah ditandai ditangani. Mengembalikan True bila peringatan baru/dibuka lagi.
    """
    level = level if level in LEVELS else "warning"
    if repeat:
        row = c.execute("""
            INSERT INTO alerts (key, level, category, title, detail, ref) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (key) DO UPDATE SET count = alerts.count + 1, last_at = now(),
                detail = EXCLUDED.detail,
                emailed_at = CASE WHEN alerts.acked_at IS NULL THEN alerts.emailed_at END,
                acked_at = NULL, acked_by = NULL
            RETURNING (xmax = 0) AS fresh, count""",
            (key, level, category, title[:300], (detail or "")[:4000], Jsonb(ref or {}))).fetchone()
        fresh = bool(row and row["fresh"])
    else:
        # NOT EXISTS dulu: cek berkala mengulang fakta yang sama, jangan habiskan nomor id
        row = c.execute("""INSERT INTO alerts (key, level, category, title, detail, ref)
                           SELECT %s, %s, %s, %s, %s, %s WHERE NOT EXISTS (SELECT 1 FROM alerts WHERE key = %s)
                           ON CONFLICT (key) DO NOTHING RETURNING id""",
                        (key, level, category, title[:300], (detail or "")[:4000], Jsonb(ref or {}), key)).fetchone()
        fresh = row is not None
    if fresh:
        log(f"{level.upper()} [{category}] {title}" + (f" - {detail[:200]}" if detail else ""))
    return fresh


def alert_now(*args, **kwargs) -> None:
    """Seperti alert(), dengan koneksi sendiri. Dipakai dari handler API; tidak pernah melempar error."""
    try:
        with db() as c:
            alert(c, *args, **kwargs)
    except Exception as e:  # peringatan tidak boleh menggagalkan permintaan asli
        log(f"gagal mencatat peringatan: {e}")


# =============================================================================
# Kejadian yang dilaporkan langsung oleh validator / API
# =============================================================================

def on_lease_expired(c, rows: list[dict]) -> None:
    """Compute node berhenti mengirim heartbeat di tengah tugas -> tugas pindah ke node lain."""
    by_worker: dict[str, int] = {}
    for r in rows:
        by_worker[r["worker_id"]] = by_worker.get(r["worker_id"], 0) + 1
    for wid, n in by_worker.items():
        w = c.execute("SELECT name FROM workers WHERE id = %s", (wid,)).fetchone()
        alert(c, f"node_lost:{wid}:{_hour()}", "info", "node",
              f"Compute node {w['name'] if w else wid} mati di tengah tugas, tugasnya dipindah ke node lain",
              f"{n} tugas (lease habis, tanpa heartbeat 30 detik). Jobdesk relawan tidak berubah.",
              {"worker_id": wid}, repeat=True)


def on_step_error(c, step: str, err: Exception) -> None:
    alert(c, f"step:{step}:{_hour()}", "warning", "error", f"Langkah validator '{step}' gagal",
          str(err)[:1000], {"step": step}, repeat=True)


# =============================================================================
# Cek per branch repo B (dipanggil untuk setiap push yang tercatat di repo_pushes)
# =============================================================================

def _commits(branch: str, base: str | None, sha: str) -> tuple[str | None, list[dict]]:
    """Bandingkan base...sha lewat GitHub API: (status, daftar commit {sha, login, email})."""
    import project
    st, data = project._gh("GET", f"/compare/{base}...{sha}")
    if st != 200 or not isinstance(data, dict):
        raise RuntimeError(f"GitHub compare HTTP {st}")
    out = []
    for cm in (data.get("commits") or [])[-100:]:
        info = cm.get("commit") or {}
        out.append({"sha": cm.get("sha", ""),
                    "login": ((cm.get("author") or {}).get("login") or "").lower() or None,
                    "email": ((info.get("author") or {}).get("email") or ""),
                    "message": ((info.get("message") or "").splitlines() or [""])[0][:120]})
    return data.get("status"), out


def check_push(c, p: dict) -> None:
    import project
    branch, sha, short = p["branch"], p["sha"], p["sha"][:7]
    ref = {"branch": branch, "sha": sha}
    main = project.DEFAULT_BRANCH
    prev = c.execute("""SELECT sha FROM repo_pushes WHERE branch = %s AND seen_at < %s
                        ORDER BY seen_at DESC LIMIT 1""", (branch, p["seen_at"])).fetchone()

    if branch == main:
        if prev and not c.execute("SELECT 1 FROM jobdesks WHERE merged_sha = %s", (sha,)).fetchone():
            # Tanpa PROJECT_GIT_TOKEN admin me-merge PR manual di GitHub, jadi cukup info
            alert(c, f"main_push:{sha}", "warning" if project.GIT_TOKEN else "info", "branch",
                  f"Push ke {main} yang bukan merge oleh sistem",
                  f"{main}@{short} oleh {p.get('pusher') or 'tidak diketahui'}. Semua perubahan seharusnya lewat "
                  "jobdesk + PR (Setujui & merge). Disarankan aktifkan branch protection di GitHub.", ref)
        if p.get("forced"):
            alert(c, f"force:{branch}:{sha}", "critical", "branch", f"Force push ke {main}",
                  f"Riwayat {main} ditulis ulang ({short}) oleh {p.get('pusher') or '?'}.", ref)
        return

    if not branch.startswith(project.BRANCH_PREFIX):
        alert(c, f"branch_foreign:{branch}", "warning", "branch", f"Branch di luar aturan: {branch}",
              f"Hanya {main} dan {project.BRANCH_PREFIX}* yang dipakai. Branch ini tidak di-CI. "
              f"Push oleh {p.get('pusher') or 'tidak diketahui'}.", ref)
        return

    # Branch baru yang masih sama dengan main (dibuat sistem): belum ada commit relawan
    if c.execute("SELECT 1 FROM repo_pushes WHERE branch = %s AND sha = %s", (main, sha)).fetchone():
        return
    jd = c.execute("""SELECT d.id, d.title, d.status, d.worker_id, w.github_username, w.name
                      FROM jobdesks d LEFT JOIN workers w ON w.id = d.worker_id
                      WHERE d.branch = %s ORDER BY d.id DESC LIMIT 1""", (branch,)).fetchone()
    if not jd:
        alert(c, f"branch_nojd:{branch}", "warning", "branch", f"Branch {branch} tidak punya jobdesk",
              f"Push {short} oleh {p.get('pusher') or 'tidak diketahui'}. Branch task/* seharusnya dibuat sistem "
              "saat jobdesk di-assign.", ref)
        return
    ref["jobdesk_id"] = jd["id"]
    if jd["status"] not in ("in_progress", "review"):
        alert(c, f"branch_inactive:{branch}:{jd['status']}", "warning", "branch",
              f"Push ke branch jobdesk #{jd['id']} yang berstatus {jd['status']}",
              f"{branch}@{short} oleh {p.get('pusher') or 'tidak diketahui'}.", ref, repeat=True)

    owner = (jd["github_username"] or "").lower()
    who = f"@{jd['github_username']}" if jd["github_username"] else (jd["name"] or "?")
    pusher = (p.get("pusher") or "").lower()
    if pusher and owner and pusher != owner:
        alert(c, f"pusher:{branch}:{sha}", "critical", "branch",
              f"Push ke branch jobdesk #{jd['id']} bukan oleh pemiliknya",
              f"{branch}@{short} di-push oleh @{pusher}, padahal jobdesk ini milik {who}.", ref)

    forced = bool(p.get("forced"))
    try:
        # Commit milik branch ini saja (yang belum ada di main). Commit main yang ikut ter-merge
        # ke branch (git merge main) tidak dihitung, jadi tidak salah tuduh.
        status, commits = _commits(branch, main, sha)
        if prev and not forced and p.get("source") == "poll" and project.GIT_TOKEN:
            st, _ = _commits(branch, prev["sha"], sha)   # polling tidak tahu force push: bandingkan
            forced = st in ("diverged", "behind")
    except Exception as e:
        c.execute("UPDATE repo_pushes SET check_note = %s WHERE branch = %s AND sha = %s",
                  (f"author tidak dicek: {e}"[:300], branch, sha))
        commits = None
    if forced:
        alert(c, f"force:{branch}:{sha}", "warning", "branch", f"Force push di {branch}",
              f"Riwayat ditulis ulang: {prev['sha'][:7] if prev else '?'} -> {short} "
              f"oleh {p.get('pusher') or 'tidak diketahui'}.", ref)
    if commits is None:
        return
    def fresh(kind, items):   # commit yang sudah pernah dilaporkan tidak dilaporkan lagi di push berikutnya
        return [cm for cm in items if not c.execute(
            "SELECT 1 FROM alerts WHERE key LIKE %s AND ref->'commits' ? %s",
            (f"{kind}:{branch}:%", cm["sha"])).fetchone()]
    foreign = fresh("author", [cm for cm in commits if cm["login"] and owner and cm["login"] != owner])
    unknown = fresh("author_unknown", [cm for cm in commits if not cm["login"]])
    if foreign:
        lines = "\n".join(f"{cm['sha'][:7]} @{cm['login']}: {cm['message']}" for cm in foreign[:10])
        alert(c, f"author:{branch}:{sha}", "critical", "branch",
              f"Commit di branch jobdesk #{jd['id']} bukan dari pemiliknya ({who})",
              f"{len(foreign)} commit oleh akun lain:\n{lines}",
              {**ref, "commits": [cm["sha"] for cm in foreign]})
    if unknown:
        alert(c, f"author_unknown:{branch}:{sha}", "info", "branch",
              f"Commit di {branch} tidak terhubung ke akun GitHub",
              f"{len(unknown)} commit memakai email git yang tidak terdaftar di GitHub "
              f"(mis. {unknown[0]['email'] or '-'}). Minta relawan memakai email akun GitHub-nya "
              "(git config user.email) agar commit bisa ditelusuri.", {**ref, "commits": [cm["sha"] for cm in unknown]})
    names = sorted({cm["login"] for cm in commits if cm["login"]})
    c.execute("UPDATE repo_pushes SET author = %s, check_note = %s WHERE branch = %s AND sha = %s",
              (",".join(names)[:200] or None, f"{len(commits)} commit dicek ({status})", branch, sha))


def _check_pushes(c) -> None:
    rows = c.execute(f"""SELECT * FROM repo_pushes WHERE NOT checked
                         AND seen_at < now() - interval '{PUSH_SETTLE_SECONDS} seconds'
                         ORDER BY seen_at LIMIT 20""").fetchall()
    for p in rows:
        c.execute("UPDATE repo_pushes SET checked = TRUE WHERE branch = %s AND sha = %s", (p["branch"], p["sha"]))
        try:
            check_push(c, p)
        except Exception as e:
            log(f"cek push {p['branch']}@{p['sha'][:7]} gagal: {e}")


# =============================================================================
# Cek berkala dari isi database
# =============================================================================

def _check_results(c) -> None:
    # Hasil worker yang beda dari hasil yang disepakati mayoritas (quorum)
    bad = c.execute("""
        SELECT a.id, a.worker_id, w.name, w.github_username, t.id AS task_id, t.job_id, j.kind
        FROM assignments a JOIN tasks t ON t.id = a.task_id JOIN jobs j ON j.id = t.job_id
        JOIN workers w ON w.id = a.worker_id
        WHERE a.status = 'submitted' AND t.status = 'done' AND t.result_hash IS NOT NULL
          AND a.result_hash IS DISTINCT FROM t.result_hash
          AND a.finished_at > now() - interval '1 day'""").fetchall()
    for b in bad:
        alert(c, f"mismatch:{b['id']}", "warning", "suspicious",
              f"Hasil worker {b['name']} beda dari mayoritas",
              f"Tugas {b['task_id']} (job #{b['job_id']}, {b['kind']}): hasil ditolak validator, tanpa kredit.",
              {"worker_id": b["worker_id"], "task_id": b["task_id"], "job_id": b["job_id"]})
    counts: dict[str, list] = {}
    for b in bad:
        counts.setdefault(b["worker_id"], []).append(b)
    for wid, items in counts.items():
        if len(items) >= MISMATCH_LIMIT:
            w = items[0]
            alert(c, f"cheat:{wid}:{datetime.now(timezone.utc):%Y%m%d}", "critical", "suspicious",
                  f"Worker {w['name']} kemungkinan curang: {len(items)} hasil beda dalam 24 jam",
                  f"GitHub @{w['github_username'] or '-'}. Pertimbangkan cabut token di tab WORKER.",
                  {"worker_id": wid})

    # Tugas invalid: tidak sepakat sampai batas replika, atau programnya terus gagal
    for t in c.execute("""
            SELECT t.id, t.job_id, j.kind,
                   (SELECT count(*) FROM assignments a WHERE a.task_id = t.id AND a.status = 'failed') AS fails
            FROM tasks t JOIN jobs j ON j.id = t.job_id
            WHERE t.status = 'invalid' AND j.created_at > now() - interval '1 day'""").fetchall():
        fails = t["fails"] > 0
        alert(c, f"task_invalid:{t['id']}", "warning", "error" if fails else "suspicious",
              f"Tugas {t['id']} (job #{t['job_id']}, {t['kind']}) invalid",
              "Program tugas gagal dijalankan berulang kali." if fails
              else "Hasil replika tidak pernah sepakat sampai batas replika.",
              {"task_id": t["id"], "job_id": t["job_id"]})


def _check_jobs(c) -> None:
    import project
    for j in c.execute("""
            SELECT id, kind, spec->>'branch' AS branch, spec->>'sha' AS sha, result->>'ci_status' AS ci,
                   result->>'build_error' AS build_error, publish_status
            FROM jobs WHERE finished_at > now() - interval '1 day'
              AND (kind = 'ci' OR publish_status LIKE 'failed%')""").fetchall():
        ref = {"job_id": j["id"], "branch": j["branch"], "sha": j["sha"]}
        if j["kind"] == "ci" and j["ci"] == "error":
            alert(c, f"ci_error:{j['id']}", "warning", "error",
                  f"CI job #{j['id']} error ({j['branch']}@{(j['sha'] or '')[:7]})",
                  j["build_error"] or "Kesalahan sistem/tes tidak deterministik. Lihat log di tab CI.", ref)
        elif j["kind"] == "ci" and j["ci"] == "failed" and j["branch"] == project.DEFAULT_BRANCH:
            alert(c, f"ci_main:{j['id']}", "critical", "error",
                  f"CI branch {j['branch']} GAGAL ({(j['sha'] or '')[:7]})",
                  "Kode utama tidak lulus test. Periksa merge terakhir.", ref)
        if (j["publish_status"] or "").startswith("failed"):
            alert(c, f"publish:{j['id']}", "warning", "error", f"Publikasi hasil job #{j['id']} gagal",
                  j["publish_status"], ref)


def _check_backups(c) -> None:
    if BACKUP_MAX_AGE_MIN <= 0:
        return
    for b in c.execute("""SELECT id, at, error FROM backups WHERE at > now() - interval '1 day'
                          AND (NOT ok OR error IS NOT NULL)""").fetchall():
        if b["error"] and b["error"].startswith("salinan"):
            alert(c, f"backup_copy:{b['at']:%Y%m%d}", "warning", "backup", "Salinan backup ke folder luar gagal",
                  f"{b['error']} (BACKUP_COPY_DIR). Backup lokal tetap dibuat.", repeat=True)
        else:
            alert(c, f"backup_fail:{b['id']}", "critical", "backup", "Backup database GAGAL", b["error"] or "")
    last = c.execute("""SELECT id, at, extract(epoch FROM now() - at) / 60 AS age
                        FROM backups WHERE ok ORDER BY at DESC LIMIT 1""").fetchone()
    if last and last["age"] > BACKUP_MAX_AGE_MIN:
        alert(c, f"backup_stale:{last['id']}", "critical", "backup", "Backup database terlambat",
              f"Backup berhasil terakhir {int(last['age'])} menit lalu ({last['at']:%Y-%m-%d %H:%M} UTC). "
              "Cek layanan backup: ./hpc.sh head-logs backup")
    elif not last and time.time() - _started > 60 * min(BACKUP_MAX_AGE_MIN, 30):
        alert(c, "backup_never", "critical", "backup", "Belum ada backup database yang berhasil",
              "Layanan backup belum jalan. Jalankan ./hpc.sh head-up (layanan 'backup').")


# =============================================================================
# Email ke admin (digabung + dibatasi)
# =============================================================================

def _send_emails(c) -> None:
    global _last_email
    rows = c.execute("""SELECT id, level, category, title, detail, count, created_at FROM alerts
                        WHERE emailed_at IS NULL AND acked_at IS NULL ORDER BY id""").fetchall()
    rows = [r for r in rows if LEVELS.get(r["level"], 1) >= EMAIL_MIN]
    if not rows:
        return
    wait = EMAIL_CRITICAL_S if any(r["level"] == "critical" for r in rows) else EMAIL_COOLDOWN_S
    if time.time() - _last_email < wait:
        return
    c.execute("UPDATE alerts SET emailed_at = now() WHERE id = ANY(%s)", ([r["id"] for r in rows],))
    _last_email = time.time()
    if not EMAIL_TO:
        log(f"{len(rows)} peringatan tidak dikirim email: ALERT_EMAIL_TO / ADMIN_EMAIL kosong")
        return
    crit = sum(r["level"] == "critical" for r in rows)
    subject = f"[HPC Cloud] {len(rows)} peringatan" + (f" ({crit} CRITICAL)" if crit else "")
    body = ["Peringatan baru dari head node HPC Cloud Service:", ""]
    for r in rows[:30]:
        body.append(f"[{r['level'].upper()}] {r['title']}" + (f" (x{r['count']})" if r["count"] > 1 else ""))
        body.append(f"  {r['created_at']:%Y-%m-%d %H:%M} UTC, kategori {r['category']}")
        if r["detail"]:
            body.extend("  " + ln for ln in r["detail"].splitlines()[:6])
        body.append("")
    if len(rows) > 30:
        body.append(f"... dan {len(rows) - 30} lainnya.")
    body.append("Buka dashboard admin (/admin), tab PERINGATAN, lalu tandai yang sudah ditangani.")
    text = "\n".join(body)

    def send():
        from email_service import send_email
        res = send_email(EMAIL_TO, subject, text)
        log(f"email peringatan ke admin: {res.get('status')}" + (f" ({res.get('error')})" if res.get("error") else ""))
    threading.Thread(target=send, daemon=True).start()


def check(c) -> None:
    """Dipanggil validator tiap putaran; benar-benar bekerja tiap WATCH_CHECK_SECONDS detik."""
    global _last_check
    if time.time() - _last_check < CHECK_SECONDS:
        return
    _last_check = time.time()
    for step in (_check_pushes, _check_results, _check_jobs, _check_backups, _send_emails):
        try:
            step(c)
        except Exception as e:
            log(f"{step.__name__} gagal: {e}")


# =============================================================================
# API admin
# =============================================================================

router = APIRouter(prefix="/api/admin", tags=["peringatan"])


def _admin(auth):
    import project
    return project._admin(auth)


@router.get("/alerts")
def list_alerts(authorization: str = Header(None), state: str = "open", limit: int = 100):
    _admin(authorization)
    where = "acked_at IS NULL" if state == "open" else "TRUE"
    with db() as c:
        rows = c.execute(f"""SELECT id, key, level, category, title, detail, ref, count, created_at, last_at,
                                    acked_at, acked_by, emailed_at FROM alerts WHERE {where}
                             ORDER BY (acked_at IS NULL) DESC,
                                      CASE level WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
                                      last_at DESC LIMIT %s""", (max(1, min(limit, 500)),)).fetchall()
        summary = c.execute("""SELECT count(*) FILTER (WHERE acked_at IS NULL) AS open,
                                      count(*) FILTER (WHERE acked_at IS NULL AND level = 'critical') AS critical,
                                      count(*) FILTER (WHERE acked_at IS NULL AND level = 'warning') AS warning,
                                      count(*) FILTER (WHERE acked_at IS NULL AND level = 'info') AS info
                               FROM alerts""").fetchone()
    return {"summary": summary, "alerts": rows,
            "email": {"to": bool(EMAIL_TO), "min_level": [k for k, v in LEVELS.items() if v == EMAIL_MIN][0],
                      "cooldown_min": EMAIL_COOLDOWN_S / 60}}


@router.post("/alerts/{alert_id}/ack")
def ack_alert(alert_id: int, authorization: str = Header(None)):
    who = _admin(authorization)
    with db() as c:
        n = c.execute("UPDATE alerts SET acked_at = now(), acked_by = %s WHERE id = %s AND acked_at IS NULL",
                      (who, alert_id)).rowcount
    if not n:
        raise HTTPException(404, "Peringatan tidak ditemukan atau sudah ditangani.")
    return {"ok": True}


@router.post("/alerts/ack-all")
def ack_all(authorization: str = Header(None), level: str | None = None):
    who = _admin(authorization)
    with db() as c:
        n = c.execute("""UPDATE alerts SET acked_at = now(), acked_by = %s
                         WHERE acked_at IS NULL AND (%s::text IS NULL OR level = %s)""",
                      (who, level, level)).rowcount
    return {"ok": True, "acked": n}


@router.get("/backups")
def list_backups(authorization: str = Header(None), limit: int = 30):
    _admin(authorization)
    with db() as c:
        rows = c.execute("""SELECT id, at, ok, file, bytes, sha256, copied, error FROM backups
                            ORDER BY at DESC LIMIT %s""", (max(1, min(limit, 200)),)).fetchall()
        last_ok = c.execute("""SELECT at, extract(epoch FROM now() - at) / 60 AS age_min
                               FROM backups WHERE ok ORDER BY at DESC LIMIT 1""").fetchone()
    return {"backups": rows, "last_ok": last_ok, "max_age_min": BACKUP_MAX_AGE_MIN}
