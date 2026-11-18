"""
Akses relawan ke COMPUTE NODE per jobdesk (login lewat command prompt, seperti SSH).

Alur:
  1. Relawan login di WEBSITE (email + password), lalu menekan "AMBIL JOBDESK": sistem
     memberi jobdesk tertua di antrean (FIFO) dan membuat AKSES NODE untuk jobdesk itu:
       - user Linux  jd<id_jobdesk>  (mis. jd12),
       - SATU token node  hpc_ng_xxxx-xxxx-xxxx-xxxx-xxxx: password ssh sekaligus login git ke
         gerbang git koordinator. Berlaku sampai jobdesk disetujui / dibatalkan, paling lama
         NODE_TOKEN_TTL_DAYS hari (bawaan 7); kedaluwarsa = dicabut, admin bisa terbitkan ulang.
  2. Agen di kontainer compute node (node/agent.py, disediakan platform) menarik daftar akses
     tiap beberapa detik (pull, sama seperti worker), membuat user-nya, dan meng-clone repo B
     HANYA branch jobdesk itu. Relawan masuk dari PC-nya:   ssh -p 2222 jd12@<alamat-head>
  3. Di node, 'git push' lewat GERBANG GIT koordinator (/api/node/git/...), bukan langsung ke
     GitHub. Gerbang hanya meneruskan push ke  refs/heads/<branch jobdesk>  (bukan branch lain,
     bukan hapus branch), memakai PROJECT_GIT_TOKEN milik platform. Relawan tidak diundang
     jadi collaborator GitHub, jadi tidak ada jalan lain untuk push.
  4. 'jobdesk ajukan' di node (atau tombol di website) membuka Pull Request.
  5. Admin menyetujui (PR di-merge) / membatalkan -> akses DICABUT: token node mati seketika,
     agen memutus semua sesi SSH user itu dan menghapus user-nya. Login website tidak
     terpengaruh; relawan bisa mengambil jobdesk baru di website -> akses node baru.

  6. Relawan TIDAK AKTIF selama NODE_IDLE_MINUTES (bawaan 30; tidak ada ketikan / keluaran di
     terminal dan tidak ada proses yang memakai CPU): sesi SSH diputus dan node DILEPAS untuk
     relawan lain. Jobdesk tetap miliknya dan token node TETAP berlaku. Folder kerja tetap ada
     (folder /home dipakai bersama semua node). Untuk lanjut: MASUK LAGI KE NODE di website
     (node terakhir diutamakan), lalu ssh dengan token yang sama. Semua node penuh = ditolak
     dengan pesan jelas.

Compute node mati (tidak sync > NODE_DEAD_SECONDS): aksesnya dilepas dan diambil node lain
(FIFO). Folder kerja ada di volume bersama, jadi pekerjaan yang belum di-push ikut pindah.

Variabel lingkungan:
  NODE_ACCESS         1 (bawaan) = aktif; 0 = alur lama (relawan diundang collaborator GitHub)
  NODE_TOKEN          rahasia bersama koordinator <-> agen compute node (dibuat './hpc.sh head-up')
  NODE_SSH_HOST       alamat yang ditampilkan ke relawan untuk ssh (bawaan localhost; isi IP LAN head)
  NODE_SSH_PORT       port ssh cadangan bila agen tidak melaporkan port-nya (bawaan 2222);
                      tiap node melaporkan port publiknya sendiri (node1 2222, node2 2223, ...)
  NODE_MAX_USERS      relawan aktif maksimal per compute node (bawaan 1: satu node = satu relawan,
                      lengkap dengan Docker uji sendiri). Bila semua node penuh,
                      AMBIL JOBDESK ditolak dan jobdesk tetap di antrean sampai ada slot kosong.

Banyak compute node: akses baru ditempatkan di node ONLINE yang paling sedikit penghuninya,
bila sama, node yang paling lama tidak diberi akses (bergiliran: node1, node2, node1, ...).
  NODE_DEAD_SECONDS   node dianggap mati bila tidak sync selama ini (bawaan 60)
  NODE_TOKEN_TTL_DAYS umur maksimal token node per jobdesk (bawaan 7; 0 = tanpa batas). Lewat dari
                      itu akses dicabut seperti saat disetujui, jobdesk tetap milik relawan; admin
                      memilih BERI AKSES NODE (token baru) atau KEMBALIKAN KE ANTREAN.
  NODE_IDLE_MINUTES   lepas node setelah sekian menit tidak aktif (bawaan 30; 0 = tidak pernah)
  NODE_READ_MAIN      1 (bawaan) = dari node boleh fetch main (baca saja, untuk git merge origin/main);
                      0 = hanya branch jobdesk sendiri yang terlihat & bisa di-fetch

Batas baca: gerbang hanya mengiklankan branch jobdesk (+ main bila NODE_READ_MAIN=1), dan menolak
fetch commit lain ('want' di luar ujung branch itu). PROJECT_GIT_TOKEN tidak pernah ada di node.
Catatan: bila repo B PUBLIK di GitHub, siapa pun tetap bisa membacanya langsung dari github.com;
jadikan repo B private agar gerbang ini satu-satunya jalan baca.
"""
import base64
import gzip
import hmac
import os
import re
import secrets
import urllib.error
import urllib.request

from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel

from common import db, strong_secret
from volunteer_auth import check_volunteer_auth
import project

