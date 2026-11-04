#!/usr/bin/env python3
"""
test_auth_flow.py — Skrip uji coba alur autentikasi worker secara lokal.

Cara pakai:
  1. Pastikan head node sudah jalan:  ./hpc.sh head-up
  2. Jalankan:                         python3 test_auth_flow.py

Skrip ini akan menguji seluruh alur:
  • POST /api/auth/register-request  (GitHub check + OTP dikirim)
  • POST /api/auth/resend-otp        (Minta OTP baru)
  • POST /api/auth/verify-otp        (Verifikasi OTP → dapat token)
  • GET  /api/auth/me                (Cek identitas token)
  • POST /api/register               (Register worker pakai token baru)
  • POST /api/workers/{id}/status    (Admin suspend worker)

Karena SMTP_HOST di .env kosong, koordinator akan mencetak OTP di log (dev mode),
dan juga mengirimkannya kembali di field "dev_otp" dalam respons JSON.
"""

import json
import sys
import urllib.request
import urllib.error

# ============================================================================
# KONFIGURASI — sesuaikan jika berbeda
# ============================================================================
BASE_URL    = "http://localhost:8000"
ADMIN_TOKEN = "token-admin-sementara"   # harus cocok dengan .env

# Data relawan uji (pakai akun GitHub yang benar-benar ada dan lolos threshold)
# 'torvalds' → akun Linus Torvalds: umur > 30 hari, repo > 2, pasti lolos.
TEST_GITHUB = "torvalds"
TEST_EMAIL  = "test@example.com"
TEST_NAME   = "worker-testing"

# ============================================================================

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"
SEP  = "=" * 70


def post(path, body=None, token=None):
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE_URL + path, data=data, headers=headers,
                                method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"detail": raw}
        return e.code, parsed
    except Exception as e:
        return 0, {"detail": str(e)}


def get(path, token=None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE_URL + path, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"detail": raw}
        return e.code, parsed
    except Exception as e:
        return 0, {"detail": str(e)}


