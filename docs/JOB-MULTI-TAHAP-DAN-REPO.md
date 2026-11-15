# Job multi-tahap, repo job (commit SHA), resource, dan branch hasil

Menjawab masukan dosen #2 (tanpa Jupyter/MPI) dan #3 (tugas berbutir halus dengan siklus compute → communicate → compute), serta saran Prof Yudi (pakai commit SHA dan branch agar pekerjaan tidak bentrok).

## 1. Tanpa Jupyter dan MPI

Tidak ada JupyterHub, MPI, maupun Slurm di sistem ini. Setiap tugas adalah proses Python kecil di dalam kontainer sandbox. Komunikasi antar-tugas tidak langsung worker-ke-worker (seperti MPI), tetapi lewat koordinator melalui HTTP, karena laptop relawan berada di balik NAT dan bisa keluar kapan saja.

## 2. Job multi-tahap `heat2d` (compute → communicate → compute)

Simulasi persamaan panas 2D (skema eksplisit), grid N × N:

```
T_baru[i][j] = T[i][j] + alpha * (T[i-1][j] + T[i+1][j] + T[i][j-1] + T[i][j+1] - 4*T[i][j])
```

- Grid dibagi menjadi **B blok baris**. Satu **tahap** = B tugas kecil (satu per blok), masing-masing menghitung **K langkah waktu**.
- **Compute**: worker menerima baris bloknya + **halo** K baris dari blok atas dan bawah, menghitung K langkah, mengembalikan baris bloknya sendiri.
- **Communicate**: setelah semua blok satu tahap tervalidasi (replikasi + quorum), validator menyusun grid lalu membuat tugas tahap berikutnya berisi halo terbaru dari blok tetangga.
- **Compute** lagi untuk tahap berikutnya, sampai tahap terakhir. Hasil akhir: grid, ringkasan (rata-rata, min, maks, SHA-256 grid), dan heatmap PNG.

Halo setebal K baris membuat baris blok tepat setelah K langkah (baris halo terluar menjadi "basi", tetapi tidak mencapai blok). Hasilnya **identik bit-per-bit** dengan perhitungan serial: dibuktikan oleh `python3 tests/test_heat2d.py` dan opsi `verify_serial` (dipakai otomatis oleh `./hpc.sh job heat2d`; hasilnya tampil "identik dengan serial" di dashboard admin).

Parameter (form admin atau API `POST /api/jobs`):

| Parameter | Bawaan | Arti |
| --- | --- | --- |
| `n_tasks` / `params.blocks` | 8 | jumlah blok = tugas per tahap |
| `params.stages` | 10 | jumlah tahap |
| `params.steps` | 20 | langkah waktu per tahap (= tebal halo) |
| `params.n` | 160 | ukuran grid N × N |
| `params.alpha` | 0.2 | koefisien difusi (≤ 0.25 agar stabil) |

Contoh: `./hpc.sh job heat2d 8 10 20 160`.

### Eksperimen granularitas (untuk laporan)

Total kerja tetap (mis. N = 160, 200 langkah), ubah ukuran butir:

| Konfigurasi | Tugas | Kerja per tugas | Data per tugas |
| --- | --- | --- | --- |
| `./hpc.sh job heat2d 4 5 40` | 4 × 5 = 20 | besar | halo 40 baris |
| `./hpc.sh job heat2d 8 10 20` | 8 × 10 = 80 | sedang | halo 20 baris |
| `./hpc.sh job heat2d 16 20 10` | 16 × 20 = 320 | kecil | halo 10 baris |

Catat durasi job (kolom *Durasi* di dashboard admin / `./hpc.sh job-result <id>`) untuk 1, 2, 4 worker. Butir terlalu kecil → overhead komunikasi + sinkronisasi antar-tahap dominan; terlalu besar → paralelisme kurang. Itulah trade-off compute vs communicate yang diminta dosen.

## 3. Antrean FIFO

Worker menarik tugas (pull model) dan selalu mendapat **tugas tertua** (urut id) yang:
- belum pernah ia kerjakan (replika harus dari worker berbeda), dan
- spesifikasi resource job-nya muat di sandbox worker.

Tugas tahap berikutnya baru masuk antrean setelah tahap sebelumnya selesai, jadi ikut antre di belakang tugas yang sudah ada.

## 4. Spesifikasi resource per job

`resources: {"cpus": 1, "memory_mb": 256, "timeout_s": 120}` (bawaan).
- Worker melaporkan kapasitas sandboxnya (`WORKER_CPUS`, `WORKER_MEMORY_MB` di `.env`, sama dengan batas kontainer). Job yang butuh lebih besar tidak diberikan ke worker itu.
- `timeout_s`: heartbeat dan submit ditolak setelah batas waktu; program dari repo job juga dihentikan worker (`RLIMIT_CPU`, `RLIMIT_AS`, timeout proses).

## 5. Repo job terpisah, dipatok ke commit SHA

Repo HPC (ini) dan repo job (kode tugas) dipisah. Contoh isi repo job ada di `job-template/` (salin ke repo baru).

```
job:  {"kind": "repo", "task_kind": "prime_count", "n_tasks": 10,
       "code": {"repo_url": "https://github.com/ORG/hpc-jobs", "sha": "<40 hex>", "entry": "python3 run.py"}}
```

- `sha` **wajib commit SHA lengkap**, bukan nama branch: semua replika menjalankan kode yang sama persis, dan relawan bisa mengaudit kode itu di GitHub.
- Worker meng-clone repo ke `/tmp` di dalam sandbox, checkout SHA itu, memastikan `git rev-parse HEAD == sha`, lalu menjalankan `entry` dengan JSON di stdin. Cache per SHA.
- Hanya repo dengan awalan `JOB_REPO_ALLOWLIST` (koordinator) dan `ALLOWED_REPO_PREFIXES` (worker) yang dipakai; bawaan `https://github.com/`.
- Job `heat2d`/`montecarlo_pi` juga boleh diberi `code`: koordinator tetap mengatur tahap & halo, tetapi kernel diambil dari repo job.
- Program yang gagal dilaporkan worker (`/api/tasks/fail`); setelah gagal di 2 worker berbeda tugas ditandai invalid sehingga job rusak tidak berputar selamanya.

Repo job belum ditentukan, jadi semuanya lewat konfigurasi `.env`: `JOB_REPO_URL`, `JOB_REPO_ENTRY`, `JOB_REPO_ALLOWLIST`.

## 6. Hasil ke branch per job (hanya head node yang commit)

Saat job selesai, validator membuat **satu commit** berisi `results/job-<id>/result.json`, `README.md`, dan `heatmap.png` (heat2d) di branch `results/job-<id>` lewat GitHub API.

- Repo tujuan: `RESULTS_REPO_URL`, atau repo job itu sendiri bila kosong. Pada repo job, branch hasil berinduk tepat pada commit SHA kode yang dipakai (jejak asal jelas).
- Token: `RESULTS_GIT_TOKEN` (fine-grained token, izin *Contents: Read and write* hanya pada repo itu). **Worker tidak pernah memegang token GitHub.**
- Satu branch per job → tidak ada dua job yang menulis ke branch yang sama (tidak bentrok).
- Bila token kosong, publikasi dilewati; hasil tetap ada di `GET /api/jobs/<id>/result`.

## 7. Validasi berbasis hash

Koordinator menghitung SHA-256 dari JSON kanonik setiap hasil saat submit (tidak memercayai hash dari worker). Validator mengelompokkan replika berdasarkan hash; kelompok ≥ 2 = valid. Bila tidak sepakat, replika ditambah sampai 4; bila tetap tidak sepakat, tugas invalid.