ENABLED = os.environ.get("NODE_ACCESS", "1").strip() != "0"
NODE_TOKEN = strong_secret("NODE_TOKEN")
SSH_HOST = os.environ.get("NODE_SSH_HOST", "").strip() or "localhost"
SSH_PORT = int(os.environ.get("NODE_SSH_PORT", "2222") or 2222)
MAX_USERS = int(os.environ.get("NODE_MAX_USERS", "1") or 1)
IDLE_SECONDS = int(float(os.environ.get("NODE_IDLE_MINUTES", "30") or 0) * 60)
PICK_LOCK = 4242   # pg_advisory_xact_lock: penempatan akses ke node tidak saling balap
DEAD_SECONDS = int(os.environ.get("NODE_DEAD_SECONDS", "60") or 60)
READ_MAIN = os.environ.get("NODE_READ_MAIN", "1").strip() != "0"
TOKEN_TTL_DAYS = float(os.environ.get("NODE_TOKEN_TTL_DAYS", "7") or 0)
EXPIRED_REASON = "token node kedaluwarsa"
UID_BASE = 20000
MAX_PUSH_BYTES = 200 * 1024 * 1024
GITHUB_GIT = os.environ.get("GITHUB_GIT_URL", "https://github.com").rstrip("/")

TOKEN_PREFIX = "hpc_ng_"
ZERO_SHA = "0" * 40
NODE_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,40}$")
USER_RE = re.compile(r"^jd\d{1,9}$")

router = APIRouter(tags=["compute node"])


def log(msg):
    print(f"[NODE] {msg}", flush=True)


def active() -> bool:
    return ENABLED and project.enabled()


# =============================================================================
# Membuat / mencabut akses (dipanggil project.py)
# =============================================================================

def username_for(jobdesk_id: int) -> str:
    return f"jd{jobdesk_id}"


def new_token() -> str:
    """
    Token node: password ssh DAN login git, satu untuk satu jobdesk. 5 kelompok x 4 karakter dari
    31 huruf/angka yang tidak mirip (tanpa 0/o/1/l/i) = ~99 bit acak, tetap bisa diketik,
    mis. hpc_ng_k7pq-2mzx-9wtr-c4hd-8wnb.
    """
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    return TOKEN_PREFIX + "-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(5))


def create_access(c, jobdesk_id: int, worker_id: str) -> dict | None:
    """Akses node baru untuk jobdesk (akses aktif lama jobdesk ini dicabut lebih dulu)."""
    if not ENABLED:
        return None
    revoke_access(c, jobdesk_id, "diganti akses baru")
    c.execute("SELECT pg_advisory_xact_lock(%s)", (PICK_LOCK,))
    node = pick_node(c)
    token = new_token()   # kolom password dan git_token berisi token yang SAMA
    row = c.execute("""
        INSERT INTO node_access (jobdesk_id, worker_id, username, uid, password, git_token, node, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s,
                CASE WHEN %s > 0 THEN now() + make_interval(secs => %s) END) RETURNING id, username""",
        (jobdesk_id, worker_id, username_for(jobdesk_id), UID_BASE + jobdesk_id, token, token, node,
         TOKEN_TTL_DAYS, TOKEN_TTL_DAYS * 86400)).fetchone()
    if node:
        c.execute("UPDATE nodes SET last_assigned_at = now() WHERE name = %s", (node,))
    project._event(c, jobdesk_id, "sistem", "akses_node",
                   f"user {row['username']} " + (f"ditempatkan di {node}" if node else "menunggu compute node kosong"))
    return row


def _free_nodes_sql() -> str:
    return """
        SELECT n.name, n.max_users,
               (SELECT count(*) FROM node_access a WHERE a.node = n.name AND a.status = 'active') AS used
        FROM nodes n WHERE n.last_seen > now() - make_interval(secs => %s)"""


def pick_node(c) -> str | None:
    """Node online dengan slot kosong: paling sedikit penghuni, lalu yang paling lama tidak diberi akses."""
    r = c.execute(f"""SELECT f.name FROM ({_free_nodes_sql()}) f JOIN nodes n ON n.name = f.name
                      WHERE f.used < f.max_users
                      ORDER BY f.used, n.last_assigned_at NULLS FIRST, f.name LIMIT 1""",
                  (DEAD_SECONDS,)).fetchone()
    return r["name"] if r else None


def capacity(c) -> dict:
    """Slot compute node: total, terpakai, kosong (hanya node online)."""
    expire_due(c)   # slot dari token yang kedaluwarsa langsung kosong, walau belum ada node yang sync
    rows = c.execute(_free_nodes_sql(), (DEAD_SECONDS,)).fetchall()
    total = sum(r["max_users"] for r in rows)
    used = sum(min(r["used"], r["max_users"]) for r in rows)
    waiting = c.execute("""SELECT count(*) AS n FROM node_access
                             WHERE status = 'active' AND node IS NULL AND parked_at IS NULL""").fetchone()["n"]
    return {"nodes": len(rows), "total": total, "used": used, "free": max(0, total - used - waiting)}


def expire_due(c) -> int:
    """Akses yang melewati NODE_TOKEN_TTL_DAYS dicabut (jobdesk tetap milik relawan)."""
    rows = c.execute("""
        UPDATE node_access SET status = 'revoked', revoked_at = now(), revoked_reason = %s
        WHERE status = 'active' AND expires_at IS NOT NULL AND expires_at <= now()
        RETURNING jobdesk_id, username, node""", (EXPIRED_REASON,)).fetchall()
    for r in rows:
        project._event(c, r["jobdesk_id"], "sistem", "akses_node_dicabut",
                       f"user {r['username']} di {r['node'] or '-'}: {EXPIRED_REASON}; admin bisa BERI AKSES NODE "
                       "atau KEMBALIKAN KE ANTREAN")
        log(f"akses {r['username']} kedaluwarsa")
    return len(rows)


