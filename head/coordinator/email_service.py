import os
import json
import secrets
import smtplib
import ssl
import socket
import urllib.request
import urllib.error
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "").strip()
SMTP_FROM = os.environ.get("SMTP_FROM", "").strip() or SMTP_USER or "hpc-cloud@localhost"
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")

# Alternatif pengiriman via HTTPS (Port 443) yang anti-blokir ISP / Antivirus
EMAIL_WEBHOOK_URL = os.environ.get("EMAIL_WEBHOOK_URL", "").strip().strip('"').strip("'")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip().strip('"').strip("'")


def generate_otp(length: int = 6) -> str:
    """
    Menghasilkan kode OTP numerik acak yang aman secara kriptografi.
    """
    return "".join(secrets.choice("0123456789") for _ in range(length))


def send_otp_email(to_email: str, otp: str, worker_name: str, github_username: str) -> dict:
    """
    Mengirimkan email berisi token OTP verifikasi ke worker.
    Mendukung 3 metode:
    1. Google Apps Script Webhook (Port 443 HTTPS - Anti blokir ISP)
    2. Resend API (Port 443 HTTPS)
    3. Direct SMTP (Port 465 SSL & Port 587 STARTTLS)
    """
    subject = f"[HPC Cloud] Kode Verifikasi Worker Anda: {otp}"

    body_text = f"""Halo {github_username},

Worker Anda '{worker_name}' sedang mencoba melakukan registrasi di kluster HPC Cloud Service.

KODE VERIFIKASI (OTP) ANDA:
===========================
      {otp}
===========================

Kode ini berlaku selama 10 menit. Masukkan kode ini ke prompt verifikasi untuk mengaktifkan worker Anda.

Jika Anda tidak merasa melakukan permintaan ini, abaikan email ini.

Salam,
Tim HPC Cloud Service
"""

    # =========================================================================
    # METODE 1: Google Apps Script Webhook HTTPS (Port 443)
    # =========================================================================
    if EMAIL_WEBHOOK_URL:
        try:
            print(f"[EMAIL] Mengirim via Google Apps Script Webhook HTTPS (Port 443) ke {to_email}...", flush=True)
            payload = json.dumps({
                "to": to_email,
                "subject": subject,
                "body": body_text,
                "otp": otp,
            }).encode("utf-8")

            req = urllib.request.Request(
                EMAIL_WEBHOOK_URL,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                print(f"[EMAIL SUCCESS] Berhasil mengirimkan email OTP via HTTPS Webhook ke {to_email}!", flush=True)
                return {
                    "success": True,
                    "dev_mode": False,
                    "message": f"Email kode verifikasi telah dikirimkan ke {to_email}",
                }
        except Exception as e:
            print(f"[EMAIL WARN] Gagal via Webhook: {e}", flush=True)

    # =========================================================================
    # METODE 2: Resend API HTTPS (Port 443)
    # =========================================================================
    if RESEND_API_KEY:
        try:
            print(f"[EMAIL] Mengirim via Resend API HTTPS (Port 443) ke {to_email}...", flush=True)
            payload = json.dumps({
                "from": "HPC Cloud <onboarding@resend.dev>",
                "to": [to_email],
                "subject": subject,
                "text": body_text,
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://api.resend.com/emails",
                data=payload,
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                print(f"[EMAIL SUCCESS] Berhasil mengirimkan email OTP via Resend API ke {to_email}!", flush=True)
                return {
                    "success": True,
                    "dev_mode": False,
                    "message": f"Email kode verifikasi telah dikirimkan ke {to_email}",
                }
        except Exception as e:
            print(f"[EMAIL WARN] Gagal via Resend API: {e}", flush=True)

    # =========================================================================
    # METODE 3: Direct SMTP
    # =========================================================================
    if not SMTP_HOST:
        print(f"\n" + "=" * 60, flush=True)
        print(f"[SIMULASI EMAIL / DEV MODE] Pengiriman OTP ke {to_email}", flush=True)
        print(f"Worker      : {worker_name} (GitHub: @{github_username})", flush=True)
        print(f"Kode OTP    : {otp}", flush=True)
        print("=" * 60 + "\n", flush=True)
        return {
            "success": True,
            "dev_mode": True,
            "message": "OTP disimulasikan (cek log head node coordinator).",
            "dev_otp": otp,
        }

    clean_user = SMTP_USER.strip().strip('"').strip("'")
    clean_from = (SMTP_FROM or clean_user).strip().strip('"').strip("'")
    clean_password = SMTP_PASSWORD.strip().strip('"').strip("'").replace(" ", "")

    msg = MIMEMultipart()
    msg["From"] = clean_from
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    methods = [("SSL", 465), ("STARTTLS", 587)]
    last_error = None

    orig_getaddrinfo = socket.getaddrinfo
    def force_ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

    try:
        socket.getaddrinfo = force_ipv4_getaddrinfo
        for mode, port in methods:
            try:
                print(f"[EMAIL] Mencoba mengirim email ke {to_email} via {SMTP_HOST}:{port} ({mode} IPv4)...", flush=True)
                if mode == "SSL" or port == 465:
                    context = ssl.create_default_context()
                    with smtplib.SMTP_SSL(SMTP_HOST, port, context=context, timeout=20) as server:
                        if clean_user and clean_password:
                            server.login(clean_user, clean_password)
                        server.send_message(msg)
                else:
                    with smtplib.SMTP(SMTP_HOST, port, timeout=20) as server:
                        server.ehlo()
                        if SMTP_USE_TLS:
                            context = ssl.create_default_context()
                            server.starttls(context=context)
                            server.ehlo()
                        if clean_user and clean_password:
                            server.login(clean_user, clean_password)
                        server.send_message(msg)

                print(f"[EMAIL SUCCESS] Berhasil mengirimkan email OTP ke {to_email} via port {port}!", flush=True)
                return {
                    "success": True,
                    "dev_mode": False,
                    "message": f"Email kode verifikasi telah dikirimkan ke {to_email}",
                }
            except Exception as e:
                last_error = e
                print(f"[EMAIL WARN] Gagal via {SMTP_HOST}:{port} ({mode}): {e}", flush=True)
    finally:
        socket.getaddrinfo = orig_getaddrinfo

    print(f"[EMAIL ERROR] Semua metode SMTP gagal. Error terakhir: {last_error}", flush=True)
    print(f"[FALLBACK LOG] KODE OTP UNTUK {to_email} ADALAH: {otp}", flush=True)
    return {
        "success": False,
        "dev_mode": True,
        "warning": f"Pengiriman email gagal ({str(last_error)}). Kode OTP dicatat ke log server.",
        "dev_otp": otp,
    }
