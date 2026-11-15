# Cloud Service HPC

Volunteer computing berbasis pull model: **head node** (koordinator FastAPI + antrean PostgreSQL + validator + dashboard) dan **compute node** (worker dalam kontainer sandbox). Semua dijalankan dengan Docker di Ubuntu WSL2.

## Pasang proyek (sekali per laptop)

```bash
cd ~
git clone https://github.com/USERNAME/cloud-hpc.git
cd ~/cloud-hpc
chmod +x hpc.sh     # sekali saja setelah clone
./hpc.sh            # menampilkan daftar perintah dan membuat .env
```

Simpan proyek di `~` (filesystem Linux), bukan di `/mnt/c`. Butuh Docker Desktop dengan WSL Integration aktif (cek: `docker compose version`).

## Konfigurasi `.env`

| Variabel | Dipakai di | Isi |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | head | password database |
| `ADMIN_TOKEN` | head | token untuk membuat job |
| `WORKER_TOKEN` | head + compute | token relawan (bisa dari hasil `./hpc.sh worker-login` atau token bersama) |
| `COORDINATOR_URL` | compute | `http://host.docker.internal:8000` (laptop yang sama) atau alamat `https://...trycloudflare.com` |
| `WORKER_NAME` | compute | nama yang tampil di dashboard |
| `GITHUB_TOKEN` | head (opsional) | token personal GitHub untuk menaikkan batas rate limit API |
| `SMTP_HOST` | head (opsional) | host SMTP email OTP (kosongkan untuk mode simulasi dev di log server) |

## Head node

```bash
./hpc.sh head-up            # build & jalankan; dashboard di http://localhost:8000
./hpc.sh head-online        # alamat HTTPS untuk laptop relawan lain
./hpc.sh job                # 20 tugas Monte Carlo pi
./hpc.sh job mandelbrot 20  # 20 strip Mandelbrot
```

## Autentikasi Worker (CLI Login)

Sebelum worker dijalankan dan menerima tugas, worker relawan dapat melakukan autentikasi identitas melalui CLI:

```bash
./hpc.sh worker-login
# atau langsung jalankan script Python:
python3 worker_auth_cli.py
```

### Alur Autentikasi:
1. **Input Identitas**: User memasukkan nama worker, username GitHub, dan email di CLI.
2. **Pengecekan Anti-Fake Worker**: Koordinator memeriksa reputasi akun GitHub calon worker melalui GitHub REST API:
   - **Faktor Utama 1 (Usia Akun)**: Minimal 30 hari (mencegah akun bot instan / throwaway).
   - **Faktor Utama 2 (Jumlah Proyek/Repositori)**: Minimal 2 repositori publik (memastikan ada jejak kontribusi developer asli).
   - **Faktor Tambahan 3 (Jumlah Pengikut/Followers)**: Mendeteksi akun bot (umumnya 0 followers).
   - **Faktor Tambahan 4 (Kelengkapan Profil)**: Menilai keberadaan nama lengkap, bio, dan informasi profil.
   - **Faktor Tambahan 5 (Aktivitas Akun)**: Memeriksa waktu pembaruan terakhir (`updated_at`).
   - **Faktor Tambahan 6 (Rasio Spam)**: Mendeteksi akun yang mem-follow banyak orang tanpa pengikut.
   - **Faktor Tambahan 7 (Tipe Entitas)**: Memastikan akun bertipe personal `User`, bukan bot/organisasi.
3. **Pengiriman Email OTP**: Jika lolos, koordinator mengirimkan kode OTP 6-digit ke email user (atau dicatat di log bila mode simulasi dev aktif).
4. **Verifikasi OTP di CLI**: User memasukkan kode OTP ke CLI dalam batas waktu 10 menit.
5. **Penerbitan Worker Token**: Jika valid, koordinator menerbitkan `WORKER_TOKEN` unik dan menandai status worker sebagai `active` (terverifikasi). CLI akan menawarkan opsi untuk otomatis memperbarui file `.env`.

## Menjalankan Compute node

Setelah worker memiliki token (baik via `./hpc.sh worker-login` atau token bersama di `.env`), jalankan:

