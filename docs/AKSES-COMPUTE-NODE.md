# Akses compute node per jobdesk

Compute node untuk relawan-developer disediakan platform: 5 node (layanan `node`, `node2` ...
`node5` di `hpc/head/docker-compose.yml`, port ssh 2222 ... 2226). Satu node dipakai SATU relawan
aktif, dan tiap node punya Docker sendiri untuk testing (perintah `uji`). Relawan login ke node
dari command prompt PC-nya dengan `ssh`, dan di sana hanya bisa bekerja di branch jobdesk-nya sendiri.

## Penempatan dan batas

- Akses jobdesk baru ditempatkan di node ONLINE yang kosong; bila beberapa kosong, node yang
  paling lama tidak diberi akses (bergiliran: node1, node2, ..., node5).
- Tiap node menampung `NODE_MAX_USERS` relawan aktif (bawaan 1, jadi 5 node = 5 relawan sekaligus).
- Semua node penuh: AMBIL JOBDESK ditolak dengan pesan, jobdesk tetap di antrean (FIFO tidak
  berubah). Slot kosong lagi saat jobdesk disetujui, atau saat relawan tidak aktif (lihat bawah).
- Antrean kosong: tombol AMBIL JOBDESK nonaktif. Relawan tanpa jobdesk tidak punya user di node
  mana pun (tidak bisa ssh), tetapi tetap login di website dan tetap bisa menyumbang CPU lewat
  worker repo B. Compute node tetap menyala dan sync tiap 3 detik, tanpa user relawan.

## Alur relawan

1. Login di website (email + password), buka Dashboard, tekan **AMBIL JOBDESK**.
   Sistem memberi jobdesk yang paling lama menunggu di antrean (FIFO, relawan tidak memilih).
2. Kartu jobdesk menampilkan perintah ssh dan **token node**, misalnya:

   ```
   ssh -p 2222 jd12@192.168.1.10
   ```

   Password yang diminta = token node `hpc_ng_xxxx-xxxx-xxxx-xxxx-xxxx` (tombol TAMPILKAN /
   SALIN / GANTI TOKEN). Token yang sama dipakai git di node, jadi relawan hanya memegang satu
   token per jobdesk. `ssh` sudah ada di Command Prompt Windows 10/11, PowerShell, dan
   terminal Linux/macOS.

   ```
   cd ~/hpc-cloudservice-worker
   # ... ngoding ...
   git add -A && git commit -m "pesan" && git push
   jobdesk            # status jobdesk + CI
   jobdesk ajukan     # ajukan review -> sistem membuka Pull Request
   ```

4. Admin menyetujui (PR di-merge) -> dalam beberapa detik sesi SSH diputus, user `jd12` dan
   foldernya dihapus, token node mati. Login website tetap. Relawan mengambil
   jobdesk berikutnya di website dan mendapat akses node baru (`jd13`, kode baru).

## Tidak aktif = node dilepas (jobdesk dan token tetap)

Relawan yang tidak aktif selama `NODE_IDLE_MINUTES` (bawaan 30) melepaskan node-nya untuk relawan
lain. Tidak aktif berarti: tidak ada ketikan maupun keluaran di terminal ssh-nya dan tidak ada
prosesnya yang memakai CPU (keepalive ssh tidak dihitung). Tes panjang yang terus mencetak
keluaran dihitung aktif. Kontainer `uji` di latar belakang tidak dihitung.

1. Agen node mengirim pesan ke terminal relawan, memutus semua sesi ssh-nya, menghapus user
   `jd12` dari node itu dan semua kontainer `uji`-nya.
2. Jobdesk tetap milik relawan, token node TIDAK berubah, folder kerja TETAP ada (termasuk yang
   belum di-push): folder `/home` adalah satu volume yang dipakai bersama kelima node.
