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

## Uji

| Uji | Perintah | Yang diharapkan |
| --- | --- | --- |
| Autentikasi CLI | `./hpc.sh worker-login` | GitHub diverifikasi, OTP diterima, status terverifikasi |
| Antrean + replikasi | `./hpc.sh job` lalu `./hpc.sh worker-up 2` | tugas `done` bertambah, pi ≈ 3.1415 |
| Worker mati mendadak | `docker kill hpc-worker-worker-1` | ±30 detik kemudian log validator: "lease habis", tugas dikerjakan worker lain |
| Hasil palsu | `./hpc.sh worker-cheat` | log validator: "tidak sepakat, tambah replika"; kredit `curang-*` tetap 0 |

## Catatan

- Jenis tugas: `montecarlo_pi` (bawaan 30 juta sampel) dan `mandelbrot` (bawaan 2000 px). Targetnya 5–15 detik per tugas; ubah `size` di `head/coordinator/app.py` bila terlalu cepat/lambat.
