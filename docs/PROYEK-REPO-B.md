# Repo A + Repo B: jobdesk relawan dan CI terdistribusi

## Ringkasan

| | Repo A (hpc-cloudservice) | Repo B (proyek aplikasi) |
| --- | --- | --- |
| Isi | Platform HPC: koordinator, validator, worker, web | Aplikasi yang dibangun relawan, mis. website/app perusahaan untuk masyarakat |
| Yang mengubah | Tim pengelola HPC | Relawan (developer), lewat branch masing-masing |
| Relawan perlu clone? | Hanya untuk menjalankan worker (`./hpc.sh worker-up`) | Ya, untuk ngoding di VS Code |
| Hubungan | `PROJECT_REPO_URL` di `.env` repo A menunjuk repo B | Wajib punya `hpc.json` di root |

Relawan punya **dua peran**:

1. **Developer.** Admin membuat jobdesk (fitur/bug). **Sistem** meng-assign jobdesk secara
   **FIFO** (yang paling lama menunggu lebih dulu), tanpa klik, ke relawan yang compute
   node-nya sedang online. Relawan bekerja di branch `task/<id>-<judul>` di repo B. Setiap push menghasilkan commit SHA baru, yaitu "id versi"
   pekerjaan itu (saran Prof Yudi). Satu jobdesk = satu branch, jadi pekerjaan relawan tidak
   saling bentrok.
2. **Compute node.** Laptop relawan menjalankan worker sandbox. Setiap push ke repo B otomatis
   menjadi job CI yang dibagi menjadi tugas kecil dan dikerjakan paralel oleh compute node.

## Alur lengkap

```
Admin (web /admin, tab JOBDESK)          Relawan (web /dashboard)                 GitHub repo B
-------------------------------          ------------------------                 -------------
buat jobdesk #12 -> antrean FIFO
SISTEM: relawan online tanpa jobdesk  ------------------------------------->  branch task/12-... dibuat,
        mendapat #12 (jobdesk tertua)                                          relawan diundang collaborator
                                         git clone, git switch task/12-...
                                         ngoding di VS Code, git push  --------->  commit abc1234
koordinator mendeteksi push (webhook atau polling)
  -> job CI #40 untuk task/12-...@abc1234
     tahap 1 COMPUTE     : 1 tugas build + daftar file test        (2 node, hasil harus sama)
     COMMUNICATE         : koordinator membuat 1 tugas per file test
     tahap 2 COMPUTE     : tugas test tersebar ke banyak node      (FIFO, tiap tugas 2 node)
     COMMUNICATE         : laporan digabung -> LULUS / GAGAL  --------------->  centang/silang di commit
                                         lihat hasil CI di dashboard
                                         (gagal: perbaiki, push lagi)
                                         CI LULUS -> AJUKAN REVIEW  ------------>  sistem membuka Pull Request
review kode di PR, SETUJUI & MERGE  ------------------------------------------>  sistem merge PR ke main
  (kredit masuk, relawan otomatis dapat jobdesk berikutnya) atau MINTA REVISI
```

**Siapa mengerjakan apa:**

| Langkah | Oleh |
| --- | --- |
| Membagi jobdesk ke relawan (FIFO) | Sistem, otomatis |
| Memindahkan tugas komputasi bila compute node mati | Sistem, otomatis (lease 30 detik habis → node lain mengambil tugas itu) |
| Menulis kode | Relawan |
| Menguji kode (build + test terdistribusi) | Sistem, di compute node relawan, setiap push |
| Membuka Pull Request | Sistem, saat relawan mengajukan review |
| Review kode dan keputusan diterima/revisi | **Admin** (manusia) |
| Merge PR ke `main` | Sistem, saat admin menekan *Setujui & merge* |

Admin tidak memindahkan jobdesk antar-relawan, dan sistem juga tidak mencabutnya: jobdesk tetap
milik relawan sampai selesai. Yang dipindah saat compute node tiba-tiba mati adalah **tugas
komputasi** (build/test) yang sedang dijalankan node itu: lease-nya habis setelah 30 detik dan
tugas diambil compute node lain, jadi CI tetap selesai.