3. Kartu jobdesk di website menampilkan **NODE DILEPAS (TIDAK AKTIF)** dan tombol
   **MASUK LAGI KE NODE**. Sistem memberi node yang kosong (node terakhir diutamakan), lalu
   website menampilkan perintah ssh-nya (port bisa berbeda bila node lama sudah dipakai orang lain).
   Login dengan token yang sama.
4. Semua node sedang dipakai: ditolak dengan pesan "Semua compute node sedang dipakai (5/5) ...
   coba lagi beberapa menit lagi".

Admin melihat status ini di tab JOBDESK ("dilepas (tidak aktif sejak ...)") dan di `./hpc.sh nodes`
(PARKIR). Folder rumah baru dihapus saat aksesnya benar-benar dicabut (disetujui / dibatalkan /
kedaluwarsa / dicabut admin).

## Docker untuk testing (`uji`)

Tiap node punya Docker sendiri (layanan `dind1` ... `dind5`, Docker-in-Docker), terpisah dari Docker
host yang menjalankan koordinator dan database. Relawan TIDAK memegang Docker: socket-nya hanya bisa
dibuka root di node. Relawan memakai perintah `uji`, yang dikerjakan layanan uji (root) di node
dengan aturan tetap:

```
uji jalan --nama db --latar -e POSTGRES_PASSWORD=rahasia postgres:16-alpine   # database di latar
uji bangun app                                    # build Dockerfile di folder ini -> lokal/app
uji jalan -e DATABASE_URL=postgresql://postgres:rahasia@db/postgres lokal/app pytest
uji daftar | uji log db | uji masuk db psql -U postgres | uji hapus semua
```

- Kode di folder saat ini DISALIN ke `/work` di kontainer (dibuat sebagai user relawan, jadi hanya
  file yang memang bisa ia baca). Tidak ada mount folder host.
- Kontainer relawan ada di jaringannya sendiri dan saling memanggil lewat nama (`db`, `app`).
  Jaringan Docker uji hanya punya akses internet; koordinator, database platform, dan node lain
  tidak bisa dihubungi.
- Ditolak: `--privileged`, `-v` / mount, `-p` / publish port, `--network host`, `--cap-add`,
  `--user`, image lewat ID, opsi lain di luar daftar `uji`.
- Batas: maks `NODE_TEST_MAX_CONTAINERS` (5) kontainer, RAM `NODE_TEST_CONTAINER_MEMORY` (1g) dan
  `NODE_TEST_CONTAINER_CPUS` (1) per kontainer, 512 proses, `no-new-privileges`; total per node
  `NODE_TEST_MEMORY` (3g) / `NODE_TEST_CPUS` (2).
- Kontainer, jaringan, dan image buatan relawan dihapus saat sesinya di node berakhir.
- Image dari Docker Hub diunduh tanpa login (batas Docker Hub: sekitar 100 unduhan / 6 jam per IP);
  image yang sudah diunduh tetap di cache node.

Pilihan desain dan trade-off:

| Pilihan | Keamanan | Kemudahan | Dipakai? |
|---|---|---|---|
| Socket Docker host dibagikan ke node | relawan = root host | mudah | tidak (berbahaya) |
| Docker-in-Docker, relawan pegang `docker` penuh | relawan bisa `--privileged` -> root host | paling mudah | tidak |
| **Docker-in-Docker per node + perintah `uji` terbatas** | relawan tidak pegang Docker; kontainer tanpa hak istimewa | perintah sendiri, tanpa `docker compose` | **ya** |
| Sysbox (`runtime: sysbox-runc`) menggantikan `privileged` di dind | Docker uji tanpa root host sama sekali | perlu dipasang di host Linux (dukungan di WSL2 / Docker Desktop terbatas) | disarankan untuk server |

Titik lemah yang tersisa: layanan `dindN` berjalan `privileged`. Kontainer relawan sendiri tidak
privileged, jadi untuk keluar ke host dibutuhkan celah kernel / Docker. Di server Linux asli, pasang
Sysbox lalu ganti `privileged: true` dengan `runtime: sysbox-runc` di blok `dind1`.