def pp(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def main():
    print(SEP)
    print("  HPC CLOUD SERVICE — UJI COBA ALUR AUTENTIKASI WORKER")
    print(SEP)

    errors = 0

    # ========================================================================
    # Uji 0: Cek koordinator hidup
    # ========================================================================
    print(f"\n{INFO} Uji 0: Mengecek apakah koordinator merespon di {BASE_URL} ...")
    code, res = get("/api/stats")
    if code != 200:
        print(f"{FAIL} Koordinator tidak bisa dihubungi di {BASE_URL}.")
        print(f"       Pastikan head node sudah jalan: ./hpc.sh head-up")
        print(f"       Error: {res}")
        sys.exit(1)
    print(f"{PASS} Koordinator hidup.\n")

    # ========================================================================
    # Uji 1: POST /api/auth/register-request — Verifikasi GitHub + kirim OTP
    # ========================================================================
    print(SEP)
    print(f"{INFO} Uji 1: POST /api/auth/register-request")
    print(f"         GitHub: @{TEST_GITHUB}  |  Email: {TEST_EMAIL}")
    print(SEP)

    code, res = post("/api/auth/register-request", {
        "worker_name":     TEST_NAME,
        "github_username": TEST_GITHUB,
        "email":           TEST_EMAIL,
    })

    if code == 200 and res.get("status") == "pending_otp":
        print(f"{PASS} Registrasi berhasil! GitHub lolos verifikasi.")
        print(f"      Session ID   : {res['session_id']}")
        print(f"      GitHub Score  : {res.get('github_score')}/100")
        factors = res.get("factors", {})
        print(f"      Usia Akun     : {factors.get('account_age_days')} hari")
        print(f"      Repositori    : {factors.get('public_repos')} repo")
        print(f"      Followers     : {factors.get('followers')}")
        if res.get("dev_mode"):
            print(f"      [DEV] OTP     : {res.get('dev_otp')}")
    else:
        print(f"{FAIL} Registrasi gagal (status {code}):")
        pp(res)
        errors += 1
        print(f"\n[!] Tidak bisa melanjutkan uji coba tanpa registrasi berhasil.")
        sys.exit(1)

    session_id = res["session_id"]
    dev_otp    = res.get("dev_otp")

    # ========================================================================
    # Uji 1b: OTP salah (harus ditolak)
    # ========================================================================
    print(f"\n{INFO} Uji 1b: Kirim OTP salah (harus ditolak)...")
    code, res = post("/api/auth/verify-otp", {
        "session_id": session_id,
        "otp":        "000000",
    })
    if code == 400:
        print(f"{PASS} OTP salah ditolak: {res.get('detail')}")
    else:
        print(f"{FAIL} Seharusnya ditolak, tapi status {code}:")
        pp(res)
        errors += 1

    # ========================================================================
    # Uji 2: POST /api/auth/resend-otp — Minta OTP baru
    # ========================================================================
    print(f"\n{SEP}")
    print(f"{INFO} Uji 2: POST /api/auth/resend-otp")
    print(SEP)

    code, res = post("/api/auth/resend-otp", {
        "session_id": session_id,
    })

    if code == 200 and res.get("status") == "otp_resent":
        print(f"{PASS} OTP baru berhasil di-resend.")
        if res.get("dev_mode"):
            dev_otp = res.get("dev_otp")
            print(f"      [DEV] OTP baru: {dev_otp}")
    else:
        print(f"{FAIL} Resend gagal (status {code}):")
        pp(res)
        errors += 1

    # ========================================================================
    # Uji 3: POST /api/auth/verify-otp — Verifikasi OTP yang benar
    # ========================================================================
    print(f"\n{SEP}")
    print(f"{INFO} Uji 3: POST /api/auth/verify-otp (OTP benar)")
    print(SEP)

    if not dev_otp:
        print(f"{FAIL} Tidak ada dev_otp — SMTP_HOST mungkin terisi di .env.")
        print(f"       Pastikan SMTP_HOST= (kosong) di .env untuk dev mode.")
        sys.exit(1)

    code, res = post("/api/auth/verify-otp", {
        "session_id": session_id,
        "otp":        dev_otp,
    })

    if code == 200 and res.get("status") == "authenticated":
        print(f"{PASS} OTP valid! Worker berhasil diautentikasi.")
        print(f"      Worker ID    : {res['worker_id']}")
        print(f"      Worker Token : {res['worker_token']}")
        print(f"      GitHub       : @{res['github_username']}")
    else:
        print(f"{FAIL} Verifikasi OTP gagal (status {code}):")
        pp(res)
        errors += 1
        sys.exit(1)

    worker_id    = res["worker_id"]
    worker_token = res["worker_token"]

    # ========================================================================
    # Uji 3b: Sesi sudah verified (tidak boleh verify ulang)
    # ========================================================================
    print(f"\n{INFO} Uji 3b: Coba verify ulang sesi yang sudah verified...")
    code, res = post("/api/auth/verify-otp", {
        "session_id": session_id,
        "otp":        dev_otp,
    })
    if code == 400:
        print(f"{PASS} Ditolak: {res.get('detail')}")
    else:
        print(f"{FAIL} Seharusnya ditolak, tapi status {code}")
        errors += 1

    # ========================================================================
    # Uji 4: GET /api/auth/me — Cek identitas token
    # ========================================================================
    print(f"\n{SEP}")
    print(f"{INFO} Uji 4: GET /api/auth/me (pakai worker_token individual)")
    print(SEP)

    code, res = get("/api/auth/me", token=worker_token)
    if code == 200 and res.get("verified"):
        print(f"{PASS} Token valid dan terverifikasi.")
        print(f"      worker_id     : {res['worker_id']}")
        print(f"      github        : @{res['github_username']}")
        print(f"      status        : {res['status']}")
    else:
        print(f"{FAIL} /api/auth/me gagal (status {code}):")
        pp(res)
        errors += 1

    # ========================================================================
    # Uji 4b: GET /api/auth/me — Token global (backward-compat)
    # ========================================================================
    print(f"\n{INFO} Uji 4b: GET /api/auth/me (pakai WORKER_TOKEN global)...")
    code, res = get("/api/auth/me", token="token-relawan-sementara")
    if code == 200 and res.get("type") == "global_token":
        print(f"{PASS} Token global diterima (belum terverifikasi individual).")
    else:
        print(f"{FAIL} Token global ditolak (status {code}):")
        pp(res)
        errors += 1

    # ========================================================================
    # Uji 5: POST /api/register — Worker register pakai token individual
    # ========================================================================
    print(f"\n{SEP}")
    print(f"{INFO} Uji 5: POST /api/register (dengan token individual)")
    print(SEP)

    code, res = post("/api/register", {"name": TEST_NAME}, token=worker_token)
    if code == 200 and res.get("worker_id") == worker_id:
        print(f"{PASS} Register berhasil, worker_id konsisten: {res['worker_id']}")
    else:
        print(f"{FAIL} Register gagal (status {code}):")
        pp(res)
        errors += 1

    # ========================================================================
    # Uji 6: POST /api/workers/{id}/status — Admin suspend worker
    # ========================================================================
    print(f"\n{SEP}")
    print(f"{INFO} Uji 6: Admin suspend worker lalu coba claim")
    print(SEP)

    code, res = post(f"/api/workers/{worker_id}/status",
                     {"status": "suspended", "reason": "uji coba suspend"},
                     token=ADMIN_TOKEN)
    if code == 200:
        print(f"{PASS} Worker berhasil di-suspend: {res.get('message')}")
    else:
        print(f"{FAIL} Suspend gagal (status {code}):")
        pp(res)
        errors += 1

    # Coba pakai token yang di-suspend → harus 403
    print(f"\n{INFO} Uji 6b: Coba /api/auth/me pakai token yang di-suspend...")
    code, res = get("/api/auth/me", token=worker_token)
    if code == 403:
        print(f"{PASS} Worker suspended ditolak: {res.get('detail')}")
    else:
        print(f"{FAIL} Seharusnya 403, tapi {code}:")
        pp(res)
        errors += 1

    # Kembalikan ke active
    print(f"\n{INFO} Uji 6c: Admin aktifkan kembali worker...")
    code, res = post(f"/api/workers/{worker_id}/status",
                     {"status": "active", "reason": "uji selesai"},
                     token=ADMIN_TOKEN)
    if code == 200:
        print(f"{PASS} Worker diaktifkan kembali: {res.get('message')}")
    else:
        print(f"{FAIL} Reactivation gagal:")
        pp(res)
        errors += 1

    # ========================================================================
    # Uji 7: Token palsu → harus ditolak
    # ========================================================================
    print(f"\n{INFO} Uji 7: Token palsu harus ditolak...")
    code, res = get("/api/auth/me", token="hpc_w_tokenpalsutidakvalid")
    if code == 401:
        print(f"{PASS} Token palsu ditolak.")
    else:
        print(f"{FAIL} Seharusnya 401, tapi {code}")
        errors += 1

    # ========================================================================
    # Uji 8: Dashboard masih bisa diakses
    # ========================================================================
    print(f"\n{INFO} Uji 8: Dashboard HTML...")
    code, _ = get("/")
    if code == 200:
        print(f"{PASS} Dashboard OK.")
    else:
        print(f"{FAIL} Dashboard error {code}")
        errors += 1

    # ========================================================================
    # HASIL AKHIR
    # ========================================================================
    print(f"\n{SEP}")
    if errors == 0:
        print(f"  {PASS}  SEMUA UJI BERHASIL — Alur autentikasi berjalan sempurna!")
    else:
        print(f"  {FAIL}  {errors} uji GAGAL — periksa output di atas.")
    print(SEP)
    return errors


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[!] Dibatalkan.")
        sys.exit(1)

