# Layanan Pengaduan Masyarakat (contoh repo B)

Contoh **repo proyek** yang dikerjakan relawan Cloud Service HPC. Salin isi folder ini ke
repo GitHub baru (publik), lalu isi `PROJECT_REPO_URL` di `.env` head node dengan URL repo itu.

Aplikasinya kecil dan tanpa library luar: warga mengirim pengaduan (jalan rusak, sampah, air),
pemerintah daerah memproses dan melihat statistik.

```
app/validasi.py     validasi data pengaduan
app/pengaduan.py    penyimpanan + alur status (baru -> diproses -> selesai / ditolak)
app/statistik.py    ringkasan untuk dashboard
app/server.py       API HTTP (python3 -m app.server)
tests/test_*.py     satu file test = satu tugas kecil di compute node
hpc.json            perintah build & test yang dijalankan compute node
```

## Cara kerja relawan

1. Jalankan compute node Anda (`./hpc.sh worker-up` di repo HPC). Selama worker online, sistem
   otomatis memberi Anda jobdesk tertua di antrean (FIFO) beserta branch `task/<id>-<judul>`.
   Lihat di dashboard relawan. Jobdesk tetap milik Anda sampai selesai; bila compute node Anda mati,
   tugas build/test yang sedang berjalan otomatis dikerjakan compute node lain.
2. Terima undangan collaborator dari GitHub (bila admin memakai `PROJECT_GIT_TOKEN`), lalu:
   ```bash
   git clone <url repo ini> && cd <repo>
   git switch task/<id>-<judul>        # atau: git switch -c task/<id>-<judul> origin/main
   code .                              # ngoding di VS Code
   git add -A && git commit -m "..." && git push -u origin task/<id>-<judul>
   ```
3. Setiap push di-build dan dites **terdistribusi** di compute node relawan. Hasilnya muncul di
   dashboard dan sebagai centang/silang pada commit di GitHub.
4. Bila CI lulus, klik **AJUKAN REVIEW**. Sistem membuka Pull Request ke `main`. Admin meninjau
   kodenya lalu menyetujui (PR di-merge sistem, kredit masuk, Anda dapat jobdesk berikutnya)
   atau meminta revisi.

Jalankan test di laptop sendiri sebelum push:
```bash
python3 -m unittest discover -s tests -v
```

## Format hpc.json

```json
{
  "build": "python3 -m compileall -q app",
  "test": {"files": "tests/test_*.py", "command": "python3 -m unittest -v {file}"},
  "before_test": "(opsional) perintah sebelum tiap file test, mis. build ulang"
}
```

- `build` dijalankan sekali (tahap 1). Gagal build = CI gagal, test tidak dijalankan.
- `test.files` adalah pola glob. Setiap file yang cocok menjadi satu tugas di compute node (tahap 2).
- `test.command` dijalankan per file; `{file}` diganti nama file. Kode keluar 0 = lulus.
- Runtime yang tersedia di compute node: Python 3.12 + git. Untuk bahasa lain (mis. Node.js),
  admin menambahkan paketnya di `compute/Dockerfile` repo HPC.
- Test harus deterministik (hasilnya sama di setiap node), karena tiap file dites di 2 node dan
  hasilnya harus sama. Test yang hasilnya acak akan ditandai error.