```bash
./hpc.sh worker-up          # 1 worker; ./hpc.sh worker-up 2 untuk 2 worker
./hpc.sh worker-logs
```

Setiap tugas direplikasi ke 2 worker berbeda, jadi minimal harus ada 2 worker aktif.

## Dashboard admin (web `/admin`)

Admin login dengan **email + password**. Password tidak pernah disimpan dalam bentuk asli: `.env` hanya berisi hash PBKDF2-SHA256.

```bash
./hpc.sh admin-setup   # isi email admin + password (min. 10 karakter) -> ADMIN_EMAIL & ADMIN_PASSWORD_HASH di .env
./hpc.sh head-up       # jalankan ulang koordinator agar konfigurasi admin terbaca
./hpc.sh web-dev       # buka http://localhost:3000/admin
```

Isi dashboard (semua data langsung dari koordinator, auto-refresh 5 detik):

- **Ringkasan**: worker online, tugas selesai/antre/invalid, hasil masuk per menit, lease habis (worker keluar mendadak), grafik throughput 10 menit, aktivitas terbaru.
- **Worker**: email, GitHub, kredit, jumlah hasil yang berbeda dari quorum (indikasi curang), tombol *Tangguhkan/Aktifkan* dan *Cabut token*.
- **Job & Tugas**: buat job baru, progres tiap job (π untuk Monte Carlo), daftar tugas, dan detail validasi tiap tugas (hasil setiap replika, sepakat atau tidak).
- **Pendaftaran**: riwayat pendaftaran relawan (GitHub + OTP). Kode OTP tidak pernah ditampilkan.

Keamanan:

- Sesi login disimpan sebagai cookie `httpOnly` + `SameSite=Strict` (tidak bisa dibaca JavaScript), berlaku `ADMIN_SESSION_HOURS` jam (bawaan 8), dan dicek koordinator di setiap request `/api/admin/*`. Logout langsung menghapus sesi di database.
- 5 kali salah password untuk satu email mengunci login selama 15 menit.
- `/api/stats` (publik) tidak lagi memuat email maupun `worker_id` relawan; data lengkap hanya lewat `/api/admin/*`.
- `ADMIN_TOKEN` tetap berlaku untuk perintah CLI seperti `./hpc.sh job`.

## Uji

