import Link from "next/link";
import TerminalCode from "@/components/TerminalCode";

export const metadata = { title: "FAQ & Panduan Relawan • IdleScale Cloud" };

const STEPS = [
  {
    t: "Daftar Akun (5 Menit)",
    d: "Isi nama, username GitHub, email, dan password di halaman pendaftaran. Koordinator memeriksa keaslian akun GitHub Anda (umur akun ≥ 30 hari, minimal 2 repo publik) lalu mengirim kode OTP ke email. Setelah OTP terverifikasi, login website cukup dengan email + password.",
  },
  {
    t: "Ambil Jobdesk di Website",
    d: "Di dashboard tekan AMBIL JOBDESK: sistem memberi jobdesk yang paling lama menunggu (FIFO) dan menyiapkan akses di salah satu compute node milik platform. Kartu jobdesk menampilkan perintah ssh dan TOKEN NODE (password ssh) yang hanya berlaku untuk jobdesk itu.",
  },
  {
    t: "Kerjakan di Compute Node",
    d: "Login dari Command Prompt dengan ssh (sudah ada di Windows 10/11). Repo proyek sudah ter-clone di branch jobdesk Anda; hanya branch itu yang bisa di-push, dan setiap push otomatis diuji (CI). Selesai, jalankan 'jobdesk ajukan' untuk membuka Pull Request. Setelah admin menyetujui, token node mati dan Anda bisa mengambil jobdesk berikutnya di website.",
  },
  {
    t: "Kumpulkan Kredit & Lencana",
    d: "Setiap tugas yang hasilnya tervalidasi oleh quorum multi-node memberikan kredit komputasi. Pantau skor, lencana pencapaian, dan peringkat kontributor Anda di Leaderboard.",
  },
  {
    t: "Klaim Sertifikat Resmi",
    d: "Setelah mencapai target kredit minimum, Anda dapat mengklaim Sertifikat Kontributor Resmi dengan kode verifikasi unik publik yang dapat dilampirkan pada CV, profil LinkedIn, maupun portofolio akademik.",
  },
];

const BENEFITS = [
  ["Sertifikat Kontributor Terverifikasi", "Dilengkapi kode unik resmi (IDLESCALE-XXXXXXXXXX) yang dapat diverifikasi keasliannya secara publik."],
  ["Peringkat Leaderboard & Lencana", "Tingkatkan tier kontribusi Anda: Perintis (1), Perunggu (25), Perak (100), hingga Emas (250 kredit)."],
  ["Pengalaman Komputasi Terdistribusi", "Mendalami ekosistem Docker, WSL2, container hardening, dan arsitektur komputasi grid berskala besar."],
  ["Kontrol & Keamanan Total", "Dibatasi ketat 1 CPU dan 512 MB RAM per worker. Tidak ada akses ke dokumen pribadi atau direktori laptop Anda."],
];

const FAQ = [
  ["Apakah laptop saya tetap aman saat worker berjalan?", "Sangat aman. Worker berjalan di dalam kontainer Docker dengan hak akses non-root, read-only rootfs, tanpa capability Linux (cap-drop ALL), tanpa akses folder laptop maupun docker.sock, serta kuota CPU & RAM terkunci rapi."],
  ["Apakah membutuhkan spesifikasi hardware tinggi atau GPU khusus?", "Tidak perlu. Tugas komputasi dirancang dalam bentuk batch Python ringan yang dioptimasi untuk CPU biasa. Laptop mahasiswa dengan RAM tersisa 1 GB sudah sangat cukup."],
  ["Data apa saja yang tersimpan di sistem?", "Hanya nama worker, username GitHub, email (khusus untuk pengiriman OTP rahasia dan tidak pernah dipublikasikan), serta log histori tugas yang telah Anda selesaikan."],
  ["Bagaimana jika laptop saya matikan atau terputus internet?", "Tidak masalah sama sekali. Lease tugas akan kedaluwarsa secara otomatis dalam ~30 detik dan tugas akan dialihkan ke relawan lain di jaringan. Sistem tidak akan mengalami error."],
  ["Bisakah terjadi kecurangan hasil komputasi?", "Setiap tugas dikerjakan secara paralel oleh minimal 2-4 worker berbeda dan hasilnya diverifikasi silang (quorum consensus). Hasil yang dimanipulasi akan langsung didiskualifikasi oleh validator."],
];