Jobdesk yang dibatalkan admin juga mencabut aksesnya. Admin bisa mencabut / memberi ulang
akses secara manual (tombol CABUT NODE / BERI AKSES NODE, atau `./hpc.sh node-revoke <id>`).

## Bagaimana branch dibatasi

```
PC relawan --ssh--> node (user jd12) --git--> gerbang git koordinator --token platform--> GitHub repo B
```

- `origin` di node bukan github.com, tetapi `http://coordinator:8000/api/node/git/...`.
  Login git memakai token node jobdesk itu (`hpc_ng_...`, sama dengan password ssh) yang hanya berlaku dari IP compute node
  itu dan mati saat akses dicabut.
- **Push**: gerbang membaca perintah update ref sebelum diteruskan. Hanya
  `refs/heads/<branch jobdesk>` yang diteruskan; push ke `main`, branch lain, atau menghapus
  branch ditolak (`! [remote rejected] ... hanya boleh push ke task/12-...`).
- **Fetch / clone**: gerbang hanya menampilkan branch jobdesk (+ `main` baca saja, bila
  `NODE_READ_MAIN=1`) dan menolak permintaan commit di luar ujung branch itu (HTTP 403).
- `PROJECT_GIT_TOKEN` hanya ada di koordinator, tidak pernah masuk ke node.
- Relawan tidak lagi diundang sebagai collaborator repo B, jadi tidak ada jalan push lain.
  Hapus collaborator lama (yang diundang versi sebelumnya) di GitHub -> Settings -> Collaborators.
- Bila repo B **publik**, isinya tetap bisa dibaca siapa pun dari github.com. Jadikan repo B
  private agar gerbang ini satu-satunya jalan baca.

## Keamanan node

- sshd: hanya grup `relawan`, tanpa root login, tanpa port forwarding / tunnel / agent / X11.
- Folder rumah tiap user `chmod 700`; batas proses dan ukuran file per relawan.
- Node hanya terhubung ke koordinator (jaringan docker `nodes`), tidak ke database.
- Socket Docker uji (`/run/hpc-docker`) dan CLI docker (`/opt/hpc/docker`) hanya bisa dibuka root.
- Kontainer dibatasi CPU/RAM (`NODE_CPUS`, `NODE_MEMORY`) dan capability minimum.

## Failover

Agen node sync ke koordinator tiap 3 detik (pull). Bila node tidak sync lebih dari
`NODE_DEAD_SECONDS` (60), aksesnya dilepas dan diambil node lain yang hidup dan kosong (FIFO).
Folder kerja ada di volume bersama, jadi pekerjaan yang belum di-push ikut pindah.

Catatan: volume `/home` bersama hanya bisa bila kelima node berjalan di mesin yang sama (seperti
sekarang, di laptop head). Bila kelak node dipindah ke PC lain, folder kerja tidak ikut pindah
antar-PC; relawan perlu push sebelum tidak aktif.

## Kredensial

| Kredensial | Dipakai untuk | Umur | Bila bocor |
|---|---|---|---|
| Email + password -> sesi web `hpc_ws_` | website (dashboard, ambil jobdesk) | sesi 7 hari | akun website |
| Token node `hpc_ng_` (satu per jobdesk) | password ssh + git di compute node | sampai disetujui / dibatalkan, maks `NODE_TOKEN_TTL_DAYS` (7 hari); tetap sama saat node dilepas karena tidak aktif | hanya branch jobdesk itu, hanya dari node itu |
| Token worker `hpc_w_` | mesin worker CPU (pengujian), diatur admin | sampai dicabut admin | hanya mengambil tugas komputasi |

- Website hanya menerima email + password. Token worker tidak lagi tampil atau bisa dipakai di
  website; token node juga tidak bisa dipakai login website.
