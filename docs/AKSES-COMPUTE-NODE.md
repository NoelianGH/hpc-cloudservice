# Akses compute node per jobdesk

Compute node untuk relawan-developer disediakan platform (layanan `node` = node1 di port 2222
dan `node2` di port 2223, di `hpc/head/docker-compose.yml`). Relawan login ke node dari command
prompt PC-nya dengan `ssh`, dan di sana hanya bisa bekerja di branch jobdesk-nya sendiri.

## Penempatan dan batas

- Akses jobdesk baru ditempatkan di node ONLINE yang paling sedikit penghuninya; bila sama,
  node yang paling lama tidak diberi akses (bergiliran: node1, node2, node1, ...).
- Tiap node menampung paling banyak `NODE_MAX_USERS` relawan aktif (bawaan 3, jadi 2 node = 6).
- Semua node penuh: AMBIL JOBDESK ditolak dengan pesan, jobdesk tetap di antrean (FIFO tidak
  berubah). Begitu ada jobdesk yang disetujui, slotnya kosong lagi.
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
- Kontainer dibatasi CPU/RAM (`NODE_CPUS`, `NODE_MEMORY`) dan capability minimum.

## Failover

Agen node sync ke koordinator tiap 3 detik (pull). Bila node tidak sync lebih dari
`NODE_DEAD_SECONDS` (60), aksesnya dilepas dan diambil node lain yang hidup (FIFO), yang
meng-clone ulang branch dari GitHub. Kode yang sudah di-push tidak hilang.

## Kredensial

| Kredensial | Dipakai untuk | Umur | Bila bocor |
|---|---|---|---|
| Email + password -> sesi web `hpc_ws_` | website (dashboard, ambil jobdesk) | sesi 7 hari | akun website |
| Token node `hpc_ng_` (satu per jobdesk) | password ssh + git di compute node | sampai disetujui / dibatalkan, maks `NODE_TOKEN_TTL_DAYS` (7 hari) | hanya branch jobdesk itu, hanya dari node itu |
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

`./hpc.sh head-online` juga membuka tunnel Cloudflare untuk SSH tiap node (node1, node2) dan
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
| `NODE_SSH_PORT` / `NODE2_SSH_PORT` | 2222 / 2223 | port ssh node1 / node2 di laptop head |
| `NODE_MAX_USERS` | 3 | relawan aktif maksimal per node |
| `NODE_TOKEN_TTL_DAYS` | 7 | umur maksimal token node per jobdesk (0 = tanpa batas) |
| `NODE_CPUS` / `NODE_MEMORY` | 1 / 2g | batas CPU / RAM per node |
| `NODE_READ_MAIN` | 1 | 0 = dari node hanya branch sendiri yang bisa di-fetch |
| `JOBDESK_AUTO_ASSIGN` | 0 | 1 = assign otomatis lama (tanpa tombol) |