export default function JoinPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-12 font-sans sm:px-6 lg:px-8">
      <div className="inline-flex items-center space-x-2 rounded-full border border-cyber-amber/40 bg-cyber-surface px-3 py-1 text-xs text-cyber-amber-bright mb-4">
        <span className="h-1.5 w-1.5 rounded-full bg-cyber-amber-bright"></span>
        <span className="font-mono uppercase tracking-wider">FAQ & Panduan Relawan Komputasi</span>
      </div>

      <h1 className="text-2xl font-extrabold text-white sm:text-4xl tracking-tight">
        Sumbangkan Daya Idle Komputer Anda, Raih Sertifikat Resmi
      </h1>
      <p className="mt-3 max-w-3xl text-sm sm:text-base text-zinc-300 leading-relaxed font-normal">
        Bantu penelitian sains dan simulasi komputasi dengan meminjamkan CPU yang sedang menganggur. 
        Setup mudah dan ringan di Windows (WSL2 + Docker) atau Linux, tanpa perlu keahlian server tingkat tinggi.
      </p>

      <div className="mt-6 flex flex-wrap gap-3 text-xs font-semibold">
        <Link href="/register" className="flex items-center space-x-2 rounded border border-cyber-amber bg-cyber-amber px-5 py-2.5 text-cyber-void shadow-amber-glow transition-all hover:bg-cyber-amber-bright hover:scale-105">
          <span>DAFTAR JADI RELAWAN</span>
          <span>&rarr;</span>
        </Link>
        <Link href="/appreciation" className="rounded border border-cyber-border px-5 py-2.5 text-zinc-300 hover:border-cyber-amber hover:text-cyber-amber-bright transition-colors">
          LIHAT PAPAN APRESIASI
        </Link>
      </div>

      <div className="mt-14">
        <h2 className="text-sm font-bold uppercase tracking-wider text-cyber-amber-bright font-mono">
          Keuntungan Kontributor
        </h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {BENEFITS.map(([t, d]) => (
            <div key={t} className="cyber-box p-5 rounded-lg border border-cyber-border/70 hover:border-cyber-amber/60 transition-all">
              <div className="text-sm font-bold text-white flex items-center space-x-2">
                <span className="text-cyber-amber-bright">●</span>
                <span>{t}</span>
              </div>
              <p className="mt-2 text-xs text-zinc-400 leading-relaxed font-normal">{d}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-14">
        <h2 className="text-sm font-bold uppercase tracking-wider text-cyber-amber-bright font-mono">
          Persyaratan Relawan
        </h2>
        <div className="mt-4 rounded-lg border border-cyber-border bg-cyber-surface/60 p-5">
          <ul className="list-disc space-y-2 pl-5 text-xs text-zinc-300 leading-relaxed">
            <li>Mahasiswa atau umum dengan perangkat PC / Laptop bersistem operasi Windows 10/11 (WSL2) atau Linux.</li>
            <li>Docker Desktop terpasang dengan WSL Integration aktif, dan kapasitas RAM minimum 1 GB saat worker aktif.</li>
            <li>Akun GitHub berumur minimal 30 hari dengan sedikitnya 2 repositori publik (untuk validasi reputasi anti-bot).</li>
            <li>Alamat email aktif untuk menerima kode verifikasi OTP rahasia.</li>
          </ul>
        </div>
      </div>

      <div className="mt-14">
        <h2 className="text-sm font-bold uppercase tracking-wider text-cyber-amber-bright font-mono">
          Tahapan Pendaftaran & Aktivasi Node
        </h2>
        <ol className="mt-4 space-y-3">
          {STEPS.map((s, i) => (
            <li key={s.t} className="cyber-box flex gap-4 p-5 rounded-lg">
              <span className="font-mono text-xl font-bold text-cyber-amber-bright">{String(i + 1).padStart(2, "0")}</span>
              <div>
                <div className="text-sm font-bold text-white">{s.t}</div>
                <p className="mt-1 text-xs text-zinc-400 leading-relaxed font-normal">{s.d}</p>
              </div>
            </li>
          ))}
        </ol>

        <div className="mt-6">
          <TerminalCode
            title="Command Prompt • Setelah AMBIL JOBDESK"
            code={`ssh -p 2222 jd<id>@<alamat compute node>   # password = token node (salin dari dashboard)\ncd ~/hpc-cloudservice-worker\ngit add -A && git commit -m "pesan" && git push\njobdesk            # status jobdesk + CI\njobdesk ajukan     # ajukan review (Pull Request)`}
          />
        </div>
      </div>

      <div className="mt-14">
        <h2 className="text-sm font-bold uppercase tracking-wider text-cyber-amber-bright font-mono">
          Pertanyaan yang Sering Diajukan (FAQ)
        </h2>
        <div className="mt-4 space-y-3">
          {FAQ.map(([q, a]) => (
            <details key={q} className="cyber-box p-5 rounded-lg border border-cyber-border/70">
              <summary className="cursor-pointer text-sm font-bold text-white">{q}</summary>
              <p className="mt-2 text-xs text-zinc-400 leading-relaxed font-normal">{a}</p>
            </details>
          ))}
        </div>
      </div>
    </div>
  );
}
