"""
Agen compute node (root di dalam kontainer 'node').

Pull model, sama seperti worker: tiap beberapa detik agen menanyakan ke koordinator akses mana
yang harus ada di node ini (POST /api/node/agent/sync), lalu menyamakan keadaan:
  - akses baru     -> buat user Linux jd<id> (grup relawan), pasang TOKEN NODE sebagai password SSH
                      dan sebagai kredensial gerbang git (satu token per jobdesk), clone repo B HANYA
                      branch jobdesk itu;
  - akses dicabut  -> (disetujui / dibatalkan / token kedaluwarsa) putus semua sesi SSH user itu
                      (kill), hapus user + folder rumahnya + kontainer uji-nya.
  - tidak aktif    -> agen melaporkan lama tidak aktif tiap user (tidak ada ketikan / keluaran di
                      terminal, tidak ada proses yang memakai CPU). Lewat NODE_IDLE_MINUTES, koordinator
                      melepas node: sesi diputus + pesan di terminal, user dihapus dari node ini, tetapi
                      folder rumah DISIMPAN (volume /home dipakai bersama semua node) dan token tetap.
Layanan 'uji' (runner.py) berjalan di proses ini: relawan menjalankan kontainer testing di Docker
milik node (layanan dindN), tanpa pernah memegang socket Docker.
sshd dijalankan dan dijaga oleh agen ini. Kunci host SSH disimpan di volume agar tetap sama
setelah kontainer dibuat ulang (relawan tidak melihat peringatan "host key changed").

Variabel lingkungan:
  COORDINATOR_URL  alamat koordinator dari dalam jaringan docker (bawaan http://coordinator:8000)
  NODE_TOKEN       rahasia bersama dengan koordinator
  NODE_NAME        nama node (bawaan hostname kontainer)
  NODE_MAX_USERS   akses aktif maksimal di node ini (bawaan 1)
"""
import json
import os
import pwd
import re
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request

import runner   # layanan 'uji' (kontainer testing)

COORD = os.environ.get("COORDINATOR_URL", "http://coordinator:8000").rstrip("/")
TOKEN = os.environ.get("NODE_TOKEN", "")
NAME = os.environ.get("NODE_NAME", "").strip() or socket.gethostname()
MAX_USERS = int(os.environ.get("NODE_MAX_USERS", "1") or 1)
SSH_PUBLIC_PORT = int(os.environ.get("NODE_SSH_PUBLIC_PORT", "0") or 0)   # port node ini di laptop head
KEY_DIR = "/var/lib/hpc-node/ssh"
HOME_ROOT = "/home"
USER_RE = re.compile(r"^jd\d{1,9}$")
UID_MIN = 20000

applied: dict[str, str] = {}        # user -> password terakhir yang dipasang
clone_retry: dict[str, float] = {}  # user -> waktu boleh coba clone lagi
sshd: subprocess.Popen | None = None
activity: dict[str, tuple] = {}     # user -> (sidik aktivitas terakhir, sejak kapan tidak berubah)


def log(msg):
    print(f"[node {NAME}] {msg}", flush=True)


def run(cmd, check=True, user=None, cwd=None, inp=None, timeout=300):
    if user:
        cmd = ["runuser", "-u", user, "--"] + cmd
    r = subprocess.run(cmd, input=inp, text=True, capture_output=True, cwd=cwd, timeout=timeout,
                       env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "HOME": f"{HOME_ROOT}/{user}" if user else "/root",
                            "GIT_TERMINAL_PROMPT": "0", "LANG": "C.UTF-8"})
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:6])}: {(r.stderr or r.stdout).strip()[-400:]}")
    return r


# ---------------------------------------------------------------------------- sshd

def ensure_host_keys():
    os.makedirs(KEY_DIR, exist_ok=True)
    for kind, extra in (("ed25519", []), ("ecdsa", ["-b", "256"]), ("rsa", ["-b", "3072"])):
        path = f"{KEY_DIR}/ssh_host_{kind}_key"
        if not os.path.exists(path):
            run(["ssh-keygen", "-q", "-t", kind, *extra, "-N", "", "-f", path])
            log(f"kunci host {kind} dibuat")
        os.chmod(path, 0o600)


