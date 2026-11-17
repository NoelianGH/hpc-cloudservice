"""Koneksi database dan autentikasi worker, dipakai bersama oleh app.py dan volunteer.py."""
import hmac
import os

import psycopg
from psycopg.rows import dict_row
from fastapi import HTTPException

DB_URL = os.environ["DATABASE_URL"]
WORKER_TOKEN = os.environ.get("WORKER_TOKEN", "")


def db():
    return psycopg.connect(DB_URL, row_factory=dict_row, autocommit=True)


def check_worker_auth(auth: str | None) -> dict:
    """
    Memvalidasi otentikasi worker. Mendukung dua mode:
    1. Token individual: Token unik yang didapat worker setelah verifikasi GitHub + OTP.
    2. Token global: WORKER_TOKEN dari .env (untuk backward-compatibility).
    """
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(401, "Header Authorization (Bearer token) diperlukan")

    token = auth.split("Bearer ", 1)[1].strip()

    # Token individual (hpc_w_...) dicek lebih dulu, supaya tetap dikenali walau di laptop
    # yang sama (head + worker) nilainya juga tertulis sebagai WORKER_TOKEN di .env.
    if token.startswith("hpc_w_"):
        with db() as c:
            w = c.execute(
                "SELECT id, name, github_username, email, status, coalesce(show_in_appreciation, false) AS show_in_appreciation FROM workers WHERE auth_token = %s",
                (token,)
            ).fetchone()
        if w:
            if w["status"] != "active":
                raise HTTPException(403, f"Status worker '{w['name']}' ditangguhkan ({w['status']})")
            return {"type": "individual", "worker": w}

    # Token global WORKER_TOKEN dari .env (mode lama / uji coba)
    if WORKER_TOKEN and hmac.compare_digest(token.encode(), WORKER_TOKEN.encode()):
        return {"type": "global", "token": token}

    raise HTTPException(401, "Token worker tidak sah atau belum terdaftar")


def check_worker_owner(auth_info: dict, worker_id: str, c) -> None:
    """
    Pastikan worker_id di body memang milik pemegang token:
    - token individual hanya boleh memakai worker_id miliknya sendiri;
    - token global hanya boleh memakai worker anonim (tanpa token individual).
    Worker yang ditangguhkan admin ditolak.
    """
    if auth_info["type"] == "individual":
        if auth_info["worker"]["id"] != worker_id:
            raise HTTPException(403, "worker_id tidak sesuai dengan token worker.")
        return
    w = c.execute("SELECT auth_token IS NOT NULL AS owned, status FROM workers WHERE id = %s",
                  (worker_id,)).fetchone()
    if not w:
        raise HTTPException(404, "Worker tidak ditemukan. Panggil /api/register dulu.")
    if w["owned"]:
        raise HTTPException(403, "Worker ini terikat token individual; token global tidak boleh dipakai.")
    if w["status"] != "active":
        raise HTTPException(403, f"Worker ditangguhkan ({w['status']}).")
