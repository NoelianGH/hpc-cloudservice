#!/usr/bin/env python3
"""
Layanan 'uji' di compute node: relawan menjalankan BANYAK KONTAINER untuk testing (mis. aplikasi +
database) tanpa pernah memegang Docker.

Setiap compute node punya Docker sendiri (layanan dindN di docker-compose, Docker-in-Docker),
terpisah dari Docker host yang menjalankan koordinator / database. Socket Docker itu hanya bisa
dibuka root di node (folder /run/hpc-docker 0700). Relawan memakai perintah 'uji' (node/uji): uji
mengirim permintaannya ke layanan ini lewat /run/hpc-uji.sock beserta terminalnya (file descriptor).
Layanan ini (root, dijalankan agent.py) memeriksa siapa pengirimnya (SO_PEERCRED: user jd<id>),
menyusun perintah docker sendiri dengan batas yang tidak bisa diubah relawan, lalu menjalankannya
langsung di terminal relawan:
  - tanpa --privileged, tanpa mount folder / socket host, tanpa publish port, tanpa --network host,
    no-new-privileges, beberapa capability dibuang, batas RAM / CPU / jumlah proses per kontainer,
    maksimal NODE_TEST_MAX_CONTAINERS kontainer per relawan;
  - kode relawan DISALIN ke /work di kontainer (tar dibuat sebagai user relawan sendiri, jadi hanya
    file yang memang bisa ia baca), bukan di-mount;
  - semua kontainer relawan ada di jaringan hpc-<user> sendiri, saling memanggil lewat nama
    (mis. aplikasi menghubungi 'db');
  - kontainer, jaringan, dan image buatan relawan dihapus saat aksesnya di node ini berakhir
    (tidak aktif / disetujui / dicabut).

Docker uji tidak bisa menghubungi koordinator / database / node lain (jaringan docker berbeda) dan
tidak pernah melihat PROJECT_GIT_TOKEN maupun NODE_TOKEN.
"""
import json
import os
import pwd
import re
import secrets
import select
import socket
import struct
import subprocess
import sys
import threading
import time

SOCK = "/run/hpc-uji.sock"
DOCKER_DIR = "/run/hpc-docker"                       # volume bersama dengan layanan dindN
DOCKER_SOCK = f"{DOCKER_DIR}/docker.sock"
DOCKER = "/opt/hpc/docker/docker"                    # CLI docker, hanya root (folder 0700)
MAX_CONT = int(os.environ.get("NODE_TEST_MAX_CONTAINERS", "5") or 5)
MEM = os.environ.get("NODE_TEST_CONTAINER_MEMORY", "1g")
CPUS = os.environ.get("NODE_TEST_CONTAINER_CPUS", "1")
PIDS = int(os.environ.get("NODE_TEST_CONTAINER_PIDS", "512") or 512)
UID_MIN = 20000

USER_RE = re.compile(r"^jd\d{1,9}$")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,30}$")
IMAGE_RE = re.compile(r"^[a-z0-9][a-z0-9._/-]{0,150}(:[A-Za-z0-9_][A-Za-z0-9_.-]{0,127})?(@sha256:[a-f0-9]{64})?$")
HEX_ID_RE = re.compile(r"^(sha256:)?[a-f0-9]{12,64}$")
ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
FILE_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]{0,120}$")
LOCAL = "lokal/"

