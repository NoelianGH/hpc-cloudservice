import Link from "next/link";
import TerminalCode from "@/components/TerminalCode";

export default function HomePage() {
  return (
    <div className="relative overflow-hidden py-12 lg:py-20 font-sans">
      {/* Glow effect behind hero */}
      <div className="pointer-events-none absolute left-1/2 top-0 -translate-x-1/2 h-[450px] w-[800px] rounded-full bg-cyber-amber-deep/15 blur-[120px]" />

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Hero Section */}
        <div className="text-center">
          <div className="inline-flex items-center space-x-2 rounded-full border border-cyber-amber/40 bg-cyber-surface/90 px-3.5 py-1 text-xs text-cyber-amber-bright shadow-amber-glow-sm">
            <span className="h-2 w-2 rounded-full bg-cyber-amber-bright animate-ping"></span>
            <span className="font-medium tracking-wide">IdleScale • Community-Powered Cloud Supercomputing</span>
          </div>

          <h1 className="mt-7 text-3xl font-extrabold tracking-tight text-white sm:text-5xl lg:text-6xl leading-tight">
            Ubah Komputer Biasa Menjadi <br />
            <span className="bg-gradient-to-r from-amber-300 via-amber-400 to-yellow-500 bg-clip-text text-transparent glow-text-amber">
              Kekuatan Superkomputer Terdistribusi
            </span>
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-sm sm:text-base text-zinc-300 leading-relaxed font-normal">
            Sumbangkan daya komputasi idle CPU laptop Anda untuk menjalankan simulasi ilmiah nyata. 
            Aman dengan isolasi kontainer Docker non-root, perlindungan reputasi GitHub anti-fake, dan konsensus verifikasi hasil multi-node.
          </p>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-4 text-xs font-medium">
            <Link
              href="/register"
              className="flex items-center space-x-2 rounded-md border border-cyber-amber-light bg-cyber-amber px-6 py-3 font-semibold text-cyber-void shadow-amber-glow transition-all hover:bg-cyber-amber-bright hover:scale-105"
            >
              <span>GABUNG JADI RELAWAN</span>
              <span>&rarr;</span>
            </Link>

            <Link
              href="/dashboard"
              className="flex items-center space-x-2 rounded-md border border-cyber-border bg-cyber-surface px-6 py-3 text-zinc-200 transition-all hover:border-cyber-amber hover:text-cyber-amber-bright hover:shadow-amber-glow-sm"
            >
              <span>BUKA COMMAND CENTER</span>
            </Link>
          </div>
        </div>

        {/* 3 Pillars / Feature Grid */}
        <div className="mt-16 grid grid-cols-1 gap-6 sm:grid-cols-3">
          {/* Card 1: Anti-Fake Worker Gate */}
          <div className="cyber-box p-6 transition-all hover:border-cyber-amber/60 hover:shadow-amber-glow-sm rounded-lg">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs font-semibold text-cyber-amber-bright">01 • Keamanan</span>
              <span className="rounded bg-cyber-surface px-2 py-0.5 text-[10px] text-zinc-400 border border-cyber-border font-mono">
                Reputasi GitHub
              </span>
            </div>
            <h3 className="mt-3 text-base font-bold text-gray-100">
              Validasi Anti-Fake Worker
            </h3>
            <p className="mt-2 text-xs text-zinc-400 leading-relaxed font-normal">
              Setiap node relawan dianalisis reputasinya melalui riwayat akun GitHub: umur akun minimal 30 hari, repositori publik, serta verifikasi profil untuk mencegah serangan bot Sybil.
            </p>
            <div className="mt-4 border-t border-cyber-border pt-3">
              <span className="text-[11px] font-medium text-emerald-400 flex items-center space-x-1.5">
                <span>✓</span>
                <span>Dilengkapi Verifikasi Email OTP</span>
              </span>
            </div>
          </div>

          {/* Card 2: Sandboxed Sandbox Compute */}
          <div className="cyber-box p-6 transition-all hover:border-cyber-amber/60 hover:shadow-amber-glow-sm rounded-lg">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs font-semibold text-cyber-amber-bright">02 • Isolasi Sistem</span>
              <span className="rounded bg-cyber-surface px-2 py-0.5 text-[10px] text-zinc-400 border border-cyber-border font-mono">
                Docker Sandbox
              </span>
            </div>
            <h3 className="mt-3 text-base font-bold text-gray-100">
              Sandbox Kontainer Terisolasi
            </h3>
            <p className="mt-2 text-xs text-zinc-400 leading-relaxed font-normal">
              Eksekusi non-root, sistem berkas read-only, pembatasan ketat kuota CPU & RAM, tanpa capability Linux, dan tanpa akses apa pun ke file pribadi di hard drive laptop Anda.
            </p>
            <div className="mt-4 border-t border-cyber-border pt-3">
              <span className="text-[11px] font-medium text-emerald-400 flex items-center space-x-1.5">
                <span>✓</span>
                <span>100% Aman untuk Laptop Pribadi</span>
              </span>
            </div>
          </div>

          {/* Card 3: Replicated Quorum */}
          <div className="cyber-box p-6 transition-all hover:border-cyber-amber/60 hover:shadow-amber-glow-sm rounded-lg">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs font-semibold text-cyber-amber-bright">03 • Konsensus</span>
              <span className="rounded bg-cyber-surface px-2 py-0.5 text-[10px] text-zinc-400 border border-cyber-border font-mono">
                Quorum Validator
              </span>
            </div>
            <h3 className="mt-3 text-base font-bold text-gray-100">
              Validasi Hasil Multi-Node (Quorum)
            </h3>
            <p className="mt-2 text-xs text-zinc-400 leading-relaxed font-normal">
              Tugas dikomputasi silang oleh beberapa relawan independen. Validator membandingkan hash hasil dengan toleransi presisi tinggi untuk memastikan keabsahan data ilmiah.
            </p>
            <div className="mt-4 border-t border-cyber-border pt-3">
              <span className="text-[11px] font-medium text-emerald-400 flex items-center space-x-1.5">
                <span>✓</span>
                <span>Pertahanan Otomatis Anti-Poisoning</span>
              </span>
            </div>
          </div>
        </div>

        {/* Quick Start Terminal Snippet */}
        <div className="mt-16 cyber-box p-6 rounded-lg">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-cyber-border pb-4">
            <div>
              <span className="text-xs font-semibold text-cyber-amber-bright tracking-wider uppercase font-mono">
                Panduan Memulai Cepat
              </span>
              <h2 className="mt-1 text-lg font-bold text-white">
                Jalankan Node Komputasi dalam 3 Langkah
              </h2>
            </div>
            <Link
              href="/register"
              className="mt-3 sm:mt-0 text-xs font-semibold text-cyber-amber-bright hover:underline flex items-center space-x-1"
            >
              <span>Daftar & Dapatkan Token Relawan</span>
              <span>&rarr;</span>
            </Link>
          </div>

          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div>
              <p className="text-xs text-zinc-300 font-medium mb-1">
                1. Clone repositori ke lingkungan WSL2 / Linux Anda:
              </p>
              <TerminalCode
                title="Terminal • Langkah 1: Clone Repositori"
                code={`git clone https://github.com/NoelianGH/hpc-cloudservice.git\ncd hpc-cloudservice\nchmod +x hpc.sh`}
              />

              <p className="mt-5 text-xs text-zinc-300 font-medium mb-1">
                2. Autentikasi node worker via CLI (atau gunakan token dari web):
              </p>
              <TerminalCode
                title="Terminal • Langkah 2: Login Worker"
                code={`./hpc.sh worker-login`}
              />
            </div>

            <div>
              <p className="text-xs text-zinc-300 font-medium mb-1">
                3. Nyalakan worker sandbox dan mulai memproses tugas:
              </p>
              <TerminalCode
                title="Terminal • Langkah 3: Eksekusi Worker"
                code={`# Jalankan 2 worker sandbox terisolasi\n./hpc.sh worker-up 2\n\n# Pantau log eksekusi secara real-time\n./hpc.sh worker-logs`}
              />

              <div className="mt-5 rounded-md border border-cyber-amber/30 bg-cyber-amber-darkest/30 p-3.5 text-xs text-amber-200">
                <span className="font-bold text-cyber-amber-bright">Catatan:</span> Setiap tugas yang berhasil dikerjakan akan memberikan kredit komputasi dan lencana kontributor yang tercatat di dashboard profil Anda.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

