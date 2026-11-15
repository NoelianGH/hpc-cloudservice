import Link from "next/link";
import TerminalCode from "@/components/TerminalCode";

export const metadata = { title: "Gabung Jadi Relawan // HPC Cloud" };

const STEPS = [
  {
    t: "Daftar (5 menit)",
    d: "Isi nama worker, username GitHub, dan email di halaman Register. Koordinator memeriksa akun GitHub (umur ≥ 30 hari, ≥ 2 repo publik) lalu mengirim kode OTP ke email. Setelah OTP benar, Anda mendapat WORKER_TOKEN pribadi.",
  },
  {
    t: "Siapkan laptop (sekali saja)",
    d: "Windows 10/11 dengan WSL2 (Ubuntu) dan Docker Desktop (WSL Integration aktif). Clone repo proyek ke ~ di WSL, lalu isi WORKER_TOKEN, WORKER_ID, dan COORDINATOR_URL di file .env.",
  },
  {
    t: "Nyalakan worker",
    d: "./hpc.sh worker-up menjalankan 1 kontainer sandbox. Worker menarik tugas kecil (umumnya di bawah 15 detik) dari antrean FIFO, menghitung, dan mengirim hasil. Matikan kapan saja dengan ./hpc.sh worker-down; tugas yang belum selesai otomatis dialihkan ke relawan lain.",
  },
  {
    t: "Kumpulkan kredit",
    d: "Setiap tugas yang hasilnya sama dengan worker lain (quorum) memberi kredit. Pantau kredit, peringkat, dan riwayat tugas di Dashboard Relawan dan Leaderboard.",
  },
  {
    t: "Ambil sertifikat",
    d: "Setelah syarat kredit terpenuhi, klik Ambil Sertifikat di dashboard. Sertifikat punya kode unik yang bisa diverifikasi siapa pun, cocok untuk CV, portofolio, atau LinkedIn.",
  },
];

const BENEFITS = [
  ["Sertifikat kontributor terverifikasi", "Kode unik HPC-XXXXXXXXXX, bisa dicek keasliannya secara publik di /certificate/<kode>."],
  ["Kredit, lencana, dan leaderboard", "Perintis (1), Perunggu (25), Perak (100), Emas (250 kredit). Peringkat tampil di Leaderboard."],
  ["Pengalaman praktis", "Docker, WSL2, sistem terdistribusi, dan komputasi paralel nyata, dengan log yang bisa Anda baca sendiri."],
  ["Kontrol penuh atas laptop", "Batas 1 CPU dan 512 MB RAM per worker; nyala/mati kapan saja; tidak ada akses ke file laptop Anda."],
];

const FAQ = [
  ["Apakah laptop saya aman?", "Worker berjalan di kontainer non-root, read-only, tanpa capability Linux, tanpa akses folder laptop maupun docker.sock, dibatasi CPU/RAM/jumlah proses. Kode tugas hanya diambil dari repo job pada commit SHA tertentu yang bisa Anda baca sendiri di GitHub."],
  ["Apakah butuh Jupyter atau MPI?", "Tidak. Semua tugas adalah program Python kecil di dalam kontainer; komunikasi antar-tahap lewat koordinator (HTTP), jadi ringan untuk laptop mahasiswa."],
  ["Data apa yang disimpan?", "Nama worker, username GitHub, email (hanya untuk OTP, tidak pernah tampil publik), serta catatan tugas yang Anda kerjakan."],
  ["Bagaimana jika saya mematikan laptop di tengah tugas?", "Tidak masalah. Lease tugas habis dalam ~30 detik dan tugas dikembalikan ke antrean untuk relawan lain. Hanya kredit tugas itu yang tidak Anda dapat."],
  ["Bisakah curang untuk menambah kredit?", "Setiap tugas dikerjakan minimal 2 worker berbeda dan hash hasilnya dibandingkan. Hasil yang berbeda ditolak, tidak memberi kredit, dan admin dapat menangguhkan worker."],
];

