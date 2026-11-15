"""Server HTTP sederhana (tanpa library luar). Jalankan: python3 -m app.server"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.pengaduan import Gudang
from app.statistik import ringkasan

GUDANG = Gudang()


def tangani(metode: str, path: str, body: dict | None, gudang: Gudang = GUDANG) -> tuple[int, dict]:
    """Logika routing dipisah dari HTTP supaya mudah dites."""
    if metode == "GET" and path == "/api/statistik":
        return 200, ringkasan(gudang.semua())
    if metode == "GET" and path == "/api/pengaduan":
        return 200, {"data": [vars(p) for p in gudang.semua()]}
    if metode == "POST" and path == "/api/pengaduan":
        try:
            return 201, vars(gudang.tambah(body or {}))
        except ValueError as e:
            return 400, {"error": str(e)}
    return 404, {"error": "tidak ditemukan"}


class Handler(BaseHTTPRequestHandler):
    def _kirim(self, kode, data):
        b = json.dumps(data).encode()
        self.send_response(kode)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        self._kirim(*tangani("GET", self.path, None))

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self._kirim(*tangani("POST", self.path, json.loads(self.rfile.read(n) or b"{}")))


if __name__ == "__main__":
    print("Layanan pengaduan di http://localhost:8080")
    HTTPServer(("", 8080), Handler).serve_forever()
