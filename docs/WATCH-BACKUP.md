# Backup, watch, dan peringatan admin

## Apakah proyek ini perlu?

Perlu, karena head node berjalan di **satu laptop** (titik tunggal kegagalan) dan menerima kode
serta hasil dari banyak relawan yang tidak dikenal satu per satu. Tetapi bentuknya disesuaikan:

| | Yang dijaga | Yang tidak perlu |
| --- | --- | --- |
| Backup | Database koordinator: akun relawan, kredit, sertifikat, jobdesk, riwayat CI, peringatan | Kode repo B (sudah aman di GitHub, lengkap dengan riwayat commit per branch). Kode repo A (sudah di GitHub) |
| Watch | Kejadian yang berarti: error, aktivitas mencurigakan, push per branch, backup | Memantau setiap perubahan file di folder. Kodenya ada di Git, jadi setiap perubahan sudah tercatat sebagai commit |

## Backup otomatis tiap jam

Layanan `backup` (ikut jalan dengan `./hpc.sh head-up`) menjalankan `head/backup/backup.sh`:

1. Tiap awal jam: `pg_dump` database ke `backup/hourly/hpc-db-<tanggal>-<jam>.sql.gz`.
2. Backup dicek: isinya harus memuat tabel `workers` dan file gzip harus utuh (`gzip -t`), lalu
   dicatat di tabel `backups` beserta ukuran dan SHA-256.
3. Backup pertama tiap hari disalin ke `backup/daily/`.
4. Rotasi: simpan 24 backup per jam dan 7 backup harian (`BACKUP_KEEP_HOURLY`, `BACKUP_KEEP_DAILY`).
5. Bila `BACKUP_COPY_DIR` diisi (mis. folder Google Drive/OneDrive di Windows, dari WSL:
   `/mnt/c/Users/<nama>/Google Drive/hpc-backup`), backup juga disalin ke sana. Ini penting:
   backup di laptop yang sama ikut hilang bila laptop rusak.

Koordinator memberi peringatan **critical** bila backup gagal, atau bila backup berhasil terakhir
lebih tua dari `BACKUP_MAX_AGE_MIN` (bawaan 130 menit).

`.env` tidak ikut backup otomatis karena berisi password dan token. Simpan terenkripsi:
`./hpc.sh backup-env` (AES-256, passphrase Anda), pulihkan dengan `./hpc.sh restore-env <file>`.
Isi backup database juga sensitif (token worker, email relawan), jadi `BACKUP_COPY_DIR` harus
folder pribadi, bukan folder yang dibagikan.

```
./hpc.sh backup                  backup sekarang juga
./hpc.sh backups [n]             daftar backup terakhir (berhasil/gagal, salinan luar)
./hpc.sh restore <file>          pulihkan (minta konfirmasi, kondisi sebelum restore di-backup dulu)
./hpc.sh backup-env              .env terenkripsi ke backup/env/
```

## Watch: pemantauan kejadian

`head/coordinator/watch.py` dijalankan validator setiap 20 detik dan juga dipanggil langsung oleh
API (login admin, webhook).

| Jenis | Yang dideteksi | Level |
| --- | --- | --- |
| Error sistem | CI berstatus error; CI branch `main` gagal; tugas invalid karena program terus gagal; publikasi hasil gagal; langkah validator (polling/assign) gagal | warning / critical (CI main) |
| Mencurigakan | Hasil worker beda dari mayoritas (quorum); worker beda >= `WATCH_MISMATCH_LIMIT` kali dalam 24 jam (indikasi curang); login admin dikunci setelah 5x password salah; webhook dengan tanda tangan salah; webhook dari repo lain | warning / critical |
| Cek branch | Lihat bagian berikut | info / warning / critical |
| Backup | Gagal, terlambat, salinan ke folder luar gagal | critical / warning |
| Compute node | Node mati di tengah tugas (lease habis), tugasnya otomatis pindah ke node lain | info |