- Akun lama tanpa password / lupa password: di halaman login pilih **Lupa / belum punya
  password?**, kode OTP 6 angka dikirim ke email akun (berlaku 10 menit, maks 5 kali salah).
  Setelah password disimpan semua sesi web lama keluar. Kode tidak pernah dikirim ke browser;
  tanpa layanan email (mode dev) kode hanya tampil di log koordinator.
- Token node tersimpan di node (bisa dibaca relawan), jadi sengaja terpisah dari password web.
  Mencabut akses node saat approve tidak me-logout website.
- Relawan tidak pernah memegang token GitHub; `PROJECT_GIT_TOKEN` milik platform dan hanya ada
  di koordinator.

## Umur token node

Token node berlaku sampai jobdesk disetujui / dibatalkan, paling lama `NODE_TOKEN_TTL_DAYS` hari
(bawaan 7, 0 = tanpa batas). Lewat dari itu akses dicabut seperti saat disetujui (sesi ssh
diputus, user node dihapus), tetapi jobdesk tetap milik relawan dan commit yang sudah di-push
aman di branch-nya. Dashboard relawan menampilkan tanggal kedaluwarsa dan pesan bila sudah lewat.
Admin memilih di tab JOBDESK:

- **BERI AKSES NODE**: token node baru (umur dihitung ulang), relawan melanjutkan.
- **KEMBALIKAN KE ANTREAN**: jobdesk kembali `open` (FIFO); relawan berikutnya mendapat branch
  yang sama dan melanjutkan dari commit terakhir.

**GANTI TOKEN** di dashboard relawan membuat token baru (mis. bila bocor) tanpa memperpanjang umurnya.

## Dari jaringan lain

`./hpc.sh head-online` juga membuka tunnel Cloudflare untuk SSH tiap node (node1 ... node5) dan
menampilkan perintahnya di dashboard relawan. Relawan perlu `cloudflared` sekali
(`winget install Cloudflare.cloudflared`), lalu:

```
ssh -o ProxyCommand="cloudflared access ssh --hostname %h" jd12@xxxx.trycloudflare.com
```

## Konfigurasi (.env head)

| Variabel | Bawaan | Arti |
|---|---|---|
| `PROJECT_GIT_TOKEN` | - | Wajib: token repo B (Contents, Pull requests, Commit statuses R/W) |
| `NODE_ACCESS` | 1 | 0 = alur lama (relawan diundang collaborator) |
| `NODE_TOKEN` | dibuat `head-up` | rahasia koordinator <-> agen node |
| `NODE_SSH_HOST` | localhost | alamat yang ditampilkan ke relawan (isi IP LAN laptop head) |
| `NODE_SSH_PORT`, `NODE2_SSH_PORT` ... `NODE5_SSH_PORT` | 2222 ... 2226 | port ssh node1 ... node5 di laptop head |
| `NODE_MAX_USERS` | 1 | relawan aktif maksimal per node |
| `NODE_IDLE_MINUTES` | 30 | tidak aktif sekian menit = sesi diputus, node dilepas (0 = tidak pernah) |
| `NODE_TEST_CPUS` / `NODE_TEST_MEMORY` | 2 / 3g | batas total Docker uji per node |
| `NODE_TEST_CONTAINER_CPUS` / `NODE_TEST_CONTAINER_MEMORY` | 1 / 1g | batas per kontainer `uji` |
| `NODE_TEST_MAX_CONTAINERS` | 5 | kontainer `uji` maksimal per relawan |
| `NODE_TOKEN_TTL_DAYS` | 7 | umur maksimal token node per jobdesk (0 = tanpa batas) |
| `NODE_CPUS` / `NODE_MEMORY` | 1 / 2g | batas CPU / RAM per node |
| `NODE_READ_MAIN` | 1 | 0 = dari node hanya branch sendiri yang bisa di-fetch |
| `JOBDESK_AUTO_ASSIGN` | 0 | 1 = assign otomatis lama (tanpa tombol) |
