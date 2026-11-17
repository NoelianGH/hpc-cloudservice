# Template repo job

Salin isi folder ini ke repo GitHub baru (mis. `hpc-jobs`), commit, lalu pakai SHA commit itu:

```bash
git rev-parse HEAD                                   # SHA 40 karakter
./hpc.sh job-repo <sha> prime_count 10 https://github.com/ORG/hpc-jobs
```

Atau isi `JOB_REPO_URL` di `.env` head node agar `repo_url` tidak perlu ditulis.

Kontrak: stdin `{"kind": ..., "payload": {...}}`, baris terakhir stdout = satu objek JSON hasil. Hasil harus deterministik karena dibandingkan antar-replika dengan hash. Hanya pustaka standar Python (image worker: `python:3.12-slim` + git).

Jenis tugas contoh di `run.py`: `prime_count` (job `repo`), `montecarlo_pi`, `heat2d` (kernel sama dengan worker bawaan).
