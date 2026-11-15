#!/usr/bin/env python3
"""
Pendaftaran relawan lewat terminal (dipanggil oleh './hpc.sh worker-login').

Alur: nama worker + username GitHub + email -> koordinator memeriksa akun GitHub
-> kode OTP dikirim ke email -> masukkan OTP -> WORKER_TOKEN & WORKER_ID pribadi
disimpan ke .env (dengan persetujuan Anda).

Hanya memakai pustaka standar Python 3.8+.
"""
import json
import os
import sys
import urllib.error
import urllib.request

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def read_env() -> dict:
    env = {}
    if os.path.exists(ENV_FILE):
        for line in open(ENV_FILE, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def set_env(values: dict) -> None:
    lines = open(ENV_FILE, encoding="utf-8").read().splitlines() if os.path.exists(ENV_FILE) else []
    done = set()
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in values and not line.lstrip().startswith("#"):
            lines[i] = f"{key}={values[key]}"
            done.add(key)
    lines += [f"{k}={v}" for k, v in values.items() if k not in done]
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def post(url: str, path: str, body: dict) -> dict:
    req = urllib.request.Request(url.rstrip("/") + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read()).get("detail")
        except Exception:
            detail = str(e)
        if isinstance(detail, dict):
            msg = detail.get("message", "")
            for reason in detail.get("reasons", []):
                msg += f"\n  - {reason}"
            detail = msg
        raise SystemExit(f"[DITOLAK] {detail}")
    except urllib.error.URLError as e:
        raise SystemExit(f"[ERROR] Koordinator {url} tidak dapat dihubungi: {e.reason}")


def ask(prompt: str, default: str = "") -> str:
    v = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return v or default


def main() -> int:
    env = read_env()
    url = env.get("COORDINATOR_URL", "http://localhost:8000").replace("host.docker.internal", "localhost")
    print("=== Pendaftaran relawan Cloud Service HPC ===")
    print(f"Koordinator: {url}\n")
    name = ask("Nama worker (tampil di leaderboard)", env.get("WORKER_NAME", ""))
    gh = ask("Username GitHub")
    email = ask("Email (untuk kode OTP)")

    r = post(url, "/api/auth/register-request", {"worker_name": name, "github_username": gh, "email": email})
    print(f"\n{r['message']} (skor GitHub {r.get('github_score')})")
    if r.get("dev_mode"):
        print(f"[MODE DEV] SMTP belum diatur, OTP = {r['dev_otp']}")

    for _ in range(5):
        otp = ask("Kode OTP (ketik 'ulang' untuk kirim ulang)")
        if otp.lower() == "ulang":
            rr = post(url, "/api/auth/resend-otp", {"session_id": r["session_id"]})
            print(rr["message"] + (f" [MODE DEV] OTP = {rr['dev_otp']}" if rr.get("dev_mode") else ""))
            continue
        try:
            v = post(url, "/api/auth/verify-otp", {"session_id": r["session_id"], "otp": otp})
            break
        except SystemExit as e:
            print(e)
    else:
        return 1

    print(f"\n{v['message']}\n  WORKER_ID    : {v['worker_id']}\n  WORKER_TOKEN : {v['worker_token']}")
    print("Simpan token ini; dipakai juga untuk login di dashboard relawan (web /login).")
    if ask("\nSimpan WORKER_TOKEN, WORKER_ID, WORKER_NAME ke .env? (y/n)", "y").lower().startswith("y"):
        set_env({"WORKER_TOKEN": v["worker_token"], "WORKER_ID": v["worker_id"], "WORKER_NAME": name})
        print(".env diperbarui. Jalankan: ./hpc.sh worker-up 1")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nDibatalkan.")
        sys.exit(130)