| Uji | Perintah | Yang diharapkan |
| --- | --- | --- |
| Autentikasi CLI | `./hpc.sh worker-login` | GitHub diverifikasi, OTP diterima, status terverifikasi |
| Antrean + replikasi | `./hpc.sh job` lalu `./hpc.sh worker-up 2` | tugas `done` bertambah, pi ≈ 3.1415 |
| Worker mati mendadak | `docker kill hpc-worker-worker-1` | ±30 detik kemudian log validator: "lease habis", tugas dikerjakan worker lain |
| Hasil palsu | `./hpc.sh worker-cheat` | log validator: "tidak sepakat, tambah replika"; kredit `curang-*` tetap 0 |
| Login admin | buka `http://localhost:3000/admin` | diarahkan ke `/admin/login`; setelah login tampil data worker & tugas asli |
| Tangguhkan worker | tab Worker → *Tangguhkan* pada worker `curang` | worker itu ditolak saat claim (HTTP 403) |
| Job multi-tahap | `./hpc.sh job heat2d` lalu `./hpc.sh worker-up 2` | log validator: "tahap 0 selesai -> tahap 1/9 dibuat" ... "sama dengan serial: True"; heatmap di `/api/jobs/<id>/heatmap.png` |
| Kebenaran heat2d tanpa Docker | `python3 tests/test_heat2d.py` | "SEMUA UJI LULUS" (hasil terdistribusi identik dengan serial) |
| Resource job | job dengan memori 2048 MB (form admin) | tidak diambil worker 512 MB; tetap antre |
| Repo job + SHA | `./hpc.sh job-repo <sha> prime_count 10` | log worker: "[repo] ... @ <sha> siap"; hasil tervalidasi |
| Program job rusak | job-repo ke SHA tanpa `run.py` | worker melapor gagal; setelah 2 worker gagal tugas `invalid`, job `failed` |
| Login relawan | web `/login` dengan token asal-asalan | ditolak; dengan token hasil `worker-login` masuk ke `/dashboard` berisi kredit asli |
| Sertifikat | dashboard relawan → *Ambil sertifikat* (setelah kredit ≥ `CERT_MIN_CREDITS`) | kode `HPC-...`; `/certificate/<kode>` bisa dibuka siapa pun |
| CI repo B | isi `PROJECT_REPO_URL`, `./hpc.sh head-up`, `./hpc.sh ci main` | `./hpc.sh ci-status`: tahap build → test, status `passed`, kolom node ≥ 2 |
| Assign otomatis FIFO | `./hpc.sh jobdesk-add "Judul"` 2x, lalu 2 relawan menjalankan `./hpc.sh worker-up` | tanpa klik, relawan yang online mendapat jobdesk tertua; relawan yang worker-nya mati tidak mendapat jobdesk |
| Compute node mati di tengah CI | `docker kill` worker yang sedang menjalankan tugas test | ±30 detik kemudian tugas itu dikerjakan compute node lain; jobdesk relawan pemilik node tetap miliknya |
| Push gagal / lulus | push commit yang merusak test ke branch `task/...` | CI `GAGAL` + nama file test yang gagal; *Ajukan review* ditolak sampai CI lulus |
| PR + merge | CI lulus → *Ajukan review* → admin *Setujui & merge* | PR dibuka sistem, di-merge ke `main` (squash) pada commit yang lulus CI; kredit masuk; relawan langsung dapat jobdesk berikutnya |
| Push beruntun | push 2x berturut-turut ke branch yang sama | CI commit pertama `DIBATALKAN`, CI commit kedua berjalan |
| Node mati saat test | `docker kill hpc-worker-worker-1` ketika tab CI menunjukkan tugas test berjalan | ±30 detik kemudian nama node dicoret, tugas dikerjakan node lain, CI tetap selesai |

## Proyek repo B: jobdesk relawan + CI terdistribusi

Relawan ngoding di repo B (aplikasi yang dibangun), tiap jobdesk di branch `task/<id>-<judul>`.
Setiap push otomatis di-build dan dites terdistribusi di compute node. Cara memasang
(`PROJECT_REPO_URL`, token, webhook) dan alasannya tetap HPC & cloud service: `docs/PROYEK-REPO-B.md`.
Contoh repo B: `contoh-repo-b/`.

## Job multi-tahap, repo job, dan insentif relawan

Ringkas (detail di `docs/`):

- `./hpc.sh job heat2d [blok] [tahap] [langkah] [N]`: simulasi panas 2D, tiap tahap = 1 tugas kecil per blok baris; antar-tahap koordinator mengirim baris tepi (halo) dari blok tetangga. Lihat `docs/JOB-MULTI-TAHAP-DAN-REPO.md`.
- Kode tugas bisa diambil dari **repo job terpisah** pada **commit SHA** tertentu (`JOB_REPO_URL` di `.env`, contoh isi repo di `job-template/`). Hasil job di-commit **hanya oleh head node** ke branch `results/job-<id>` bila `RESULTS_GIT_TOKEN` diisi.
- Setiap job punya **spesifikasi resource** per tugas (CPU, memori, batas waktu). Antrean tetap **FIFO**: worker selalu mendapat tugas tertua yang muat di sandbox-nya.
- Relawan mendapat kredit tervalidasi, lencana, tempat di `/leaderboard`, dan sertifikat kontributor (`/certificate/<kode>`). Skema rekrutmen: `docs/REKRUTMEN-RELAWAN.md`, halaman web `/join`.

## Catatan

- Jenis tugas: `montecarlo_pi` (bawaan 30 juta sampel), `mandelbrot` (bawaan 2000 px), `heat2d` (multi-tahap), dan `repo` (program dari repo job). Ukuran bawaan ada di `head/coordinator/jobs.py`.
- Tidak memakai Jupyter maupun MPI: semua tugas adalah proses Python kecil di kontainer sandbox, komunikasi antar-tahap lewat koordinator (HTTP).