HELP = f"""uji - menjalankan kontainer untuk testing di compute node ini (Docker milik node, terpisah).

  uji jalan [opsi] IMAGE [PERINTAH...]   jalankan kontainer; kode di folder ini disalin ke /work
      --nama NAMA     nama kontainer (kontainer lain memanggilnya lewat nama ini, mis. db)
      --latar         jalan di latar belakang (mis. database); tanpa ini: tampil di terminal, lalu dihapus
      -e KUNCI=NILAI  variabel lingkungan (boleh berulang)
      --tanpa-kode    jangan salin kode ke /work
  uji bangun NAMA [--file Dockerfile]    build image dari folder ini -> dipakai sebagai lokal/NAMA
  uji daftar                             kontainer Anda
  uji log NAMA [-f]                      log kontainer
  uji masuk NAMA [PERINTAH...]           buka shell / jalankan perintah di kontainer (bawaan: sh)
  uji hapus NAMA | semua                 hentikan + hapus kontainer
  uji gambar                             image yang Anda build

Contoh (aplikasi + PostgreSQL):
  uji jalan --nama db --latar -e POSTGRES_PASSWORD=rahasia postgres:16-alpine
  uji bangun app
  uji jalan -e DATABASE_URL=postgresql://postgres:rahasia@db/postgres lokal/app pytest

Batas: maks {MAX_CONT} kontainer, RAM {MEM} dan {CPUS} CPU per kontainer. Tanpa --privileged, mount folder,
atau publish port. Semua kontainer dihapus saat sesi node berakhir (tidak aktif / jobdesk selesai);
yang tersimpan hanya kode di folder rumah Anda.
"""

_lock = threading.Lock()


class UjiError(Exception):
    pass


def denv() -> dict:
    return {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/root",
            "DOCKER_HOST": f"unix://{DOCKER_SOCK}", "DOCKER_CONFIG": "/opt/hpc/docker", "LANG": "C.UTF-8"}


