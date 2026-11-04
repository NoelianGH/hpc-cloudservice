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
| `WORKER_TOKEN` | head + compute | token relawan sementara, harus sama di semua laptop |
| `COORDINATOR_URL` | compute | `http://host.docker.internal:8000` (laptop yang sama) atau alamat `https://...trycloudflare.com` |
| `WORKER_NAME` | compute | nama yang tampil di dashboard |

## Head node

```bash
./hpc.sh head-up            # build & jalankan; dashboard di http://localhost:8000
./hpc.sh head-online        # alamat HTTPS untuk laptop relawan lain
./hpc.sh job                # 20 tugas Monte Carlo pi
./hpc.sh job mandelbrot 20  # 20 strip Mandelbrot
```

## Compute node

Isi `COORDINATOR_URL` dan `WORKER_TOKEN` di `.env`, lalu:

```bash
./hpc.sh worker-up          # 1 worker; ./hpc.sh worker-up 2 untuk 2 worker
./hpc.sh worker-logs
```

Setiap tugas direplikasi ke 2 worker berbeda, jadi minimal harus ada 2 worker aktif.

## Uji

| Uji | Perintah | Yang diharapkan |
| --- | --- | --- |
| Antrean + replikasi | `./hpc.sh job` lalu `./hpc.sh worker-up 2` | tugas `done` bertambah, pi ≈ 3.1415 |
| Worker mati mendadak | `docker kill hpc-worker-worker-1` | ±30 detik kemudian log validator: "lease habis", tugas dikerjakan worker lain |
| Hasil palsu | `./hpc.sh worker-cheat` | log validator: "tidak sepakat, tambah replika"; kredit `curang-*` tetap 0 |

## Catatan

- Autentikasi masih token bersama di `.env`; login GitHub dikerjakan terpisah.
- Jenis tugas: `montecarlo_pi` (bawaan 30 juta sampel) dan `mandelbrot` (bawaan 2000 px). Targetnya 5–15 detik per tugas; ubah `size` di `head/coordinator/app.py` bila terlalu cepat/lambat.