import unittest

from app.pengaduan import Gudang

DATA = {"nama": "Budi", "hp": "085711112222", "kategori": "sampah", "isi": "Sampah menumpuk di pasar"}


class TestPengaduan(unittest.TestCase):
    def setUp(self):
        self.g = Gudang()

    def test_tambah(self):
        p = self.g.tambah(DATA)
        self.assertEqual((p.id, p.status), (1, "baru"))

    def test_tolak_data_salah(self):
        with self.assertRaises(ValueError):
            self.g.tambah({**DATA, "isi": "pendek"})

    def test_alur_status(self):
        p = self.g.tambah(DATA)
        self.g.ubah_status(p.id, "diproses")
        self.g.ubah_status(p.id, "selesai")
        self.assertEqual(p.riwayat, ["baru", "diproses"])
        with self.assertRaises(ValueError):
            self.g.ubah_status(p.id, "diproses")


if __name__ == "__main__":
    unittest.main()
