#!/usr/bin/env python3
"""
worker_auth_cli.py - Antarmuka CLI untuk Autentikasi Relawan Compute Worker

Alur Autentikasi:
1. Input Nama Worker, Username GitHub, dan Alamat Email.
2. Head Node (Koordinator) memverifikasi profil GitHub (Anti-Fake Worker):
   - Usia akun minimal (default 30 hari).
   - Jumlah repositori publik minimal (default 2 repo).
   - Indikator reputasi tambahan (followers, profil, rasio spam).
3. Jika akun lolos, Head Node mengirimkan kode OTP ke email.
4. User memasukkan kode OTP ke CLI ini.
5. Head Node memverifikasi OTP dan menerbitkan WORKER_TOKEN unik.
6. CLI menawarkan untuk langsung menyimpan token ke file .env.
"""

import os
import sys
import json
import socket
import argparse
import urllib.request
import urllib.error

BANNER = r"""
======================================================================
           HPC CLOUD SERVICE - WORKER CLI AUTHENTICATION
======================================================================
  Verifikasi Identitas Relawan Komputasi via GitHub & Email OTP
======================================================================
"""

def read_env_file(filepath=".env"):
    """Membaca variabel dari file .env sederhana."""
    env = {}
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip().strip('"').strip("'")
        except Exception:
            pass
    return env

def update_env_file(filepath, updates):
    """Memperbarui atau menambahkan variabel ke file .env."""
    lines = []
    found_keys = set()
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            if k in updates:
                new_lines.append(f"{k}={updates[k]}\n")
                found_keys.add(k)
                continue
        new_lines.append(line)

    for k, v in updates.items():
        if k not in found_keys:
            new_lines.append(f"{k}={v}\n")

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

def post_json(url, path, body):
    endpoint = url.rstrip("/") + path
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = {"detail": err_body}
        return e.code, parsed
    except Exception as e:
        return 0, {"detail": str(e)}