def last_revoked(c, jobdesk_id: int) -> dict | None:
    """Akses terakhir yang dicabut (untuk menjelaskan ke relawan / admin kenapa tidak ada akses)."""
    return c.execute("""SELECT revoked_reason AS reason, revoked_at AS at, revoked_reason = %s AS expired
                          FROM node_access WHERE jobdesk_id = %s AND status = 'revoked'
                         ORDER BY id DESC LIMIT 1""", (EXPIRED_REASON, jobdesk_id)).fetchone()


def revoke_access(c, jobdesk_id: int, reason: str) -> int:
    """Cabut akses aktif jobdesk: token node langsung mati, agen memutus sesi SSH & menghapus user."""
    rows = c.execute("""
        UPDATE node_access SET status = 'revoked', revoked_at = now(), revoked_reason = %s
        WHERE jobdesk_id = %s AND status = 'active' RETURNING username, node""",
        (reason[:200], jobdesk_id)).fetchall()
    for r in rows:
        project._event(c, jobdesk_id, "sistem", "akses_node_dicabut",
                       f"user {r['username']} di {r['node'] or '-'}: {reason}")
        log(f"akses {r['username']} dicabut ({reason})")
    return len(rows)


def ssh_endpoints(c=None) -> dict:
    """Alamat SSH: LAN (NODE_SSH_HOST + port tiap node) dan internet (tunnel per node dari head-online)."""
    online = {}
    try:
        own = c is None
        c = c or db()
        rows = c.execute("SELECT key, value FROM settings WHERE key LIKE 'public_ssh_host%%'").fetchall()
        if own:
            c.close()
        for r in rows:   # 'public_ssh_host' (lama, = node1) atau 'public_ssh_host:<node>'
            online[r["key"].split(":", 1)[1] if ":" in r["key"] else "node1"] = r["value"]
    except Exception:
        pass
    return {"host": SSH_HOST, "port": SSH_PORT, "online_hosts": online}


