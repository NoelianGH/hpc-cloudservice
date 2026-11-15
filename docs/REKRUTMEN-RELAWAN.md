# Skema rekrutmen relawan

Menjawab masukan dosen #1: skema rekrutmen yang jelas dengan target mahasiswa, dan relawan harus mendapat manfaat.

## Sasaran

| Kelompok | Alasan | Jalur |
| --- | --- | --- |
| Mahasiswa Informatika/Ilmu Komputer (angkatan 2022–2025) | sudah punya laptop dan akun GitHub, tertarik Docker/sistem terdistribusi | grup kelas/angkatan, asisten praktikum, himpunan mahasiswa |
| Peserta mata kuliah HPC / Sistem Terdistribusi | relevan langsung dengan materi kuliah | pengumuman dosen di kelas, LMS |
| Anggota komunitas/UKM teknologi kampus | terbiasa ikut proyek terbuka | poster digital + demo singkat di pertemuan komunitas |

Target uji: **minimal 5–10 relawan aktif** (kriteria keberhasilan proposal: ≥ 5 worker bergabung melalui panduan).

## Syarat bergabung

- Laptop Windows 10/11 dengan WSL2 (Ubuntu) + Docker Desktop, atau Linux dengan Docker.
- Akun GitHub berumur ≥ 30 hari dengan ≥ 2 repositori publik (diperiksa otomatis, mencegah akun palsu/Sybil).
- Email aktif untuk OTP.

## Manfaat untuk relawan

| Manfaat | Cara kerja di sistem |
| --- | --- |
| **Kredit tervalidasi** | +1 kredit (atau `credit_per_task` job) per tugas yang hasilnya sama dengan quorum. Hasil palsu tidak memberi kredit. (`head/coordinator/validator.py`) |
| **Lencana** | Perintis ≥ 1, Perunggu ≥ 25, Perak ≥ 100, Emas ≥ 250 kredit. (`head/coordinator/volunteer.py`) |
| **Leaderboard publik** | `/leaderboard` di web dan `./hpc.sh leaderboard`: peringkat, kredit, tugas valid, persentase ditolak, menit komputasi. Email tidak pernah ditampilkan. |
| **Sertifikat kontributor** | Bisa diambil di dashboard relawan bila kredit ≥ `CERT_MIN_CREDITS` (bawaan 50) dan hasil ditolak ≤ `CERT_MAX_REJECT_PCT` (bawaan 10%). Setiap sertifikat punya kode `HPC-XXXXXXXXXX` yang bisa diverifikasi publik di `/certificate/<kode>`; bisa dicetak/disimpan sebagai PDF. Sertifikat otomatis tampil "DICABUT" bila worker ditangguhkan admin. |
| **Pengalaman praktis** | Docker, WSL2, sandboxing, sistem terdistribusi. Cocok untuk portofolio/CV/LinkedIn. |
| **Kontrol penuh** | Worker dibatasi 1 CPU / 512 MB (bisa diubah di `.env`), bisa dimatikan kapan saja. Tugas yang terputus otomatis dialihkan ke relawan lain. |

## Alur bergabung (tercantum juga di halaman web `/join`)

1. **Daftar**: halaman `/register` atau `./hpc.sh worker-login` → verifikasi GitHub → OTP email → dapat `WORKER_TOKEN` pribadi.
2. **Siapkan laptop**: clone repo, isi `WORKER_TOKEN`, `WORKER_ID`, `COORDINATOR_URL` di `.env`.
3. **Nyalakan worker**: `./hpc.sh worker-up 1`.
4. **Pantau**: login di `/login` dengan token → `/dashboard` (kredit, peringkat, riwayat tugas, job di antrean).
5. **Ambil sertifikat** setelah syarat terpenuhi.

## Jadwal kampanye (usulan, minggu ke-9–10 proposal)

| Hari | Kegiatan |
| --- | --- |
| H-7 | Sebar poster + tautan `/join` ke grup kelas/angkatan dan himpunan; minta izin dosen untuk pengumuman di kelas |
| H-3 | Sesi daring 30 menit: demo pendaftaran + menjalankan worker, tanya jawab |
| H | Uji bersama: head node online (`./hpc.sh head-online`), job `heat2d` dan Monte Carlo dijalankan, leaderboard ditayangkan |
| H+1 s.d. H+7 | Worker tetap berjalan sukarela; sertifikat bisa diambil; kumpulkan umpan balik (kuesioner singkat) |

## Ukuran keberhasilan rekrutmen

- Jumlah pendaftar vs yang lolos verifikasi GitHub (tab *Pendaftaran* di dashboard admin).
- Jumlah relawan aktif bersamaan (worker online) dan total menit komputasi.
- Jumlah sertifikat terbit, persentase hasil ditolak.

## Privasi

Yang disimpan: nama worker, username GitHub, email (hanya untuk OTP, tidak tampil publik), catatan tugas. Relawan bisa meminta admin menangguhkan/menghapus data mereka.
