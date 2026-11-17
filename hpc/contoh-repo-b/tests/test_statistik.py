import unittest

from app.pengaduan import Gudang
from app.statistik import ringkasan


class TestStatistik(unittest.TestCase):
    def test_kosong(self):
        self.assertEqual(ringkasan([])["persen_selesai"], 0.0)

    def test_persen(self):
        g = Gudang()
        for i, k in enumerate(["jalan", "jalan", "air", "listrik"]):
            g.tambah({"nama": f"Warga {i}", "hp": "081200000000", "kategori": k, "isi": "Laporan warga nomor"})
        g.ubah_status(1, "diproses")
        g.ubah_status(1, "selesai")
        r = ringkasan(g.semua())
        self.assertEqual(r["total"], 4)
        self.assertEqual(r["per_kategori"]["jalan"], 2)
        self.assertEqual(r["persen_selesai"], 25.0)


if __name__ == "__main__":
    unittest.main()
