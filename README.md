# hpc-cloudservice

Layanan volunteer computing (pull model): **head node** (koordinator FastAPI + antrean PostgreSQL + validator + dashboard) dan **compute node** (worker relawan dalam kontainer sandbox) di Ubuntu WSL2 + Docker, ditambah portal web Next.js (`web/`).

Panduan lengkap: [COMPOSE-SETUP.md](COMPOSE-SETUP.md).

## Dua repo, dua peran relawan

- **Repo A (repo ini)** = platform HPC: membagi jobdesk (FIFO), menjalankan compute node, memindahkan tugas bila node mati, validasi replikasi, serta web registrasi, login, dashboard admin, dan dashboard relawan.
- **Repo B** = proyek perangkat lunak yang dikerjakan relawan (mis. website/app perusahaan untuk masyarakat), diatur lewat `PROJECT_REPO_URL`. Contoh isinya ada di [contoh-repo-b/](contoh-repo-b/).

Relawan **sebagai developer** otomatis di-assign jobdesk oleh sistem (FIFO, selama compute node-nya online) dan ngoding di branch `task/<id>-<judul>` di repo B. Relawan **sebagai compute node** menjalankan worker; setiap push ke repo B otomatis di-build dan dites terdistribusi di compute node (build → test per file → laporan). Penjelasan lengkap: [docs/PROYEK-REPO-B.md](docs/PROYEK-REPO-B.md).

## Backup, watch, dan peringatan admin

- **Backup** database otomatis tiap jam oleh layanan `backup` di head node: `backup/hourly/` (24 terakhir), `backup/daily/` (7 hari), opsional salinan ke folder cloud (`BACKUP_COPY_DIR`). `.env` disimpan terenkripsi lewat `./hpc.sh backup-env`.
- **Watch** memantau kejadian, bukan folder: error sistem, hasil worker yang beda dari mayoritas, login admin dikunci, webhook palsu, backup gagal/terlambat, dan **cek per branch repo B** (commit di `task/<id>` harus oleh pemilik jobdesk, push ke main harus lewat merge sistem, force push, branch dihapus/asing).
- **Peringatan** tampil di dashboard admin (tab PERINGATAN) dan dikirim ke email admin (digabung, dibatasi).

Penjelasan: [docs/WATCH-BACKUP.md](docs/WATCH-BACKUP.md).

## Penyesuaian terhadap masukan dosen

| Masukan | Implementasi |
| --- | --- |
| Skema rekrutmen relawan (target mahasiswa) + manfaat bagi relawan | Halaman `/join`, kredit tervalidasi, lencana, `/leaderboard`, dashboard relawan dengan data asli, sertifikat kontributor yang bisa diverifikasi (`/certificate/<kode>`). Dokumen: [docs/REKRUTMEN-RELAWAN.md](docs/REKRUTMEN-RELAWAN.md) |
| Hindari Jupyter dan MPI | Tidak ada Jupyter/MPI/Slurm. Tugas = proses Python kecil di sandbox; komunikasi lewat koordinator (HTTP) |
| Tugas berbutir halus, siklus compute → communicate → compute | Job multi-tahap `heat2d`: per tahap 1 tugas kecil per blok, halo dari blok tetangga dikirim koordinator antar-tahap; hasil identik dengan serial. [docs/JOB-MULTI-TAHAP-DAN-REPO.md](docs/JOB-MULTI-TAHAP-DAN-REPO.md) |
| Saran Prof Yudi: commit SHA + branch | Tiap jobdesk punya branch sendiri di repo B (`task/<id>-<judul>`), tiap push dites per commit SHA dan hasilnya jadi centang/silang di GitHub. Kode job komputasi juga dipatok ke commit SHA; hasilnya bisa di-commit ke branch `results/job-<id>` |

## Struktur Proyek

Proyek ini terbagi rapi menjadi dua domain utama: **Frontend Web Portal** (`web/`) dan **Sistem Klaster HPC** (`hpc/`):

```
├── web/                     # PORTAL WEBSITE (Next.js 14, Tailwind CSS, TypeScript)
│   ├── app/                 # Halaman: /overview, /join, /register, /dashboard, /appreciation, /admin
│   ├── components/          # Komponen UI (CyberNavbar, CyberFooter, TerminalCode, dll.)
│   └── lib/                 # Helper API klien & integrasi ke koordinator backend
│
├── hpc/                     # CORE SISTEM CLOUD HPC (Head Node, Compute Nodes, Database)
│   ├── head/                # Head Node: Koordinator API (FastAPI), Validator Quorum, Database PostgreSQL
│   │   ├── coordinator/     # app.py (REST API), validator.py, jobs.py, volunteer.py, project.py, watch.py
│   │   ├── db/              # init.sql (skema PostgreSQL terkelola)
│   │   └── docker-compose.yml
│   ├── compute/             # Compute Worker Node Sandbox (Docker, non-root, cap_drop ALL)
│   │   ├── worker.py        # Daemon worker penarik & pengeksekusi tugas
│   │   └── docker-compose.yml
│   ├── backup/              # Layanan backup database berkala (hourly/daily)
│   ├── watch/               # Pemantauan aktivitas klaster & log runtime
│   ├── job-template/        # Template komputasi HPC ilmiah (run.py)
│   ├── contoh-repo-b/       # Contoh repositori aplikasi untuk pengujian CI terdistribusi
│   ├── tests/               # Pengujian algoritma HPC numerik (test_heat2d.py)
│   └── worker_auth_cli.py   # Skrip CLI autentikasi relawan via terminal (./hpc.sh worker-login)
│
├── hpc.sh                   # Runner CLI utama proyek (head-up, worker-up, job, logs, dll.)
├── .env                     # Konfigurasi variabel lingkungan terpusat
└── docs/                    # Dokumentasi teknis sistem & panduan relawan
```