def docker(*args, timeout=120, check=False) -> subprocess.CompletedProcess:
    r = subprocess.run([DOCKER, *args], env=denv(), capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise UjiError((r.stderr or r.stdout).strip()[-400:])
    return r


def ready() -> bool:
    if not os.path.exists(DOCKER_SOCK):
        return False
    try:
        return docker("version", "--format", "{{.Server.Version}}", timeout=10).returncode == 0
    except Exception:
        return False


def log(msg):
    print(f"[uji] {msg}", flush=True)


# ---------------------------------------------------------------------------- nama & aturan

def cont_name(user: str, nama: str) -> str:
    nama = nama.removeprefix(f"{user}-")
    if not NAME_RE.match(nama):
        raise UjiError("Nama kontainer: huruf kecil / angka / . _ - (maks 31 karakter).")
    return f"{user}-{nama}"


def own_container(user: str, nama: str) -> str:
    c = cont_name(user, nama)
    r = docker("inspect", "--format", '{{index .Config.Labels "hpc.user"}}', c)
    if r.returncode != 0 or r.stdout.strip() != user:
        raise UjiError(f"Kontainer '{nama}' tidak ada. Lihat: uji daftar")
    return c


def image_for(user: str, image: str) -> str:
    if image.startswith(LOCAL):
        nama = image[len(LOCAL):].split(":", 1)[0]
        if not NAME_RE.match(nama):
            raise UjiError("Nama image lokal tidak valid.")
        return f"{LOCAL}{user}-{nama}"
    if HEX_ID_RE.match(image) or not IMAGE_RE.match(image):
        raise UjiError(f"Nama image tidak valid: {image[:80]}")
    return image


def count_containers(user: str) -> int:
    r = docker("ps", "-aq", "--filter", f"label=hpc.user={user}")
    return len(r.stdout.split())


def ensure_network(user: str) -> str:
    net = f"hpc-{user}"
    if docker("network", "inspect", net).returncode != 0:
        docker("network", "create", "--label", f"hpc.user={user}", net, check=True)
    return net


def workdir_ok(user: str, cwd: str) -> str:
    home = os.path.realpath(pwd.getpwnam(user).pw_dir)
    real = os.path.realpath(cwd or home)
    if real != home and not real.startswith(home + "/"):
        raise UjiError(f"Jalankan uji dari folder di dalam {home} (mis. folder repo Anda).")
    return real


def tar_as_user(user: str, cwd: str, prefix: str | None) -> subprocess.Popen:
    """tar folder kerja SEBAGAI USER RELAWAN (bukan root): hanya file yang memang bisa ia baca."""
    cmd = ["runuser", "-u", user, "--", "tar", "-C", cwd, "--exclude=./.git", "-cf", "-"]
    if prefix:
        cmd.append(f"--transform=s,^\\.,{prefix},")
    cmd.append(".")
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"})


# ---------------------------------------------------------------------------- perintah

def run_attached(argv: list[str], fds: list[int], conn: socket.socket, on_abort=None, stdin=None) -> int:
    """Jalankan docker langsung di terminal relawan; bila 'uji' dihentikan (Ctrl+C), docker ikut dihentikan."""
    p = subprocess.Popen([DOCKER, *argv], env=denv(), stdin=stdin if stdin is not None else fds[0],
                         stdout=fds[1], stderr=fds[2])
    while p.poll() is None:
        r, _, _ = select.select([conn], [], [], 0.5)
        if r:
            try:
                gone = conn.recv(1, socket.MSG_PEEK) == b""
            except OSError:
                gone = True
            if gone:
                p.kill()
                if on_abort:
                    on_abort()
                return 130
    return p.returncode


def cmd_jalan(user: str, args: list[str], cwd: str, tty: bool, fds, conn, say) -> int:
    nama, latar, kode, env = None, False, True, []
    i = 0
    while i < len(args) and args[i].startswith("-"):
        a = args[i]
        if a in ("--nama", "--name") and i + 1 < len(args):
            nama = args[i + 1]; i += 2; continue
        if a in ("--latar", "-d", "--detach"):
            latar = True; i += 1; continue
        if a == "--tanpa-kode":
            kode = False; i += 1; continue
        if a in ("-e", "--env") and i + 1 < len(args):
            k, _, v = args[i + 1].partition("=")
            if not ENV_KEY_RE.match(k) or len(v) > 4096 or "\0" in v:
                raise UjiError(f"Variabel lingkungan tidak valid: {args[i + 1][:60]}")
            env += ["-e", f"{k}={v}"]; i += 2; continue
        raise UjiError(f"Opsi tidak dikenal / tidak diizinkan: {a}. Lihat: uji")
    if i >= len(args):
        raise UjiError("Sebutkan image, mis. uji jalan python:3.12-slim python -V")
    image, command = image_for(user, args[i]), args[i + 1:]
    if latar and not nama:
        raise UjiError("Kontainer latar perlu --nama (agar bisa dipanggil / dilihat lognya).")
    nama = nama or f"run-{secrets.token_hex(3)}"
    cname = cont_name(user, nama)
    work = workdir_ok(user, cwd) if kode else None
    with _lock:
        if count_containers(user) >= MAX_CONT:
            raise UjiError(f"Maksimal {MAX_CONT} kontainer. Hapus yang tidak dipakai: uji daftar / uji hapus NAMA")
        if docker("inspect", cname).returncode == 0:
            raise UjiError(f"Nama '{nama}' sudah dipakai. Hapus dulu: uji hapus {nama}")
        net = ensure_network(user)
        create = ["create", "--name", cname, "--label", f"hpc.user={user}", "--label", f"hpc.nama={nama}",
                  "--network", net, "--network-alias", nama, "--hostname", nama,
                  "--memory", MEM, "--memory-swap", MEM, "--cpus", CPUS, "--pids-limit", str(PIDS),
                  "--security-opt", "no-new-privileges",
                  "--cap-drop", "NET_RAW", "--cap-drop", "MKNOD", "--cap-drop", "AUDIT_WRITE", "--cap-drop", "SETFCAP",
                  "--ulimit", "nofile=4096:4096", "--log-opt", "max-size=5m", "--log-opt", "max-file=1", *env]
        if work:
            create += ["-w", "/work"]
        if not latar:
            create += ["-i"] + (["-t"] if tty else [])
        create += [image, *command]
        # 'docker create' mengunduh image bila belum ada (progres tampil di terminal relawan)
        p = subprocess.run([DOCKER, *create], env=denv(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=fds[2], text=True)
        if p.returncode != 0:
            return p.returncode
    remove = lambda: docker("rm", "-fv", cname)
    try:
        if work:
            t = tar_as_user(user, work, "work")
            cp = subprocess.run([DOCKER, "cp", "-", f"{cname}:/"], env=denv(), stdin=t.stdout,
                                capture_output=True, text=True)
            t.stdout.close()
            t.wait()
            if cp.returncode != 0 or t.returncode not in (0, 1):   # tar 1 = file berubah saat dibaca
                raise UjiError("Gagal menyalin kode ke kontainer: " + (cp.stderr or t.stderr.read().decode()).strip()[-300:])
        if latar:
            docker("start", cname, check=True)
            say(f"Kontainer '{nama}' berjalan di latar ({image}). Dipanggil kontainer lain dengan nama '{nama}'.\n"
                f"Log: uji log {nama}    Masuk: uji masuk {nama}    Hentikan: uji hapus {nama}\n")
            return 0
        return run_attached(["start", "-a", "-i", cname], fds, conn, on_abort=remove)
    except Exception:
        remove()
        raise
    finally:
        if not latar:
            remove()


def cmd_bangun(user: str, args: list[str], cwd: str, fds, conn) -> int:
    if not args or args[0].startswith("-"):
        raise UjiError("Pakai: uji bangun NAMA [--file Dockerfile]")
    nama, dockerfile = args[0], "Dockerfile"
    if not NAME_RE.match(nama):
        raise UjiError("Nama image: huruf kecil / angka / . _ -")
    rest = args[1:]
    if rest[:1] in (["--file"], ["-f"]) and len(rest) == 2:
        dockerfile = rest[1]
        rest = []
    if rest or not FILE_RE.match(dockerfile) or ".." in dockerfile.split("/"):
        raise UjiError("Pakai: uji bangun NAMA [--file path/Dockerfile]")
    work = workdir_ok(user, cwd)
    if not os.path.isfile(os.path.join(work, dockerfile)):
        raise UjiError(f"{dockerfile} tidak ada di folder ini ({work}).")
    t = tar_as_user(user, work, None)
    code = run_attached(["build", "-t", f"{LOCAL}{user}-{nama}", "--label", f"hpc.user={user}", "-f", dockerfile, "-"],
                        fds, conn, stdin=t.stdout)
    t.stdout.close()
    t.wait()
    if code == 0:
        os.write(fds[1], f"Image siap: lokal/{nama}   Jalankan: uji jalan lokal/{nama} ...\n".encode())
    return code


def handle(conn: socket.socket):
    fds: list[int] = []
    try:
        pid, uid, gid = struct.unpack("3i", conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
        msg, fds, _, _ = socket.recv_fds(conn, 65536, 3)
        try:
            user = pwd.getpwuid(uid).pw_name
        except KeyError:
            user = ""
        if uid < UID_MIN or not USER_RE.match(user) or len(fds) != 3:
            conn.sendall(b'{"code": 126}')
            return
        req = json.loads(msg.decode() or "{}")
        args = [str(a) for a in req.get("args", [])][:200]
        cwd, tty = str(req.get("cwd", "")), bool(req.get("tty"))
        say = lambda text: os.write(fds[1], text.encode())
        err = lambda text: os.write(fds[2], text.encode())
        try:
            if not args or args[0] in ("bantuan", "help", "-h", "--help"):
                say(HELP)
                code = 0
            elif not ready():
                err("Docker uji di node ini belum siap (layanan dind). Coba lagi sebentar, atau hubungi admin.\n")
                code = 1
            else:
                sub, rest = args[0], args[1:]
                if sub in ("jalan", "run"):
                    code = cmd_jalan(user, rest, cwd, tty, fds, conn, say)
                elif sub in ("bangun", "build"):
                    code = cmd_bangun(user, rest, cwd, fds, conn)
                elif sub in ("daftar", "ps"):
                    code = run_attached(["ps", "-a", "--filter", f"label=hpc.user={user}", "--format",
                                         'table {{.Label "hpc.nama"}}\t{{.Image}}\t{{.Status}}'], fds, conn)
                elif sub in ("log", "logs") and rest:
                    follow = ["-f"] if "-f" in rest[1:] else []
                    code = run_attached(["logs", "--tail", "200", *follow, own_container(user, rest[0])], fds, conn)
                elif sub in ("masuk", "exec") and rest:
                    c = own_container(user, rest[0])
                    code = run_attached(["exec", "-i", *(["-t"] if tty else []), c, *(rest[1:] or ["sh"])], fds, conn)
                elif sub in ("hapus", "rm", "stop") and rest:
                    if rest[0] == "semua":
                        tidy_user(user)
                        say("Semua kontainer Anda dihapus.\n")
                    else:
                        docker("rm", "-fv", own_container(user, rest[0]), check=True)
                        say(f"Kontainer '{rest[0]}' dihapus.\n")
                    code = 0
                elif sub in ("gambar", "images"):
                    code = run_attached(["images", "--filter", f"label=hpc.user={user}", "--format",
                                         "table {{.Repository}}\t{{.Size}}\t{{.CreatedSince}}"], fds, conn)
                else:
                    err("Perintah tidak dikenal. Lihat: uji\n")
                    code = 2
        except UjiError as e:
            err(f"uji: {e}\n")
            code = 1
        log(f"{user}: {' '.join(args[:3])[:80]} -> {code}")
        conn.sendall(json.dumps({"code": code}).encode())
    except Exception as e:
        log(f"permintaan gagal: {e}")
        try:
            if len(fds) == 3:
                os.write(fds[2], "uji: terjadi kesalahan di layanan uji node; coba lagi atau hubungi admin.\n".encode())
            conn.sendall(b'{"code": 1}')
        except OSError:
            pass
    finally:
        for fd in fds:
            try:
                os.close(fd)
            except OSError:
                pass
        conn.close()


# ---------------------------------------------------------------------------- pembersihan (dipanggil agen)

def tidy_user(user: str):
    ids = docker("ps", "-aq", "--filter", f"label=hpc.user={user}").stdout.split()
    if ids:
        docker("rm", "-fv", *ids, timeout=300)
    docker("network", "rm", f"hpc-{user}")
    imgs = [i for i in docker("images", "--format", "{{.Repository}}:{{.Tag}}").stdout.split()
            if i.startswith(f"{LOCAL}{user}-")]
    if imgs:
        docker("rmi", "-f", *imgs, timeout=300)


_last_prune = time.time()


def tidy(keep: set[str]):
    """Hapus kontainer / jaringan / image milik user yang tidak lagi punya akses di node ini."""
    global _last_prune
    if not ready():
        return
    users = set()
    for line in docker("ps", "-a", "--filter", "label=hpc.user", "--format", '{{.Label "hpc.user"}}').stdout.split():
        users.add(line)
    for line in docker("network", "ls", "--filter", "label=hpc.user", "--format", '{{.Label "hpc.user"}}').stdout.split():
        users.add(line)
    for img in docker("images", "--format", "{{.Repository}}").stdout.split():
        m = re.match(rf"^{LOCAL}(jd\d+)-", img)
        if m:
            users.add(m.group(1))
    for u in sorted(users - keep):
        if USER_RE.match(u):
            tidy_user(u)
            log(f"kontainer / image {u} dihapus (akses di node ini berakhir)")
    if time.time() - _last_prune > 6 * 3600:   # sisa build / image tanpa nama / volume tak terpakai
        _last_prune = time.time()
        docker("image", "prune", "-f", timeout=600)   # image dasar (python, postgres, ...) tetap di cache
        docker("builder", "prune", "-af", "--filter", "until=72h", timeout=600)
        docker("volume", "prune", "-f", timeout=300)


def serve():
    try:
        os.unlink(SOCK)
    except FileNotFoundError:
        pass
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(SOCK)
    os.chmod(SOCK, 0o666)   # siapa pun boleh menghubungi; identitas diperiksa lewat SO_PEERCRED
    s.listen(32)
    log(f"siap di {SOCK}")
    while True:
        conn, _ = s.accept()
        threading.Thread(target=handle, args=(conn,), daemon=True).start()


if __name__ == "__main__":
    serve()
