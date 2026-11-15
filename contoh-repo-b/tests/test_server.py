import unittest

from app.pengaduan import Gudang
from app.server import tangani


class TestServer(unittest.TestCase):
    def test_alur_api(self):
        g = Gudang()
        kode, _ = tangani("POST", "/api/pengaduan", {"nama": "Rina", "hp": "081399998888",
                                                     "kategori": "air", "isi": "Air PAM mati 3 hari"}, g)
        self.assertEqual(kode, 201)
        kode, data = tangani("GET", "/api/statistik", None, g)
        self.assertEqual((kode, data["total"]), (200, 1))

    def test_data_salah(self):
        kode, data = tangani("POST", "/api/pengaduan", {"nama": "R"}, Gudang())
        self.assertEqual(kode, 400)
        self.assertIn("error", data)

    def test_404(self):
        self.assertEqual(tangani("GET", "/tidak-ada", None, Gudang())[0], 404)


if __name__ == "__main__":
    unittest.main()