def keep_sshd():
    global sshd
    if sshd is None or sshd.poll() is not None:
        if sshd is not None:
            log(f"sshd berhenti (kode {sshd.returncode}), dijalankan ulang")
        sshd = subprocess.Popen(["/usr/sbin/sshd", "-D", "-e"])


# ---------------------------------------------------------------------------- user

def present_users() -> list[str]:
    return sorted(p.pw_name for p in pwd.getpwall() if USER_RE.match(p.pw_name) and p.pw_uid >= UID_MIN)


def session_counts() -> dict[str, int]:
    """Jumlah sesi SSH per user (proses 'sshd: jd12@pts/0' / 'sshd-session: ...' milik user itu)."""
    out = run(["ps", "-eo", "user:32=,args="], check=False).stdout
    counts: dict[str, int] = {}
    for line in out.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and USER_RE.match(parts[0]) and re.match(r"^sshd(-session)?: ", parts[1]):
            counts[parts[0]] = counts.get(parts[0], 0) + 1
    return counts


def activity_fingerprint(uid: int) -> tuple:
    """
    Sidik aktivitas user: waktu baca/tulis terminal (pts) miliknya + total waktu CPU prosesnya,
    KECUALI proses sshd (keepalive SSH bukan aktivitas). Berubah = relawan masih bekerja.
    """
    ptys = []
    try:
        names = os.listdir("/dev/pts")
    except OSError:
        names = []
    for n in names:
        if n.isdigit():
            try:
                st = os.stat(f"/dev/pts/{n}")
            except OSError:
                continue
            if st.st_uid == uid:
                ptys.append((n, int(max(st.st_atime, st.st_mtime))))
    cpu = 0
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            if os.stat(f"/proc/{pid}").st_uid != uid:
                continue
            with open(f"/proc/{pid}/stat") as f:
                data = f.read()
        except OSError:
            continue
        end = data.rfind(")")
        if data[data.find("(") + 1:end].startswith("sshd"):
            continue
        fields = data[end + 2:].split()
        cpu += int(fields[11]) + int(fields[12])   # utime + stime
    return tuple(sorted(ptys)), cpu


def idle_seconds(users: list[str]) -> dict[str, int]:
    now = time.time()
    out = {}
    for u in users:
        try:
            fp = activity_fingerprint(pwd.getpwnam(u).pw_uid)
        except KeyError:
            continue
        old = activity.get(u)
        if not old or old[0] != fp:
            activity[u] = (fp, now)
        out[u] = int(now - activity[u][1])
    for u in list(activity):
        if u not in users:
            activity.pop(u)
    return out


def tell_user(user: str, text: str):
    """Tulis pesan ke semua terminal user (sebelum sesinya diputus)."""
    try:
        uid = pwd.getpwnam(user).pw_uid
    except KeyError:
        return
    for n in os.listdir("/dev/pts"):
        if not n.isdigit():
            continue
        try:
            if os.stat(f"/dev/pts/{n}").st_uid != uid:
                continue
            fd = os.open(f"/dev/pts/{n}", os.O_WRONLY | os.O_NOCTTY | os.O_NONBLOCK)
            try:
                os.write(fd, ("\r\n\r\n*** " + text + " ***\r\n\r\n").encode())
            finally:
                os.close(fd)
        except OSError:
            pass


def write_file(path: str, content: str, user: str, mode: int = 0o600):
    try:
        with open(path) as f:
            same = f.read() == content      # tidak berubah: jangan timpa tiap putaran
    except OSError:
        same = False
    if not same:
        with open(path, "w") as f:
            f.write(content)
    shutil.chown(path, user, "relawan")
    os.chmod(path, mode)


