"""Penyimpanan pengaduan di memori dan alur statusnya."""
from dataclasses import dataclass, field

from app.validasi import validasi_pengaduan

ALUR = {"baru": ("diproses", "ditolak"), "diproses": ("selesai",), "selesai": (), "ditolak": ()}


@dataclass
class Pengaduan:
    id: int
    nama: str
    hp: str
    kategori: str
    isi: str
    status: str = "baru"
    riwayat: list = field(default_factory=list)


class Gudang:
    def __init__(self):
        self._data: dict[int, Pengaduan] = {}
        self._berikut = 1

    def tambah(self, data: dict) -> Pengaduan:
        salah = validasi_pengaduan(data)
        if salah:
            raise ValueError("; ".join(salah))
        p = Pengaduan(self._berikut, data["nama"].strip(), data["hp"], data["kategori"], data["isi"].strip())
        self._data[p.id] = p
        self._berikut += 1
        return p

    def ambil(self, pid: int) -> Pengaduan:
        if pid not in self._data:
            raise KeyError(f"pengaduan {pid} tidak ada")
        return self._data[pid]

    def ubah_status(self, pid: int, status: str) -> Pengaduan:
        p = self.ambil(pid)
        if status not in ALUR[p.status]:
            raise ValueError(f"status {p.status} tidak bisa menjadi {status}")
        p.riwayat.append(p.status)
        p.status = status
        return p

    def semua(self, kategori: str | None = None) -> list[Pengaduan]:
        return [p for p in self._data.values() if kategori in (None, p.kategori)]