Status jobdesk: `open` (antre) → `in_progress` → `review` → `done`. Revisi mengembalikan ke
`in_progress`. Jobdesk baru hanya di-assign ke relawan yang compute node-nya online; relawan yang
menunggu paling lama (jobdesk terakhirnya selesai paling awal) didahulukan.

Merge dipatok ke commit yang lulus CI: bila relawan push lagi setelah mengajukan review,
merge ditolak sampai CI commit baru selesai. Bila PR konflik dengan `main`, admin memilih
*Minta revisi* agar relawan memperbarui branch-nya.

## Kenapa ini tetap HPC

Bagian jobdesk (mirip Jira) sendiri bukan HPC. Bagian jobdesk adalah **sumber pekerjaan**.
HPC-nya ada pada cara pekerjaan komputasi dari setiap push dijalankan:

| Konsep HPC | Di sistem ini |
| --- | --- |
| Dekomposisi tugas berbutir halus | Satu file test = satu tugas (detik), bukan satu CI besar |
| compute → communicate → compute | Build (compute) → koordinator membagi file test (communicate) → test paralel (compute) → laporan digabung (communicate) |
| Penjadwalan | Pull model, FIFO (`ORDER BY id`), pencocokan resource (CPU/RAM) per node |
| Toleransi kesalahan | Lease 30 detik + heartbeat; node mati → tugas pindah ke node lain |
| Validasi hasil | Tiap tugas dikerjakan 2 node, hash SHA-256 hasil harus sama (quorum) |
| Pengukuran kinerja | Tiap CI mencatat jumlah node, waktu nyata, waktu bila 1 node, dan percepatan |

Jenisnya **high-throughput / volunteer computing** (keluarga BOINC, juga mirip CI terdistribusi
seperti GitHub Actions), bukan HPC *tightly-coupled* dengan MPI. Ini sesuai masukan dosen
untuk menghindari MPI. Job komputasi `heat2d` tetap ada sebagai benchmark compute-communicate-compute.

**Catatan jujur soal percepatan:** pada contoh repo B, setiap file test hanya butuh sepersekian
detik. Akibatnya overhead (polling, clone, validasi tiap 1 detik) lebih besar daripada waktu test,
dan percepatan < 1x. Percepatan baru terasa bila test berat (mis. test integrasi 10-60 detik per
file). Untuk laporan, ukur dengan test yang lebih berat: 1, 2, 4, 8 node, lalu bandingkan kolom
"waktu" dan "percepatan" di tab CI.

## Kenapa ini cloud service (definisi NIST)

| Ciri | Di sistem ini |
| --- | --- |
| On-demand self-service | Admin membuat jobdesk di web; push langsung dites tanpa minta ke siapa pun |
| Broad network access | Web + REST API lewat HTTPS |
| Resource pooling | Laptop relawan menjadi satu pool compute node, dipakai bersama semua branch |
| Rapid elasticity | Node bisa bergabung/keluar kapan saja; antrean menyesuaikan |
| Measured service | Kredit, waktu komputasi, dan tugas tervalidasi tercatat per relawan |

Model layanan: mirip **CI/Testing-as-a-Service (PaaS)**. Model deployment: **community cloud**.
Syaratnya, koordinator dan web harus bisa diakses dari luar laptop admin (lihat bagian "Online").

## Repo B yang dipakai

Repo B proyek ini: **https://github.com/ChanceClover/hpc-cloudservice-worker**, yaitu kode worker
(compute node) ringan yang dikembangkan relawan lewat jobdesk. File CI-nya (`hpc.json` dan
`tests/`) disiapkan di folder `repo-b-tambahan/` dan harus di-push ke `main` repo itu, karena
tanpa `hpc.json` setiap CI berstatus error. Isinya: build `python3 -m py_compile worker.py`, lalu
satu tugas test per file (`tests/test_montecarlo.py`, `tests/test_mandelbrot.py`,
`tests/test_koordinator.py`, 12 test). Folder `contoh-repo-b/` tetap ada sebagai contoh lain.

## Cara memasang