def motd(g: dict, repo: dict, cloned: bool, err: str | None) -> str:
    line = "=" * 64
    lines = [line, f" COMPUTE NODE {NAME}  -  jobdesk #{g['jobdesk_id']}: {g['title']}"[:100], line,
             f" Folder kerja : ~/{repo['name']}   (branch {g['branch']})"]
    if not cloned:
        lines.append(f" Repo belum bisa di-clone, dicoba lagi otomatis. ({(err or '')[:120]})")
    lines += [" Simpan kerja : git add -A && git commit -m \"pesan\" && git push",
              " Hanya branch ini yang bisa di-push. Setiap push otomatis di-CI.",
              " Status       : jobdesk          Ajukan review: jobdesk ajukan",
              " Testing pakai kontainer (mis. app + database): uji   (lihat bantuan)",
              " Setelah admin menyetujui, akses node ini berakhir otomatis."]
    if g.get("expires_at"):
        lines.append(f" Token node berlaku sampai {g['expires_at']}; setelah itu minta admin menerbitkan ulang.")
    if g.get("idle_minutes"):
        lines.append(f" Tidak aktif {g['idle_minutes']} menit = sesi diputus & node dilepas (jobdesk, token, folder tetap).")
    lines += [line, ""]
    return "\n".join(lines) + "\n"


def ensure_user(g: dict, repo: dict):
    user, uid, home = g["user"], int(g["uid"]), f"{HOME_ROOT}/{g['user']}"
    if not USER_RE.match(user) or uid < UID_MIN:
        return
    new = False
    try:
        pwd.getpwnam(user)
    except KeyError:
        run(["useradd", "-M", "-u", str(uid), "-g", "relawan", "-d", home, "-s", "/bin/bash", user])
        new = True
        log(f"user {user} dibuat untuk jobdesk #{g['jobdesk_id']}")
    if not os.path.isdir(home):
        os.makedirs(home)
    for f in (".bashrc", ".profile"):
        if os.path.exists(f"/etc/skel/{f}") and not os.path.exists(f"{home}/{f}"):
            shutil.copy(f"/etc/skel/{f}", f"{home}/{f}")
        if os.path.exists(f"{home}/{f}"):
            shutil.chown(f"{home}/{f}", user, "relawan")
    shutil.chown(home, user, "relawan")
    os.chmod(home, 0o700)
    token = g.get("token") or g["password"]   # satu token node: password ssh = token git
    if new or applied.get(user) != token:
        run(["chpasswd"], inp=f"{user}:{token}\n")
        applied[user] = token

    gw = COORD.split("://", 1)
    write_file(f"{home}/.git-credentials", f"{gw[0]}://{user}:{g['git_token']}@{gw[1]}\n", user)
    write_file(f"{home}/.gitconfig",
               f"[user]\n\tname = {g['git_name']}\n\temail = {g['git_email']}\n"
               "[credential]\n\thelper = store\n[push]\n\tdefault = current\n"
               "[init]\n\tdefaultBranch = main\n[pull]\n\trebase = false\n", user, 0o644)
    write_file(f"{home}/.hpc-node", json.dumps({"coordinator": COORD, "token": g["git_token"],
                                                 "jobdesk_id": g["jobdesk_id"], "branch": g["branch"]}), user)

    workdir = f"{home}/{repo['name']}"
    err = None
    if not os.path.isdir(f"{workdir}/.git") and time.time() >= clone_retry.get(user, 0):
        try:
            clone(user, g["branch"], repo, workdir)
        except Exception as e:
            err = str(e)
            clone_retry[user] = time.time() + 30
            shutil.rmtree(workdir, ignore_errors=True)
            log(f"clone untuk {user} gagal: {err}")
    write_file(f"{home}/.hpc-motd", motd(g, repo, os.path.isdir(f"{workdir}/.git"), err), user, 0o644)


def clone(user: str, branch: str, repo: dict, workdir: str):
    url = f"{COORD}/api/node/git/{repo['name']}.git"
    main = repo["default_branch"]
    r = run(["git", "clone", "--single-branch", "--branch", branch, url, workdir], check=False, user=user)
    if r.returncode != 0:
        # Branch belum ada di GitHub (dibuat manual tanpa token): mulai dari main, push pertama membuatnya
        shutil.rmtree(workdir, ignore_errors=True)
        run(["git", "clone", "--single-branch", "--branch", main, url, workdir], user=user)
        run(["git", "switch", "-c", branch], user=user, cwd=workdir)
    git = lambda *a: run(["git", *a], user=user, cwd=workdir)
    # 'git push' selalu ke branch jobdesk; 'git fetch' juga mengambil main (untuk git merge origin/main)
    git("config", "remote.origin.push", f"refs/heads/{branch}:refs/heads/{branch}")
    git("config", "--add", "remote.origin.fetch", f"+refs/heads/{main}:refs/remotes/origin/{main}")
    git("config", f"branch.{branch}.remote", "origin")
    git("config", f"branch.{branch}.merge", f"refs/heads/{branch}")
    log(f"repo {repo['name']} branch {branch} di-clone untuk {user}")