## Apakah watch dan backup mengecek setiap branch?

- **Backup: tidak per branch.** Semua branch repo B sudah tersimpan di GitHub. Status setiap
  branch di sistem (jobdesk, hasil CI per commit) ada di database, dan database itulah yang
  di-backup, jadi semua branch ikut terlindungi.
- **Watch: ya, per branch, setiap push** (dari webhook atau polling). Saat push masuk, sistem
  menunggu 15 detik lalu mengecek:

| Branch | Aturan | Bila dilanggar |
| --- | --- | --- |
| `task/<id>-...` | Semua commit yang belum ada di `main` harus milik akun GitHub relawan pemilik jobdesk itu | critical |
| `task/<id>-...` | Yang push (dari webhook) harus pemilik jobdesk | critical |
| `task/<id>-...` | Jobdesk harus masih aktif (`in_progress`/`review`); branch harus punya jobdesk | warning |
| `task/<id>-...` | Email git commit harus terhubung ke akun GitHub agar bisa ditelusuri | info |
| `main` | Setiap perubahan harus hasil *Setujui & merge* oleh sistem | warning (info bila tanpa `PROJECT_GIT_TOKEN`, karena merge manual) |
| semua | Force push (riwayat ditulis ulang) | warning (critical di `main`) |
| semua | Branch jobdesk aktif atau `main` dihapus (webhook) | critical |
| lainnya | Branch di luar aturan (bukan `main` atau `task/*`) | warning |

Commit dari `main` yang ikut masuk ke branch relawan (mis. `git merge main` untuk menyelesaikan
konflik) tidak dihitung, karena yang dicek hanya commit yang belum ada di `main`. Commit yang
sudah pernah dilaporkan tidak dilaporkan lagi di push berikutnya.

Catatan: author commit diambil dari email git, yang bisa diatur sendiri oleh relawan. Yang paling
bisa dipercaya adalah *pusher* dari webhook (akun GitHub yang benar-benar push), jadi webhook
lebih kuat daripada polling. Pencegahan terbaik tetap di GitHub: aktifkan **branch protection**
pada `main` (wajib lewat PR, tanpa force push), sehingga watch menjadi lapisan kedua.

## Peringatan untuk admin

- **Dashboard admin, tab PERINGATAN:** jumlah yang belum ditangani (critical/warning/info), status
  email, status backup terakhir, daftar peringatan dengan filter jenis, dan tombol *Sudah
  ditangani*. Bila ada critical, tab berwarna merah dan tab RINGKASAN menampilkan banner.
- **Email ke admin:** dikirim ke `ALERT_EMAIL_TO` (kosong = `ADMIN_EMAIL`) dengan metode email
  yang sama dengan OTP. Beberapa peringatan digabung dalam satu email, paling sering tiap
  `ALERT_EMAIL_COOLDOWN_MIN` menit (critical paling cepat 2 menit), hanya level >=
  `ALERT_EMAIL_MIN_LEVEL`. Tanpa metode email, isi email dicatat di log validator.
- Peringatan tidak dobel: setiap kejadian punya kunci unik. Kejadian berulang (mis. webhook
  palsu) dihitung per jam (x2, x3, ...) dan dibuka lagi bila sudah ditandai ditangani.
- Terminal: `./hpc.sh alerts [all]`, `./hpc.sh alert-ack <id|all>`.

API: `GET /api/admin/alerts?state=open|all`, `POST /api/admin/alerts/<id>/ack`,
`POST /api/admin/alerts/ack-all`, `GET /api/admin/backups`.

## Folder `watch/` (log mentah)

`./hpc.sh watch-start` tetap bisa dipakai untuk menyimpan log mentah docker ke `watch/` (berguna
untuk menelusuri setelah ada peringatan). Log di atas 50 MB diputar saat `watch-start`.
`./hpc.sh watch` kini juga menampilkan peringatan yang belum ditangani.
