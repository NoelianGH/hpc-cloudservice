import os
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "").strip()
SMTP_FROM = os.environ.get("SMTP_FROM", "").strip() or SMTP_USER or "hpc-cloud@localhost"
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")


def generate_otp(length: int = 6) -> str:
    """
    Menghasilkan kode OTP numerik acak yang aman secara kriptografi.
    """
    return "".join(secrets.choice("0123456789") for _ in range(length))


def send_otp_email(to_email: str, otp: str, worker_name: str, github_username: str) -> dict:
    """
    Mengirimkan email berisi token OTP verifikasi ke worker.
    Jika konfigurasi SMTP (SMTP_HOST) belum disetel, sistem secara otomatis
    berjalan dalam mode simulasi / development dan mencatat OTP ke log koordinator.
    """
    subject = f"[HPC Cloud] Kode Verifikasi Worker Anda: {otp}"

    body_text = f"""Halo {github_username},

Worker Anda '{worker_name}' sedang mencoba melakukan autentikasi di kluster HPC Cloud.

KODE VERIFIKASI (OTP) ANDA:
===========================
      {otp}
===========================

Kode ini berlaku selama 10 menit. Masukkan kode ini ke prompt CLI Anda untuk menyelesaikan proses autentikasi.

Jika Anda tidak merasa melakukan permintaan ini, abaikan email ini.

Salam,
Tim HPC Cloud Service
"""

    # Jika SMTP_HOST tidak dikonfigurasi, gunakan mode simulasi (dev mode)
    if not SMTP_HOST:
        print(f"\n" + "=" * 60, flush=True)
        print(f"[SIMULASI EMAIL / DEV MODE] Pengiriman OTP ke {to_email}", flush=True)
        print(f"Worker      : {worker_name} (GitHub: @{github_username})", flush=True)
        print(f"Kode OTP    : {otp}", flush=True)
        print(f"Catatan     : Setel SMTP_HOST, SMTP_USER, SMTP_PASSWORD di .env untuk email riil.", flush=True)
        print("=" * 60 + "\n", flush=True)
        return {
            "success": True,
            "dev_mode": True,
            "message": "OTP disimulasikan (cek log head node coordinator).",
            "dev_otp": otp,
        }

    # Pengiriman email riil melalui SMTP
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_FROM
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body_text, "plain", "utf-8"))

        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as server:
                if SMTP_USER and SMTP_PASSWORD:
                    server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
                if SMTP_USE_TLS:
                    server.starttls()
                if SMTP_USER and SMTP_PASSWORD:
                    server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)

        print(f"[EMAIL] Berhasil mengirimkan OTP ke {to_email} untuk worker '{worker_name}'", flush=True)
        return {
            "success": True,
            "dev_mode": False,
            "message": f"Email kode verifikasi telah dikirimkan ke {to_email}",
        }
    except Exception as e:
        print(f"[EMAIL ERROR] Gagal mengirimkan email ke {to_email}: {e}", flush=True)
        # Fallback agar user tetap bisa melanjutkan pengetesan jika SMTP lokal gagal koneksi
        print(f"[FALLBACK LOG] KODE OTP UNTUK {to_email} ADALAH: {otp}", flush=True)
        return {
            "success": True,
            "dev_mode": True,
            "warning": f"Pengiriman SMTP gagal ({str(e)}), kode dicatat ke log server.",
            "dev_otp": otp,
        }