def access_for_volunteer(c, jobdesk_id: int) -> dict | None:
    """Info akses node untuk kartu jobdesk di dashboard relawan."""
    a = c.execute("""
        SELECT a.id, a.username, a.password AS token, a.node, a.provisioned_at, a.last_login_at, a.sessions,
               a.created_at, a.expires_at, a.parked_at, a.last_node, n.last_seen AS node_seen, n.ssh_port,
               coalesce((now() - n.last_seen) < make_interval(secs => %s), false) AS node_online
        FROM node_access a LEFT JOIN nodes n ON n.name = a.node
        WHERE a.jobdesk_id = %s AND a.status = 'active' AND (a.expires_at IS NULL OR a.expires_at > now())
        ORDER BY a.id DESC LIMIT 1""",
        (DEAD_SECONDS, jobdesk_id)).fetchone()
    if not a:
        return None
    ep = ssh_endpoints(c)
    p = a.pop("ssh_port") or ep["port"]
    port = "" if p == 22 else f"-p {p} "
    online = ep["online_hosts"].get(a["node"] or "")
    a["ready"] = bool(a["node"] and a["provisioned_at"] and a["node_online"])
    a["parked"] = bool(not a["node"] and a["parked_at"])   # dilepas karena tidak aktif: MASUK LAGI KE NODE
    a["idle_minutes"] = max(1, IDLE_SECONDS // 60) if IDLE_SECONDS else 0
    a["ssh_command"] = f"ssh {port}{a['username']}@{ep['host']}"
    a["ssh_online_command"] = (f'ssh -o ProxyCommand="cloudflared access ssh --hostname %h" '
                               f"{a['username']}@{online}") if online else None
    return a


def rotate_token(c, worker_id: str, jobdesk_id: int) -> str:
    """Token node baru (password ssh + git). Batas umur tidak diperpanjang."""
    token = new_token()
    r = c.execute("""UPDATE node_access SET password = %s, git_token = %s WHERE jobdesk_id = %s AND worker_id = %s
                     AND status = 'active' AND (expires_at IS NULL OR expires_at > now())
                     RETURNING password""", (token, token, jobdesk_id, worker_id)).fetchone()
    if not r:
        raise HTTPException(404, "Jobdesk ini tidak punya akses compute node aktif.")
    project._event(c, jobdesk_id, "relawan", "akses_node",
                   "token node diganti (sesi SSH yang sedang jalan tetap; git di node memakai token baru)")
    return r["password"]


@router.post("/api/me/jobdesk/{jid}/node-code")
def rotate_node_token(jid: int, authorization: str = Header(None)):
    """Ganti token node (mis. bocor). Hanya lewat login website pemilik jobdesk."""
    w = check_volunteer_auth(authorization, web_only=True)["worker"]
    with db() as c:
        token = rotate_token(c, w["id"], jid)
    return {"ok": True, "token": token}


def resume_access(c, worker_id: str, jobdesk_id: int) -> dict:
    """
    MASUK LAGI KE NODE: akses yang dilepas karena tidak aktif mendapat node lagi (token tetap).
    Node terakhir diutamakan bila masih kosong. Semua node penuh -> 409 dengan pesan jelas.
    """
    with c.transaction():
        c.execute("SELECT pg_advisory_xact_lock(%s)", (PICK_LOCK,))
        a = c.execute("""SELECT id, username, node, last_node FROM node_access
                          WHERE jobdesk_id = %s AND worker_id = %s AND status = 'active'
                            AND (expires_at IS NULL OR expires_at > now()) FOR UPDATE""",
                      (jobdesk_id, worker_id)).fetchone()
        if not a:
            raise HTTPException(404, "Jobdesk ini tidak punya akses compute node aktif.")
        if a["node"]:
            return {"node": a["node"], "already": True}
        cap = capacity(c)
        node = None
        if cap["free"] > 0:
            if a["last_node"]:
                r = c.execute(f"SELECT f.name FROM ({_free_nodes_sql()}) f WHERE f.name = %s AND f.used < f.max_users",
                              (DEAD_SECONDS, a["last_node"])).fetchone()
                node = r["name"] if r else None
            node = node or pick_node(c)
        if not node:
            raise HTTPException(409, f"Semua compute node sedang dipakai ({cap['used']}/{cap['total']} relawan aktif). "
                                     "Jobdesk dan token node Anda tetap aman; coba lagi beberapa menit lagi.")
        c.execute("""UPDATE node_access SET node = %s, parked_at = NULL, provisioned_at = NULL, sessions = 0
                     WHERE id = %s""", (node, a["id"]))
        c.execute("UPDATE nodes SET last_assigned_at = now() WHERE name = %s", (node,))
        project._event(c, jobdesk_id, "relawan", "akses_node", f"{a['username']} masuk lagi ke compute node {node}")
    return {"node": node, "already": False}


@router.post("/api/me/jobdesk/{jid}/node-resume")
def resume_node(jid: int, authorization: str = Header(None)):
    """Tombol MASUK LAGI KE NODE (hanya lewat login website pemilik jobdesk)."""
    w = check_volunteer_auth(authorization, web_only=True)["worker"]
    with db() as c:
        r = resume_access(c, w["id"], jid)
    return {"ok": True, **r}


# =============================================================================
# Agen compute node (pull): sinkron daftar user
# =============================================================================

class SyncBody(BaseModel):
    name: str
    users: list[str] = []            # user jd* yang ada di node sekarang (sudah siap)
    sessions: dict[str, int] = {}    # jumlah sesi SSH yang sedang login per user
    idle: dict[str, int] = {}        # detik sejak aktivitas terakhir per user (terminal / CPU)
    max_users: int | None = None
    ssh_port: int | None = None      # port SSH node ini di laptop head (mis. 2222 / 2223)


def _check_node_token(auth: str | None) -> None:
    if not NODE_TOKEN:
        raise HTTPException(503, "NODE_TOKEN belum diisi di .env koordinator (jalankan ./hpc.sh head-up).")
    if not auth or not hmac.compare_digest(auth.encode(), f"Bearer {NODE_TOKEN}".encode()):
        raise HTTPException(401, "Token compute node tidak sah.")


@router.post("/api/node/agent/sync")
def agent_sync(body: SyncBody, request: Request, authorization: str = Header(None)):
    _check_node_token(authorization)
    name = body.name.strip()
    if not NODE_NAME_RE.match(name):
        raise HTTPException(400, "Nama node tidak valid.")
    ip = request.client.host if request.client else None
    cap = max(1, min(body.max_users or MAX_USERS, MAX_USERS))
    present = {u for u in body.users if USER_RE.match(u)}
    with db() as c:
        with c.transaction():
            port = body.ssh_port if body.ssh_port and 0 < body.ssh_port < 65536 else None
            c.execute("""INSERT INTO nodes (name, ip, last_seen, max_users, ssh_port) VALUES (%s, %s, now(), %s, %s)
                         ON CONFLICT (name) DO UPDATE SET ip = EXCLUDED.ip, last_seen = now(),
                                max_users = EXCLUDED.max_users, ssh_port = EXCLUDED.ssh_port""", (name, ip, cap, port))
            expire_due(c)   # token node yang melewati NODE_TOKEN_TTL_DAYS
            # Failover: akses di node yang mati dilepas, lalu diambil node yang masih hidup
            moved = c.execute("""
                UPDATE node_access a SET node = NULL, provisioned_at = NULL, sessions = 0
                FROM nodes n WHERE a.node = n.name AND a.status = 'active'
                  AND n.last_seen < now() - make_interval(secs => %s)
                RETURNING a.jobdesk_id, a.username, n.name AS dead""", (DEAD_SECONDS,)).fetchall()
            for m in moved:
                project._event(c, m["jobdesk_id"], "sistem", "akses_node",
                               f"compute node {m['dead']} mati: {m['username']} dipindah ke node lain")
            # Relawan tidak aktif terlalu lama: node dilepas (akses tetap aktif, token tetap)
            notices: dict[str, str] = {}
            if IDLE_SECONDS > 0:
                for u in sorted(present):
                    if int(body.idle.get(u, 0) or 0) < IDLE_SECONDS:
                        continue
                    p = c.execute("""UPDATE node_access SET node = NULL, provisioned_at = NULL, sessions = 0,
                                            parked_at = now(), last_node = %s
                                     WHERE node = %s AND username = %s AND status = 'active'
                                     RETURNING jobdesk_id""", (name, name, u)).fetchone()
                    if p:
                        mins = IDLE_SECONDS // 60
                        project._event(c, p["jobdesk_id"], "sistem", "akses_node",
                                       f"{u} tidak aktif {mins} menit: sesi diputus, {name} dilepas untuk relawan lain "
                                       "(jobdesk dan token tetap; MASUK LAGI KE NODE di website)")
                        notices[u] = (f"Sesi diputus: tidak ada aktivitas selama {mins} menit, compute node {name} "
                                      "dilepas untuk relawan lain. Jobdesk dan token node Anda TETAP. Folder kerja tetap "
                                      "ada. Untuk lanjut: tekan MASUK LAGI KE NODE di website, lalu ssh lagi.")
                        log(f"{u} di {name} tidak aktif, node dilepas")
                present -= set(notices)
            # Akses yang belum punya node (node penuh saat dibuat / node lamanya mati) diambil FIFO
            # (id terkecil dulu), hanya bila node ini yang paling longgar, sampai kapasitasnya.
            # Akses yang dilepas karena tidak aktif (parkir) TIDAK diambil: relawan yang meminta lagi.
            c.execute("SELECT pg_advisory_xact_lock(%s)", (PICK_LOCK,))
            mine = c.execute("SELECT count(*) AS n FROM node_access WHERE node = %s AND status = 'active'",
                             (name,)).fetchone()["n"]
            if mine < cap and pick_node(c) == name:
                got = c.execute("""
                    UPDATE node_access SET node = %s WHERE id IN (
                        SELECT id FROM node_access WHERE node IS NULL AND status = 'active' AND parked_at IS NULL
                        ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED)
                    RETURNING jobdesk_id, username""", (name, cap - mine)).fetchall()
                for g in got:
                    project._event(c, g["jobdesk_id"], "sistem", "akses_node", f"{g['username']} disiapkan di {name}")
            # User yang sudah dibuat agen = siap; catat sesi login
            for u in present:
                n_sess = max(0, int(body.sessions.get(u, 0)))
                c.execute("""UPDATE node_access SET provisioned_at = coalesce(provisioned_at, now()),
                                    sessions = %s,
                                    last_login_at = CASE WHEN %s > 0 THEN now() ELSE last_login_at END
                             WHERE node = %s AND username = %s AND status = 'active'""", (n_sess, n_sess, name, u))
            rows = c.execute("""
                SELECT a.username, a.uid, a.password, a.git_token, a.jobdesk_id, a.expires_at,
                       d.title, d.branch, w.name AS worker_name, w.username AS preferred,
                       w.github_username, w.email
                FROM node_access a JOIN jobdesks d ON d.id = a.jobdesk_id JOIN workers w ON w.id = a.worker_id
                WHERE a.node = %s AND a.status = 'active' AND w.status = 'active'
                  AND d.status IN ('in_progress', 'review')
                ORDER BY a.id""", (name,)).fetchall()
            # Folder rumah (volume /home bersama semua node) yang masih harus disimpan: semua akses aktif,
            # termasuk yang sedang di node lain / parkir. Selain ini dihapus agen (akses sudah dicabut).
            keep = [r["username"] for r in c.execute(
                "SELECT username FROM node_access WHERE status = 'active'").fetchall()]
    repo = project.PROJECT_REPO_URL.rsplit("/", 1)[-1].removesuffix(".git")
    return {"grants": [{
                "user": r["username"], "uid": r["uid"], "password": r["password"], "git_token": r["git_token"],
                "jobdesk_id": r["jobdesk_id"], "title": r["title"], "branch": r["branch"],
                "expires_at": r["expires_at"].strftime("%Y-%m-%d %H:%M UTC") if r["expires_at"] else None,
                "git_name": r["preferred"] or r["github_username"] or r["worker_name"],
                "git_email": r["email"] or f"{r['github_username'] or r['username']}@users.noreply.github.com",
            } for r in rows],
            "repo": {"name": repo, "url": project.PROJECT_REPO_URL, "default_branch": project.DEFAULT_BRANCH},
            "keep_users": keep, "notices": notices,
            "interval_s": 3, "token_ttl_days": TOKEN_TTL_DAYS, "idle_minutes": IDLE_SECONDS // 60}


# =============================================================================
# Akses relawan dari dalam node: token hpc_ng_ (Basic auth untuk git, Bearer untuk CLI 'jobdesk')
# =============================================================================

def _token_from(auth: str | None) -> str | None:
    if not auth:
        return None
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    if auth.startswith("Basic "):
        try:
            raw = base64.b64decode(auth[6:].strip()).decode()
        except Exception:
            return None
        return raw.split(":", 1)[1] if ":" in raw else raw
    return None


def _need_basic():
    return Response("Butuh login git (token compute node).\n", status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="hpc-compute-node"'})


def grant_from(c, auth: str | None, request: Request) -> dict | None:
    """Akses aktif pemilik token. Token hanya berlaku dari IP compute node yang terdaftar."""
    token = _token_from(auth)
    if not token or not token.startswith(TOKEN_PREFIX):
        return None
    g = c.execute("""
        SELECT a.id, a.jobdesk_id, a.username, a.worker_id, a.node, d.branch, d.status AS jd_status,
               w.github_username, w.name AS worker_name, w.status AS worker_status, n.ip AS node_ip
        FROM node_access a JOIN jobdesks d ON d.id = a.jobdesk_id JOIN workers w ON w.id = a.worker_id
        LEFT JOIN nodes n ON n.name = a.node
        WHERE a.git_token = %s AND a.status = 'active'
          AND (a.expires_at IS NULL OR a.expires_at > now())""", (token,)).fetchone()
    if not g or g["worker_status"] != "active" or g["jd_status"] not in ("in_progress", "review"):
        return None
    ip = request.client.host if request.client else None
    if not g["node_ip"] or ip != g["node_ip"]:
        log(f"token {g['username']} dipakai dari {ip}, bukan dari compute node-nya ({g['node_ip']}): ditolak")
        return None
    return g


@router.get("/api/node/me")
def node_me(request: Request, authorization: str = Header(None)):
    with db() as c:
        g = grant_from(c, authorization, request)
        if not g:
            raise HTTPException(401, "Akses compute node untuk jobdesk ini sudah dicabut atau tidak sah.")
        d = c.execute(project._JD_SQL + " WHERE d.id = %s", (g["jobdesk_id"],)).fetchone()
    keep = ("id", "title", "description", "kind", "credit", "status", "branch", "note", "last_sha",
            "last_ci_job", "last_ci_status", "pr_number", "pr_url")
    return {"jobdesk": {k: d[k] for k in keep}, "repo_url": project.PROJECT_REPO_URL,
            "require_ci_pass": project.REQUIRE_CI_PASS}


@router.post("/api/node/me/submit")
def node_submit(request: Request, authorization: str = Header(None)):
    """'jobdesk ajukan' di compute node: sama dengan tombol AJUKAN REVIEW di website (membuka PR)."""
    with db() as c:
        g = grant_from(c, authorization, request)
        if not g:
            raise HTTPException(401, "Akses compute node untuk jobdesk ini sudah dicabut atau tidak sah.")
        w = c.execute("SELECT id, name, github_username FROM workers WHERE id = %s", (g["worker_id"],)).fetchone()
    return project.do_submit(w, g["jobdesk_id"], actor=f"{w['name']} (compute node)")


# =============================================================================
# Gerbang git: proxy smart HTTP ke GitHub, push hanya ke branch jobdesk sendiri
# =============================================================================

def _pkt_lines(data: bytes, pos: int = 0):
    """Iterasi pkt-line: (payload | None untuk flush/delim, posisi berikutnya)."""
    while pos + 4 <= len(data):
        try:
            n = int(data[pos:pos + 4], 16)
        except ValueError:
            return
        if n < 4:   # 0000 flush, 0001 delim, 0002 response-end
            yield None, pos + 4
            pos += 4
            continue
        yield data[pos + 4:pos + n], pos + n
        pos += n


def _pkt(payload: bytes) -> bytes:
    return f"{len(payload) + 4:04x}".encode() + payload


def filter_advertisement(body: bytes, keep_refs: set[str]) -> bytes:
    """
    Iklan ref (protokol v0) hanya menampilkan HEAD + ref yang diizinkan (branch jobdesk + main),
    sehingga branch relawan lain tidak terlihat dari node. Kapabilitas dipindah ke baris pertama.
    """
    out, refs, caps, header_done = [], [], None, False
    for payload, _ in _pkt_lines(body):
        if not header_done:
            if payload is None:
                header_done = True
            else:
                out.append(_pkt(payload))
                if not payload.startswith(b"# service="):   # tanpa header (bukan smart HTTP GET)
                    out.pop()
                    header_done = True
                    refs.append(payload)
            continue
        if payload is None:
            break
        refs.append(payload)
    if out:
        out.append(b"0000")
    kept = []
    for line in refs:
        line = line.rstrip(b"\n")
        if b"\0" in line:
            line, cap = line.split(b"\0", 1)
            caps = caps if caps is not None else cap
        sha, _, ref = line.partition(b" ")
        name = ref.decode(errors="replace")
        if name == "HEAD" or name in keep_refs or name == "capabilities^{}":
            kept.append((sha, ref))
    if not any(r != b"capabilities^{}" for _, r in kept):
        kept = [(ZERO_SHA.encode(), b"capabilities^{}")]
    else:
        kept = [(s, r) for s, r in kept if r != b"capabilities^{}"]
    for i, (sha, ref) in enumerate(kept):
        line = sha + b" " + ref + (b"\0" + (caps or b"") if i == 0 else b"") + b"\n"
        out.append(_pkt(line))
    out.append(b"0000")
    return b"".join(out)


def parse_push_commands(body: bytes) -> tuple[list[tuple[str, str, str]], set[str]]:
    """Perintah update ref di awal request receive-pack: [(old, new, ref)], kapabilitas klien."""
    cmds, caps = [], set()
    for payload, _ in _pkt_lines(body):
        if payload is None:
            break
        line = payload.rstrip(b"\n")
        if line.startswith(b"shallow ") or line.startswith(b"push-cert"):
            continue
        if b"\0" in line:
            line, cap = line.split(b"\0", 1)
            caps |= set(cap.decode(errors="replace").split())
        parts = line.decode(errors="replace").split(" ")
        if len(parts) == 3:
            cmds.append((parts[0], parts[1], parts[2]))
    return cmds, caps


def reject_report(cmds, caps: set[str], reason: str, message: str) -> bytes:
    """Jawaban report-status: git menampilkan '! [remote rejected] ... (<reason>)' + pesan 'remote:'."""
    status = [_pkt(b"unpack ok\n")] + [_pkt(f"ng {ref} {reason}\n".encode()) for _, _, ref in cmds] + [b"0000"]
    inner = b"".join(status)
    if "side-band-64k" in caps or "side-band" in caps:
        msg = b"".join(_pkt(b"\x02" + f"{line}\n".encode()) for line in message.splitlines())
        return msg + _pkt(b"\x01" + inner) + b"0000"
    return inner


def _upstream(path: str, method: str, body: bytes | None, ctype: str | None, encoding: str | None):
    owner, name = project.parse_repo(project.PROJECT_REPO_URL)
    headers = {"User-Agent": "git/2.43.0 (hpc-node-gateway)", "Accept": "*/*"}
    if project.GIT_TOKEN:
        headers["Authorization"] = "Basic " + base64.b64encode(
            f"x-access-token:{project.GIT_TOKEN}".encode()).decode()
    if ctype:
        headers["Content-Type"] = ctype
    if encoding:
        headers["Content-Encoding"] = encoding
    req = urllib.request.Request(f"{GITHUB_GIT}/{owner}/{name}.git/{path}", data=body, method=method,
                                 headers=headers)
    try:
        return urllib.request.urlopen(req, timeout=300)
    except urllib.error.HTTPError as e:
        return e


def _stream(resp):
    try:
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            yield chunk
    finally:
        resp.close()


def _gate(request: Request, authorization: str | None):
    if not active():
        raise HTTPException(503, "Akses compute node tidak aktif (NODE_ACCESS / PROJECT_REPO_URL).")
    if not project.GIT_TOKEN:
        raise HTTPException(503, "PROJECT_GIT_TOKEN kosong: gerbang git tidak bisa meneruskan ke GitHub.")
    with db() as c:
        return grant_from(c, authorization, request)


def _allowed_refs(g: dict, push: bool = False) -> set[str]:
    refs = {f"refs/heads/{g['branch']}"}
    if READ_MAIN or push:   # untuk push, ujung main hanya dipakai menghitung isi pack (tidak bisa ditulis)
        refs.add(f"refs/heads/{project.DEFAULT_BRANCH}")
    return refs


def _allowed_tips(g: dict) -> set[str]:
    """SHA ujung ref yang boleh di-fetch dari node saat ini."""
    resp = _upstream("info/refs?service=git-upload-pack", "GET", None, None, None)
    body = resp.read()
    resp.close()
    keep = _allowed_refs(g)
    tips = set()
    for payload, _ in _pkt_lines(body):
        if not payload or payload.startswith(b"# service="):
            continue
        line = payload.rstrip(b"\n").split(b"\0", 1)[0].decode(errors="replace")
        sha, _, ref = line.partition(" ")
        if ref in keep:
            tips.add(sha)
    return tips


def parse_wants(body: bytes) -> list[str]:
    return [p.decode(errors="replace").split()[1] for p, _ in _pkt_lines(body)
            if p and p.startswith(b"want ") and len(p.split()) >= 2]


@router.get("/api/node/git/{repo}.git/info/refs")
def git_info_refs(repo: str, request: Request, service: str = "", authorization: str = Header(None)):
    if service not in ("git-upload-pack", "git-receive-pack"):
        raise HTTPException(403, "Hanya smart HTTP (git versi baru).")
    g = _gate(request, authorization)
    if not g:
        return _need_basic()
    # Tanpa header Git-Protocol -> GitHub menjawab protokol v0 (daftar ref lengkap) yang bisa disaring
    resp = _upstream(f"info/refs?service={service}", "GET", None, None, None)
    body = resp.read()
    resp.close()
    if resp.status != 200:
        log(f"info/refs {service} dari GitHub HTTP {resp.status}")
        raise HTTPException(502, f"GitHub menjawab HTTP {resp.status} (cek PROJECT_GIT_TOKEN).")
    return Response(filter_advertisement(body, _allowed_refs(g, push=service == "git-receive-pack")),
                    media_type=f"application/x-{service}-advertisement",
                    headers={"Cache-Control": "no-cache"})


@router.post("/api/node/git/{repo}.git/git-upload-pack")
async def git_upload_pack(repo: str, request: Request, authorization: str = Header(None)):
    g = await run_in_threadpool(_gate, request, authorization)
    if not g:
        return _need_basic()
    body = await request.body()
    raw = gzip.decompress(body) if request.headers.get("content-encoding") == "gzip" else body
    if request.headers.get("git-protocol", "").find("version=2") >= 0 or b"command=" in raw[:64]:
        raise HTTPException(400, "Gerbang hanya melayani protokol git v0.")
    wants = parse_wants(raw)
    if wants:
        tips = await run_in_threadpool(_allowed_tips, g)
        bad = [w for w in wants if w not in tips]
        if bad:
            log(f"fetch {g['username']} ditolak: commit di luar branch-nya ({bad[0][:7]})")
            raise HTTPException(403, "Hanya branch jobdesk Anda yang bisa di-fetch dari compute node.")
    resp = await run_in_threadpool(_upstream, "git-upload-pack", "POST", body, request.headers.get("content-type"),
                                   request.headers.get("content-encoding"))
    if resp.status != 200:
        raise HTTPException(502, f"GitHub menjawab HTTP {resp.status}.")
    return StreamingResponse(_stream(resp), media_type="application/x-git-upload-pack-result",
                             headers={"Cache-Control": "no-cache"})


@router.post("/api/node/git/{repo}.git/git-receive-pack")
async def git_receive_pack(repo: str, request: Request, authorization: str = Header(None)):
    g = await run_in_threadpool(_gate, request, authorization)
    if not g:
        return _need_basic()
    body = await request.body()
    if len(body) > MAX_PUSH_BYTES:
        raise HTTPException(413, "Push terlalu besar.")
    encoding = request.headers.get("content-encoding")
    if encoding == "gzip":
        body, encoding = gzip.decompress(body), None
    cmds, caps = parse_push_commands(body)
    branch_ref = f"refs/heads/{g['branch']}"
    bad = [ref for old, new, ref in cmds if ref != branch_ref]
    deleting = [ref for old, new, ref in cmds if new == ZERO_SHA]
    if not cmds or bad or deleting:
        why = (f"hanya boleh push ke {g['branch']}" if bad or not cmds else "branch jobdesk tidak boleh dihapus")
        await run_in_threadpool(_note_rejected, g, f"{', '.join(bad or deleting) or '-'}: {why}")
        log(f"push {g['username']} ditolak: {bad or deleting}")
        return Response(reject_report(cmds, caps, why.replace(" ", "-"),
                                      f"Compute node jobdesk #{g['jobdesk_id']}: {why}.\n"
                                      f"Pakai: git push origin {g['branch']}"),
                        media_type="application/x-git-receive-pack-result")
    resp = await run_in_threadpool(_upstream, "git-receive-pack", "POST", body,
                                   request.headers.get("content-type"), encoding)
    out = await run_in_threadpool(resp.read)
    resp.close()
    if resp.status != 200:
        log(f"receive-pack ke GitHub HTTP {resp.status}: {out[:200]!r}")
        raise HTTPException(502, f"GitHub menolak push (HTTP {resp.status}). Cek izin PROJECT_GIT_TOKEN.")
    if f"ok {branch_ref}".encode() in out:
        await run_in_threadpool(_after_push, g, cmds[0][1])
    return Response(out, media_type="application/x-git-receive-pack-result")


def _note_rejected(g: dict, detail: str) -> None:
    with db() as c:
        project._event(c, g["jobdesk_id"], g["username"], "push_ditolak", detail)


def _after_push(g: dict, sha: str) -> None:
    """Push diterima GitHub: langsung jadi job CI (tanpa menunggu webhook/polling)."""
    pusher = g["github_username"] or g["worker_name"]
    try:
        with db() as c:
            project.register_push(c, g["branch"], sha, "compute-node", pusher=pusher)
            c.execute("UPDATE repo_pushes SET pusher = %s WHERE branch = %s AND sha = %s",
                      (pusher, g["branch"], sha.lower()))
            project._event(c, g["jobdesk_id"], g["username"], "push", f"{sha[:7]} lewat compute node {g['node']}")
    except Exception as e:
        log(f"CI untuk push {g['branch']}@{sha[:7]} tertunda (polling akan mengambil): {e}")


# =============================================================================
# Admin: daftar compute node + akses
# =============================================================================

@router.get("/api/admin/nodes")
def admin_nodes(authorization: str = Header(None)):
    project._admin(authorization)
    with db() as c:
        nodes = c.execute("""
            SELECT n.name, n.ip, n.last_seen, n.max_users, n.ssh_port,
                   (now() - n.last_seen) < make_interval(secs => %s) AS online,
                   (SELECT count(*) FROM node_access a WHERE a.node = n.name AND a.status = 'active') AS users
            FROM nodes n ORDER BY n.name""", (DEAD_SECONDS,)).fetchall()
        access = c.execute("""
            SELECT a.id, a.jobdesk_id, a.username, a.node, a.status, a.sessions, a.created_at, a.parked_at, a.last_node,
                   a.provisioned_at, a.last_login_at, a.revoked_at, a.revoked_reason,
                   d.title, d.branch, d.status AS jobdesk_status, w.name AS worker_name, w.github_username
            FROM node_access a JOIN jobdesks d ON d.id = a.jobdesk_id JOIN workers w ON w.id = a.worker_id
            ORDER BY (a.status = 'active') DESC, a.id DESC LIMIT 100""").fetchall()
        cap = capacity(c)
    return {"enabled": ENABLED, "nodes": nodes, "access": access, "ssh": ssh_endpoints(),
            "capacity": cap, "git_token": bool(project.GIT_TOKEN)}


class RevokeBody(BaseModel):
    reason: str = ""


@router.post("/api/admin/jobdesks/{jid}/revoke-node")
def admin_revoke_node(jid: int, body: RevokeBody, authorization: str = Header(None)):
    """Cabut akses compute node secara manual (mis. disalahgunakan). Jobdesk tetap milik relawan."""
    who = project._admin(authorization)
    with db() as c:
        n = revoke_access(c, jid, f"dicabut admin {who}" + (f": {body.reason.strip()[:150]}" if body.reason.strip() else ""))
    if not n:
        raise HTTPException(404, "Jobdesk ini tidak punya akses compute node aktif.")
    return {"ok": True}


@router.post("/api/admin/jobdesks/{jid}/grant-node")
def admin_grant_node(jid: int, authorization: str = Header(None)):
    """Terbitkan ulang akses compute node untuk jobdesk aktif (setelah dicabut manual)."""
    who = project._admin(authorization)
    with db() as c:
        d = c.execute("SELECT id, worker_id, status FROM jobdesks WHERE id = %s", (jid,)).fetchone()
        if not d or d["status"] not in ("in_progress", "review") or not d["worker_id"]:
            raise HTTPException(409, "Hanya untuk jobdesk yang sedang dikerjakan / direview.")
        create_access(c, jid, d["worker_id"])
        ttl = f", berlaku {TOKEN_TTL_DAYS:g} hari" if TOKEN_TTL_DAYS > 0 else ""
        project._event(c, jid, who, "akses_node", f"akses compute node diterbitkan ulang oleh admin (token node baru{ttl})")
    return {"ok": True}
