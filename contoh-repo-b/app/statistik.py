"""Ringkasan pengaduan untuk dashboard pemerintah daerah."""
from collections import Counter


def ringkasan(daftar) -> dict:
    per_status = Counter(p.status for p in daftar)
    per_kategori = Counter(p.kategori for p in daftar)
    total = len(daftar)
    selesai = per_status.get("selesai", 0)
    return {"total": total, "per_status": dict(sorted(per_status.items())),
            "per_kategori": dict(sorted(per_kategori.items())),
            "persen_selesai": round(100 * selesai / total, 1) if total else 0.0}