export default function JoinPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 font-mono sm:px-6 lg:px-8">
      <span className="text-xs font-bold uppercase tracking-widest text-cyber-amber-bright">// REKRUTMEN RELAWAN</span>
      <h1 className="mt-1 text-2xl font-extrabold text-white sm:text-4xl">PINJAMKAN CPU LAPTOPMU, DAPATKAN SERTIFIKAT</h1>
      <p className="mt-3 max-w-3xl text-sm text-zinc-400">
        Kami mencari mahasiswa yang mau menyumbangkan sebagian daya komputasi laptopnya untuk menjalankan tugas-tugas
        komputasi kecil (simulasi panas 2D, Monte Carlo, dan lainnya). Tidak perlu keahlian HPC; cukup laptop dengan
        WSL2 + Docker dan akun GitHub.
      </p>
      <div className="mt-6 flex flex-wrap gap-3 text-xs">
        <Link href="/register" className="rounded border border-cyber-amber bg-cyber-amber px-4 py-2.5 font-bold text-cyber-void shadow-amber-glow hover:bg-cyber-amber-bright">
          DAFTAR SEKARANG &rarr;
        </Link>
        <Link href="/leaderboard" className="rounded border border-cyber-border px-4 py-2.5 text-zinc-300 hover:border-cyber-amber">
          LIHAT LEADERBOARD
        </Link>
      </div>

      <h2 className="mt-12 text-sm font-bold text-cyber-amber-bright">// YANG KAMU DAPAT</h2>
      <div className="mt-3 grid gap-4 md:grid-cols-2">
        {BENEFITS.map(([t, d]) => (
          <div key={t} className="cyber-box p-4">
            <div className="text-sm font-bold text-white">{t}</div>
            <p className="mt-1 text-xs text-zinc-400">{d}</p>
          </div>
        ))}
      </div>

      <h2 className="mt-12 text-sm font-bold text-cyber-amber-bright">// SYARAT</h2>
      <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-zinc-300">
        <li>Mahasiswa aktif (prioritas mahasiswa Informatika / Ilmu Komputer), laptop Windows 10/11 atau Linux.</li>
        <li>WSL2 Ubuntu + Docker Desktop, sisa RAM minimal 1 GB saat worker berjalan.</li>
        <li>Akun GitHub berumur ≥ 30 hari dengan ≥ 2 repositori publik (mencegah akun palsu).</li>
        <li>Email aktif untuk menerima kode OTP.</li>
      </ul>

      <h2 className="mt-12 text-sm font-bold text-cyber-amber-bright">// LANGKAH BERGABUNG</h2>
      <ol className="mt-3 space-y-3">
        {STEPS.map((s, i) => (
          <li key={s.t} className="cyber-box flex gap-4 p-4">
            <span className="text-xl font-bold text-cyber-amber-bright">{String(i + 1).padStart(2, "0")}</span>
            <div>
              <div className="text-sm font-bold text-white">{s.t}</div>
              <p className="mt-1 text-xs text-zinc-400">{s.d}</p>
            </div>
          </li>
        ))}
      </ol>
      <TerminalCode
        title="COMPUTE NODE // WSL2 BASH"
        code={`git clone https://github.com/NoelianGH/hpc-cloudservice.git ~/hpc-cloudservice\ncd ~/hpc-cloudservice && chmod +x hpc.sh\n./hpc.sh worker-login     # atau daftar di web, lalu isi WORKER_TOKEN & WORKER_ID di .env\n# isi COORDINATOR_URL di .env dengan alamat dari panitia\n./hpc.sh worker-up 1\n./hpc.sh worker-logs`}
      />

      <h2 className="mt-12 text-sm font-bold text-cyber-amber-bright">// PERTANYAAN UMUM</h2>
      <div className="mt-3 space-y-3">
        {FAQ.map(([q, a]) => (
          <details key={q} className="cyber-box p-4">
            <summary className="cursor-pointer text-sm font-bold text-white">{q}</summary>
            <p className="mt-2 text-xs text-zinc-400">{a}</p>
          </details>
        ))}
      </div>
    </div>
  );
}
