"""
Utilitas autentikasi admin (hanya pustaka standar Python).

- Hash password memakai PBKDF2-HMAC-SHA256 dengan salt acak.
  Format: pbkdf2_sha256:<iterasi>:<salt_b64>:<hash_b64>
  (tanpa karakter '$' agar aman ditaruh di .env yang dibaca docker compose).
- Bisa dijalankan sebagai skrip untuk membuat hash / mengisi .env:

    python3 head/coordinator/admin_auth.py hash          # cetak hash saja
    python3 head/coordinator/admin_auth.py set .env      # isi ADMIN_EMAIL & ADMIN_PASSWORD_HASH di .env

  Pintasan: ./hpc.sh admin-setup
"""
import base64
import getpass
import hashlib
import hmac
import os
import re
import secrets
import sys

ALGO = "pbkdf2_sha256"
ITERATIONS = 600_000
MIN_PASSWORD_LEN = 10


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hash_password(password: str, iterations: int = ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"{ALGO}:{iterations}:{_b64(salt)}:{_b64(dk)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, iters, salt, expected = encoded.strip().split(":")
        if algo != ALGO:
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), _unb64(salt), int(iters))
        return hmac.compare_digest(dk, _unb64(expected))
    except (ValueError, TypeError):
        return False


# Hash palsu untuk menyamakan waktu respons saat email salah (mencegah enumerasi).
DUMMY_HASH = hash_password(secrets.token_hex(16), iterations=ITERATIONS)


def hash_token(token: str) -> str:
    """Token sesi disimpan di DB dalam bentuk hash SHA-256, bukan teks asli."""
    return hashlib.sha256(token.encode()).hexdigest()


def new_session_token() -> str:
    return "hpc_adm_" + secrets.token_urlsafe(32)


# =============================================================================
# CLI
# =============================================================================

def _ask_password() -> str:
    while True:
        p1 = getpass.getpass(f"Password admin (min. {MIN_PASSWORD_LEN} karakter): ")
        if len(p1) < MIN_PASSWORD_LEN:
            print(f"Password terlalu pendek. Minimal {MIN_PASSWORD_LEN} karakter.")
            continue
        p2 = getpass.getpass("Ulangi password: ")
        if p1 != p2:
            print("Password tidak sama, coba lagi.")
            continue
        return p1


def _set_env_value(text: str, key: str, value: str) -> str:
    line = f"{key}={value}"
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(lambda _m: line, text, count=1)
    if text and not text.endswith("\n"):
        text += "\n"
    return text + line + "\n"


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "hash"
    if cmd == "hash":
        print(hash_password(_ask_password()))
        return 0
    if cmd == "set":
        env_path = argv[2] if len(argv) > 2 else ".env"
        email = input("Email admin: ").strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            print("Format email tidak valid.")
            return 1
        hashed = hash_password(_ask_password())
        text = open(env_path, encoding="utf-8").read() if os.path.exists(env_path) else ""
        text = _set_env_value(text, "ADMIN_EMAIL", email)
        text = _set_env_value(text, "ADMIN_PASSWORD_HASH", hashed)
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"ADMIN_EMAIL dan ADMIN_PASSWORD_HASH tersimpan di {env_path}.")
        print("Jalankan ulang head node agar berlaku: ./hpc.sh head-up")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