def main():
    print(BANNER)
    
    env_vars = read_env_file()
    default_url = env_vars.get("COORDINATOR_URL", "http://localhost:8000")
    default_name = env_vars.get("WORKER_NAME", f"worker-{socket.gethostname()[:5]}")

    parser = argparse.ArgumentParser(description="HPC Cloud Service Worker Authentication CLI")
    parser.add_argument("--url", default=None, help="URL Coordinator (default: dari .env atau http://localhost:8000)")
    parser.add_argument("--name", default=None, help="Nama Worker")
    parser.add_argument("--github", default=None, help="Username GitHub")
    parser.add_argument("--email", default=None, help="Email untuk menerima kode OTP")
    args = parser.parse_args()

    # Tentukan parameter URL & Nama
    coord_url = args.url
    if not coord_url:
        val = input(f"[?] URL Koordinator [{default_url}]: ").strip()
        coord_url = val if val else default_url

    worker_name = args.name
    if not worker_name:
        val = input(f"[?] Nama Worker [{default_name}]: ").strip()
        worker_name = val if val else default_name

    github_user = args.github
    while not github_user:
        github_user = input("[?] Username GitHub (akan diverifikasi anti-fake): ").strip()
        if not github_user:
            print("    [!] Username GitHub tidak boleh kosong.")

    email = args.email
    while not email:
        email = input("[?] Alamat Email (untuk menerima kode OTP): ").strip()
        if not email or "@" not in email:
            print("    [!] Masukkan alamat email yang valid.")
            email = None

    print("\n" + "-" * 70)
    print(f"[*] Menghubungi Koordinator di: {coord_url}")
    print(f"[*] Mengirim permintaan registrasi untuk '{worker_name}' (GitHub: @{github_user})...")
    print("    Sistem sedang memverifikasi akun GitHub Anda (Anti-Fake Worker)...")
    print("-" * 70)

    # Langkah 1: Request Register + GitHub Check
    status, res = post_json(coord_url, "/api/auth/register-request", {
        "worker_name": worker_name,
        "github_username": github_user,
        "email": email
    })

    if status != 200:
        print("\n[X] REGISTRASI DITOLAK OLEH KOORDINATOR:")
        detail = res.get("detail", {})
        if isinstance(detail, dict):
            print(f"    Pesan : {detail.get('message')}")
            reasons = detail.get("reasons", [])
            if reasons:
                print("    Alasan Penolakan:")
                for r in reasons:
                    print(f"    - {r}")
            factors = detail.get("factors", {})
            if factors:
                print("\n    Detail Hasil Analisis Akun GitHub:")
                print(f"    * Usia Akun        : {factors.get('account_age_days')} hari (Syarat: minimal {factors.get('min_account_age_days')} hari)")
                print(f"    * Repositori Publik: {factors.get('public_repos')} repo (Syarat: minimal {factors.get('min_public_repos')} repo)")
                print(f"    * Followers        : {factors.get('followers')}")
                print(f"    * Tipe Akun        : {factors.get('account_type')}")
        else:
            print(f"    Error: {detail}")
        sys.exit(1)

    session_id = res["session_id"]
    factors = res.get("factors", {})
    score = res.get("github_score", 100)

    print("\n[V] VERIFIKASI GITHUB BERHASIL (LOLOS ANTI-FAKE WORKER)!")
    print(f"    * Skor Reputasi    : {score}/100")
    print(f"    * Usia Akun        : {factors.get('account_age_days')} hari [LOLOS]")
    print(f"    * Repositori Publik: {factors.get('public_repos')} repo [LOLOS]")
    print(f"    * Followers        : {factors.get('followers')}")
    print(f"    * Profil Lengkap   : {'Ya' if factors.get('profile_complete') else 'Cukup'}")
    print(f"\n[i] {res.get('message', 'Kode OTP telah dikirim ke email.')}")

    if res.get("dev_mode") and res.get("dev_otp"):
        print(f"\n    [DEV HINT] (Koordinator dalam dev mode) Kode OTP: {res['dev_otp']}")

    # Langkah 2: Input Kode OTP
    print("\n" + "=" * 70)
    print("LANGKAH 2: VERIFIKASI KODE TOKEN OTP")
    print("=" * 70)
    print("  Ketik 'resend' untuk meminta kode OTP baru jika email belum datang.")

    verified    = False
    attempts    = 0
    max_attempts = 5

    while not verified and attempts < max_attempts:
        otp_input = input("\n[?] Masukkan 6 digit Kode OTP dari email Anda (atau 'resend'): ").strip()
        if not otp_input:
            continue

        # Opsi resend OTP tanpa restart dari awal
        if otp_input.lower() == "resend":
            print("[*] Meminta kode OTP baru ke koordinator...")
            r_status, r_res = post_json(coord_url, "/api/auth/resend-otp", {"session_id": session_id})
            if r_status == 200:
                print(f"[V] OTP baru dikirimkan ke {email}.")
                if r_res.get("dev_mode") and r_res.get("dev_otp"):
                    print(f"    [DEV HINT] Kode OTP baru: {r_res['dev_otp']}")
            else:
                print(f"[X] Gagal resend: {r_res.get('detail', 'Error tidak diketahui')}")
            continue

        print("[*] Memverifikasi kode OTP ke koordinator...")
        v_status, v_res = post_json(coord_url, "/api/auth/verify-otp", {
            "session_id": session_id,
            "otp":        otp_input,
        })

        if v_status == 200:
            verified     = True
            worker_id    = v_res["worker_id"]
            worker_token = v_res["worker_token"]

            print("\n" + "=" * 70)
            print("                 AUTENTIKASI WORKER BERHASIL!")
            print("=" * 70)
            print(f"Worker ID    : {worker_id}")
            print(f"Nama Worker  : {worker_name}")
            print(f"GitHub       : @{github_user}")
            print(f"Email        : {email}")
            print(f"Status       : Terverifikasi (Active)")
            print(f"Worker Token : {worker_token}")
            print("-" * 70)
            print("[INFO] Worker kini terverifikasi dan siap diassign ke jobdesk komputasi!")
            print("-" * 70)

            # Simpan token ke .env
            save_env = input("\n[?] Simpan WORKER_TOKEN, WORKER_ID, dan WORKER_NAME ke file .env sekarang? [Y/n]: ").strip().lower()
            if save_env in ("", "y", "ya", "yes"):
                update_env_file(".env", {
                    "WORKER_TOKEN":    worker_token,
                    "WORKER_NAME":     worker_name,
                    "WORKER_ID":       worker_id,
                    "COORDINATOR_URL": coord_url,
                })
                print("[V] File .env berhasil diperbarui.")
                print(f"    WORKER_TOKEN = {worker_token}")
                print(f"    WORKER_ID    = {worker_id}")
                print(f"    WORKER_NAME  = {worker_name}")
                print("\n    Sekarang Anda dapat menjalankan worker dengan:")
                print("    ./hpc.sh worker-up\n")
            else:
                print("\n[!] Simpan variabel ini secara manual ke .env sebelum menjalankan worker:")
                print(f"    WORKER_TOKEN={worker_token}")
                print(f"    WORKER_ID={worker_id}")
                print(f"    WORKER_NAME={worker_name}")
            break
        else:
            attempts += 1
            err = v_res.get("detail", "Verifikasi OTP gagal")
            print(f"[X] {err}")

    if not verified:
        print("\n[!] Batas percobaan habis atau sesi berakhir. Silakan jalankan ulang script ini.")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Proses dibatalkan oleh user.")
        sys.exit(0)

