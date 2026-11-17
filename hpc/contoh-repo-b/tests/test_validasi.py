import unittest

from app.validasi import nomor_hp_valid, validasi_pengaduan

BAIK = {"nama": "Siti", "hp": "081234567890", "kategori": "jalan", "isi": "Jalan berlubang di RT 03"}


class TestValidasi(unittest.TestCase):
    def test_hp(self):
        self.assertTrue(nomor_hp_valid("0812-3456-7890"))
        self.assertTrue(nomor_hp_valid("+6281234567890"))
        self.assertFalse(nomor_hp_valid("12345"))

    def test_data_baik(self):
        self.assertEqual(validasi_pengaduan(BAIK), [])

    def test_data_buruk(self):
        salah = validasi_pengaduan({**BAIK, "nama": "A", "kategori": "x"})
        self.assertIn("Nama minimal 3 huruf", salah)
        self.assertIn("Kategori tidak dikenal", salah)


if __name__ == "__main__":
    unittest.main()
