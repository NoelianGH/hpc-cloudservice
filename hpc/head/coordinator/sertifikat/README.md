# Template sertifikat kontributor

Sertifikat PDF relawan dibuat koordinator dari file di folder ini:

| File | Isi |
|------|-----|
| `template.png` | Desain sertifikat A4 lanskap 2480 x 1754 px. Semua teks tetap sudah ada di gambar; area nama, tanggal terbit, dan nomor sertifikat dikosongkan. |
| `layout.json` | Posisi, font, ukuran, dan warna isian (nama, tanggal, kaki halaman). |
| `fonts/` | Great Vibes (nama), Lora, Cinzel. Semua berlisensi SIL Open Font License (`OFL-*.txt`). |
| `buat_template.py` | Pembuat ulang `template.png` bawaan (`python buat_template.py`). |

Alur (lihat `../certificate_pdf.py` dan `GET /api/me/certificate.pdf` di `../volunteer.py`):

1. Relawan login di web lalu menekan **BUKA / AMBIL SERTIFIKAT (PDF)** di dashboard (tab baru).
2. Koordinator memeriksa syarat: poin (kredit) >= `CERT_MIN_CREDITS` (bawaan 50), ditambah syarat lama
   `CERT_MIN_ACCEPT_PCT` dan akun terverifikasi GitHub. Bila terpenuhi, sertifikat otomatis diterbitkan
   (atau nama & angkanya diperbarui; kode tetap).
3. `template.png` diisi **nama lengkap registrasi** (First Name + Last Name), tanggal terbit, dan nomor
   sertifikat + alamat verifikasi `/certificate/<kode>`, lalu disimpan sebagai PDF A4 lanskap.
   Nama yang sangat panjang otomatis mengecil / jadi dua baris, tidak dipotong.

## Mengganti desain

Buat desain sendiri (mis. Canva) berukuran 2480 x 1754 px, kosongkan area isian, ekspor PNG lalu
timpa `template.png`. Bila posisi garis nama berubah, sesuaikan `center_x` / `baseline_y` /
`max_width` di `layout.json`. Setelah mengubah file di folder ini jalankan `./hpc.sh head-up`
(koordinator berjalan dari image Docker). Folder lain bisa dipakai lewat env `CERT_TEMPLATE_DIR`.