def remove_user(user: str, why: str, keep_home: bool):
    run(["pkill", "-KILL", "-u", user], check=False)
    time.sleep(0.3)
    run(["userdel", "-f", user], check=False)
    if not keep_home:
        shutil.rmtree(f"{HOME_ROOT}/{user}", ignore_errors=True)
    applied.pop(user, None)
    clone_retry.pop(user, None)
    activity.pop(user, None)
    log(f"user {user} dihapus dari node ini, semua sesinya diputus ({why})"
        + ("; folder rumah disimpan" if keep_home else ""))


_tidy_lock = threading.Lock()


def tidy_docker(keep: set[str]):
    """Kontainer uji user yang tidak lagi di node ini dihapus (di thread: Docker bisa lambat)."""
    def work():
        if _tidy_lock.acquire(blocking=False):
            try:
                runner.tidy(keep)
            except Exception as e:
                log(f"membersihkan kontainer uji gagal: {e}")
            finally:
                _tidy_lock.release()
    threading.Thread(target=work, daemon=True).start()


# ---------------------------------------------------------------------------- loop

def sync(users: list[str]) -> dict:
    body = json.dumps({"name": NAME, "users": users, "sessions": session_counts(), "idle": idle_seconds(users),
                       "max_users": MAX_USERS, "ssh_port": SSH_PUBLIC_PORT or None}).encode()
    req = urllib.request.Request(f"{COORD}/api/node/agent/sync", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def main():
    if not TOKEN:
        log("NODE_TOKEN kosong. Isi di .env head lalu jalankan ulang (./hpc.sh head-up).")
    ensure_host_keys()
    keep_sshd()
    for d in ("/run/hpc-docker", "/var/lib/hpc-node"):   # socket Docker uji + kunci host: hanya root
        if os.path.isdir(d):
            os.chmod(d, 0o700)
    threading.Thread(target=runner.serve, daemon=True).start()
    log(f"siap, koordinator {COORD}, maks {MAX_USERS} relawan")
    interval, warned, last_tidy = 3, 0.0, 0.0
    while True:
        keep_sshd()
        try:
            state = sync(present_users())
            interval = state.get("interval_s", 3)
            grants = {g["user"]: g for g in state["grants"]}
            # Folder rumah ada di volume bersama semua node: hanya dihapus bila aksesnya sudah dicabut
            keep = set(state.get("keep_users", grants)) | set(grants)
            for g in grants.values():
                g.setdefault("idle_minutes", state.get("idle_minutes"))
                try:
                    ensure_user(g, state["repo"])
                except Exception as e:
                    log(f"menyiapkan {g['user']} gagal: {e}")
            removed = False
            for user in present_users():
                if user not in grants:
                    note = (state.get("notices") or {}).get(user)
                    tell_user(user, note or "Akses compute node ini berakhir (jobdesk disetujui / dibatalkan / dicabut).")
                    time.sleep(0.2)
                    remove_user(user, "tidak aktif, node dilepas" if note else "akses dicabut / dipindah",
                                keep_home=user in keep)
                    removed = True
            for d in os.listdir(HOME_ROOT):   # sisa folder rumah dari akses yang sudah dicabut
                if USER_RE.match(d) and d not in keep:
                    shutil.rmtree(f"{HOME_ROOT}/{d}", ignore_errors=True)
            if removed or time.time() - last_tidy > 60:
                last_tidy = time.time()
                tidy_docker(set(grants))
        except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
            if time.time() - warned > 60:
                log(f"koordinator belum bisa dihubungi: {e}")
                warned = time.time()
        time.sleep(interval)


if __name__ == "__main__":
    main()
