"""Validasi data pengaduan yang dikirim warga."""
import re

KATEGORI = ("jalan", "sampah", "air", "listrik", "keamanan", "lainnya")
_HP_RE = re.compile(r"^(\+62|62|0)8[0-9]{7,11}$")


def nomor_hp_valid(nomor: str) -> bool:
    return bool(_HP_RE.match((nomor or "").replace(" ", "").replace("-", "")))


def validasi_pengaduan(data: dict) -> list[str]:
    """Kembalikan daftar pesan kesalahan (kosong berarti data valid)."""
    salah = []
    if len((data.get("nama") or "").strip()) < 3:
        salah.append("Nama minimal 3 huruf")
    if not nomor_hp_valid(data.get("hp", "")):
        salah.append("Nomor HP tidak valid")
    if data.get("kategori") not in KATEGORI:
        salah.append("Kategori tidak dikenal")
    if len((data.get("isi") or "").strip()) < 10:
        salah.append("Isi pengaduan minimal 10 karakter")
    return salah