1. **Siapkan repo B** di GitHub (publik). Pastikan `hpc.json` dan folder `tests/` sudah ada di `main`
   (untuk repo B di atas: salin isi `repo-b-tambahan/`). Untuk repo baru, bisa mulai dari `contoh-repo-b/`.
2. **Isi `.env` head node:**
   ```
   PROJECT_REPO_URL=https://github.com/ChanceClover/hpc-cloudservice-worker
   PROJECT_APP_NAME=HPC Cloud Service Worker
   PROJECT_POLL_SECONDS=90
   ```
3. **(Disarankan) Token repo B.** Buat *fine-grained personal access token* khusus repo B
   dengan izin *Contents*, *Commit statuses*, *Pull requests*, dan *Administration* (semua
   Read and write). Isi ke `PROJECT_GIT_TOKEN`. Dengan token ini: branch jobdesk dibuat
   otomatis, relawan diundang jadi collaborator, PR dibuka dan di-merge oleh sistem, hasil CI
   tampil sebagai centang di GitHub, dan polling tidak kena batas 60 request/jam.
   Tanpa token: relawan membuat branch sendiri, admin mengundang collaborator, membuka dan
   me-merge PR secara manual di GitHub.
4. **Deteksi push.** Polling sudah cukup (tanpa alamat publik). Untuk reaksi instan, pakai
   webhook: isi `PROJECT_WEBHOOK_SECRET` dengan string acak, lalu di GitHub repo B buka
   *Settings → Webhooks → Add webhook*: Payload URL `https://<alamat-koordinator>/api/webhooks/github`,
   Content type `application/json`, Secret sama, event *Just the push event*.
5. `./hpc.sh head-up`, lalu `./hpc.sh ci main` untuk memastikan CI main lulus.
6. Tambah jobdesk lewat web (tab JOBDESK) atau `./hpc.sh jobdesk-add "Judul" 15 fitur`.

## Perintah

```
./hpc.sh jobdesk-add "<judul>" [kredit] [fitur|bug|lainnya]
./hpc.sh jobdesks
./hpc.sh ci [branch]
./hpc.sh ci-status [n]
```

API: `GET /api/project` (publik), `GET /api/me/jobdesk`, `POST /api/me/jobdesk/<id>/submit`
(token relawan), `GET|POST /api/admin/jobdesks`, `POST /api/admin/jobdesks/<id>/action`,
`GET|POST /api/admin/ci`, `GET /api/admin/ci/<job>/log` (admin), `POST /api/webhooks/github`.

## Keamanan

- Kode dari branch relawan dijalankan di laptop relawan lain. Karena itu tetap di sandbox
  Docker: read-only, tanpa capability, maks 64 proses, RAM dan CPU dibatasi, `/tmp` di RAM.
- Proses worker ditandai *non-dumpable*, sehingga test di repo B **tidak bisa membaca
  `WORKER_TOKEN`** dari `/proc/<pid>/environ` worker (sudah diuji: tanpa ini token terbaca).
  Perintah build/test juga dijalankan dengan environment kosong.
- Hanya branch `main` dan `task/*` yang di-CI. Hanya relawan terdaftar (GitHub + OTP) yang
  diundang collaborator, jadi setiap commit bisa ditelusuri ke akun GitHub-nya.
- Jobdesk hanya bisa diajukan review bila CI commit terakhir lulus (`REQUIRE_CI_PASS=1`), tapi
  persetujuan tetap oleh admin (review kode manusia).
- Webhook diverifikasi HMAC-SHA256 (`X-Hub-Signature-256`).

## Batasan saat ini

- Runtime compute node hanya Python 3.12 + git. Bila repo B memakai Node.js/Java, tambahkan
  paketnya di `compute/Dockerfile`.
- Test di repo B harus deterministik. Test yang hasilnya berubah-ubah (mis. bergantung waktu
  atau jaringan) akan dianggap tidak sepakat antar-replika dan ditandai error.
- `/tmp` worker 128 MB: cukup untuk repo kecil-menengah, tidak untuk repo dengan `node_modules` besar.
- Jobdesk tidak punya batas waktu. Bila relawan berhenti total, admin bisa *Batal* lalu
  *Buka lagi* agar jobdesk itu kembali ke antrean.
