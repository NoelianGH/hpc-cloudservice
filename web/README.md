# HPC Cloud Service — Web Portal (Next.js)

Portal antarmuka web futuristik untuk platform **HPC Cloud Service** (Distributed Volunteer Computing). Menggunakan tema **Cyberpunk Dark** dengan aksen **Kuning Gelap (Dark Amber / Gold)** dan **Hitam (Obsidian / Carbon)**.

---

## Fitur Utama

1. **Registrasi Worker Node (`/register`)**:
   - Input data lengkap: Nama Depan, Nama Belakang, Username, Email, Password, Username GitHub, dan Nama Worker Node.
   - **Verifikasi Otomatis Anti-Fake Worker**:
     - Sistem menganalisis akun GitHub (usia akun minimal 30 hari, repositori publik minimal 2, followers, dan kelengkapan profil).
     - Menolak bot dan throwaway account palsu.
   - **Pengiriman Kode OTP ke Email**:
     - Kode keamanan 6 digit dikirimkan ke email user (atau dicatat ke console log jika mode simulasi dev aktif).
   - **Verifikasi OTP & Penerbitan Token**:
     - Setelah OTP valid, sistem menerbitkan `WORKER_TOKEN` unik dan `WORKER_ID`.
     - Menyediakan instruksi copy-paste perintah Bash untuk langsung menjalankan `./hpc.sh worker-up` di terminal.

2. **Login Portal (`/login`)**:
   - Mendukung login dengan kredensial akun atau langsung menggunakan `WORKER_TOKEN`.

3. **Command Center Dashboard (`/dashboard`)**:
   - Status live cluster telemetry (Online/Standby, Quorum consensus, Active tasks).
   - Kartu identitas worker yang terverifikasi beserta peek/hide token.
   - Kartu metrik: Tasks executed, volunteer credits, lease heartbeat status.
   - Monitoring antrean tugas (Monte Carlo Pi, Mandelbrot, dsb) beserta status konsensus.
   - Terminal runner snippet untuk menjalankan worker kontainer via Docker.

---

## Cara Menjalankan Website

### Opsi 1: Menjalankan Langsung dengan Node.js (Rekomendasi)

Masuk ke folder `web`:
```bash
cd web
npm install
npm run dev
```

Buka browser di:
```
http://localhost:3000
```

---

### Opsi 2: Menjalankan dengan Docker

Jika ingin menjalankan website sebagai kontainer Docker:
```bash
cd web
docker build -t hpc-web .
docker run -p 3000:3000 -e COORDINATOR_URL=http://host.docker.internal:8000 hpc-web
```

---

## Struktur Folder `web/`

```
web/
├── app/
│   ├── api/
│   │   ├── auth/
│   │   │   ├── register-request/route.ts  # Endpoint cek GitHub & kirim OTP
│   │   │   ├── verify-otp/route.ts        # Endpoint verifikasi kode OTP
│   │   │   └── resend-otp/route.ts        # Endpoint kirim ulang OTP
│   │   └── stats/route.ts                 # Telemetry cluster koordinator
│   ├── dashboard/
│   │   └── page.tsx                       # Halaman Command Center Dashboard
│   ├── login/
│   │   └── page.tsx                       # Halaman Login
│   ├── register/
│   │   └── page.tsx                       # Halaman Registrasi, Cek GitHub & OTP
│   ├── globals.css                        # Cyberpunk scanlines, grid & glow
│   ├── layout.tsx                         # Root layout dengan Navbar & Footer
│   └── page.tsx                           # Landing page futuristik
├── components/
│   ├── CyberNavbar.tsx                    # Header navigasi & status cluster
│   ├── CyberFooter.tsx                    # Footer telemetry & links
│   └── TerminalCode.tsx                   # Blok kode terminal cyberpunk
├── lib/
│   ├── coordinator.ts                     # Integrasi ke backend FastAPI Coordinator
│   └── types.ts                           # Interface TypeScript
├── package.json
├── tailwind.config.ts                     # Konfigurasi warna Kuning Gelap & Hitam
├── tsconfig.json
└── Dockerfile
```

