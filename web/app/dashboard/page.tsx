"use client";
import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import TerminalCode from "@/components/TerminalCode";
import JobdeskCard from "./JobdeskCard";

// Data dari koordinator (lewat /api/volunteer/me dan /api/jobs). Tidak ada angka contoh.
type Me = {
  worker: {
    id: string; name: string; github_username: string | null; email: string | null; status: string;
    created_at: string; online: boolean; last_seen: string
  };
  stats: {
    credits: number; rank: number | null; of: number; badge: string | null;
    next_badge: { name: string; credits: number } | null; tasks_validated: number;
    tasks_rejected: number; tasks_expired: number; reject_pct: number; jobs_joined: number;
    compute_seconds: number
  };
  certificate: {
    eligible: boolean; missing: string[]; min_credits: number; max_reject_pct: number;
    progress_pct: number; issued: { code: string; issued_at: string; credits: number } | null
  };
  recent: Array<{
    id: number; task_id: number; job_id: number; kind: string; stage: number; n_stages: number;
    outcome: string; credit: number; seconds: number | null; started_at: string
  }>;
};
type Job = {
  id: number; kind: string; status: string; n_stages: number; current_stage: number; total: number; done: number;
  code: { repo_url: string; sha: string } | null; resources: { cpus: number; memory_mb: number; timeout_s: number };
  result: any; result_branch: string | null; seconds: number | null;
};

const OUTCOME_STYLE: Record<string, string> = {
  tervalidasi: "text-emerald-400",
  ditolak: "text-red-400",
  expired: "text-zinc-500",
  running: "text-cyber-amber-bright",
  "menunggu validasi": "text-zinc-300",
};

function Stat({ label, value, sub, accent }: { label: string; value: React.ReactNode; sub?: string; accent?: string }) {
  return (
    <div className="cyber-box p-4 border-l-2 border-l-cyber-amber">
      <span className="text-[10px] text-zinc-400">{label}</span>
      <div className={`mt-1 text-2xl font-bold tabular-nums ${accent || "text-white"}`}>{value}</div>
      {sub && <p className="mt-1 text-[10px] text-zinc-500">{sub}</p>}
    </div>
  );
}

export default function DashboardPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [certMsg, setCertMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showConsentModal, setShowConsentModal] = useState(false);
  const [consentSubmitting, setConsentSubmitting] = useState(false);

  const load = useCallback(async () => {
    const r = await fetch("/api/volunteer/me", { cache: "no-store" });
    if (r.status === 401 || r.status === 403) {
      window.location.href = "/login";
      return;
    }
    const d = await r.json();
    if (!r.ok) {
      setError(d.detail || "Koordinator tidak dapat dihubungi.");
      return;
    }
    setError(null);
    setMe(d);
    const j = await fetch("/api/jobs", { cache: "no-store" }).then((x) => x.json()).catch(() => ({ jobs: [] }));
    setJobs(j.jobs || []);
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  const handleLogoutClick = () => {
    // Buka floating modal persetujuan apresiasi sebelum logout
    setShowConsentModal(true);
  };

  const handleConfirmLogout = async (giveConsent: boolean) => {
    setConsentSubmitting(true);
    try {
      // 1. Kirim izin consent relawan ke koordinator
      await fetch("/api/volunteer/appreciation-consent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ consent: giveConsent }),
      }).catch(() => undefined);

      // 2. Hapus sesi login worker
      await fetch("/api/volunteer/logout", { method: "POST" }).catch(() => undefined);

      // 3. Jika setuju tampil, arahkan langsung ke halaman appreciation agar melihat profilnya!
      if (giveConsent) {
        window.location.href = "/appreciation";
      } else {
        window.location.href = "/login";
      }
    } catch {
      window.location.href = "/login";
    } finally {
      setConsentSubmitting(false);
    }
  };

  const claimCertificate = async () => {
    setBusy(true);
    setCertMsg(null);
    const r = await fetch("/api/volunteer/certificate", { method: "POST" });
    const d = await r.json().catch(() => ({}));
    setBusy(false);
    if (!r.ok) {
      const det = d.detail;
      setCertMsg(typeof det === "string" ? det : `${det?.message || "Ditolak"} ${(det?.missing || []).join(", ")}`);
      return;
    }
    await load();
  };

  if (error) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 font-mono text-xs">
        <div className="rounded border border-red-500/50 bg-red-950/40 p-4 text-red-300">[ERROR]: {error}</div>
      </div>
    );
  }
  if (!me) {
    return <div className="mx-auto max-w-7xl px-4 py-16 font-mono text-xs text-zinc-400">Memuat data relawan...</div>;
  }

  const s = me.stats;
  const cert = me.certificate;
  const nb = s.next_badge;
  const activeJobs = jobs.filter((j) => j.status === "running");
  const doneJobs = jobs.filter((j) => j.status !== "running").slice(0, 6);

  return (
    <div className="min-h-screen py-8 px-4 sm:px-6 lg:px-8 font-mono">
      <div className="mx-auto max-w-7xl space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between border-b border-cyber-border pb-4 gap-4">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-cyber-amber-bright font-mono">
              Dashboard Relawan {me.worker.online ? "• Worker Online" : "• Worker Offline"}
            </span>
            <h1 className="mt-1 text-2xl font-extrabold text-white sm:text-3xl">{me.worker.name}</h1>
            <p className="mt-1 text-xs text-zinc-400">
              {me.worker.github_username ? `@${me.worker.github_username}` : "tanpa GitHub"} • ID {me.worker.id} •{" "}
              {me.worker.email || "-"}
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs">
            {s.badge && (
              <span className="rounded border border-cyber-amber bg-cyber-amber-darkest/60 px-3 py-1.5 font-bold text-cyber-amber-bright">
                LENCANA {s.badge.toUpperCase()}
              </span>
            )}
            <Link href="/appreciation" className="rounded border border-cyber-border px-3 py-1.5 text-zinc-300 hover:border-cyber-amber hover:text-cyber-amber-bright transition-colors">
              PAPAN APRESIASI
            </Link>
            <button
              onClick={handleLogoutClick}
              className="rounded border border-cyber-border px-3 py-1.5 text-zinc-300 hover:border-red-500 hover:text-red-400 transition-colors"
            >
              KELUAR
            </button>
          </div>
        </div>

        <JobdeskCard />

        {/* Statistik */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Stat label="KREDIT TERVALIDASI" value={s.credits} accent="text-cyber-amber-bright"
            sub={nb ? `${nb.credits - s.credits} lagi menuju lencana ${nb.name}` : "Lencana tertinggi tercapai"} />
          <Stat label="PERINGKAT" value={s.rank ? `#${s.rank}` : "-"} sub={`dari ${s.of} relawan aktif`} />
          <Stat label="TUGAS TERVALIDASI" value={s.tasks_validated}
            sub={`${s.jobs_joined} job • ${Math.round(s.compute_seconds / 60)} menit komputasi`} />
          <Stat label="HASIL DITOLAK" value={`${s.reject_pct}%`} accent={s.tasks_rejected ? "text-red-300" : "text-emerald-400"}
            sub={`${s.tasks_rejected} ditolak • ${s.tasks_expired} lease habis`} />
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Sertifikat */}
          <div className="cyber-box p-6 space-y-3">
            <div className="text-xs font-bold text-cyber-amber-bright uppercase tracking-wider font-mono">Sertifikat Kontributor</div>
            <div className="h-2 w-full rounded bg-cyber-black">
              <div className="h-2 rounded bg-cyber-amber" style={{ width: `${cert.progress_pct}%` }} />
            </div>
            <p className="text-[11px] text-zinc-400">
              Syarat: kredit ≥ {cert.min_credits} dan hasil ditolak ≤ {cert.max_reject_pct}%. Progres {cert.progress_pct}%.
            </p>
            {cert.issued ? (
              <div className="space-y-2 text-xs">
                <p className="text-emerald-400">Sertifikat diterbitkan: {cert.issued.code}</p>
                <div className="flex gap-2">
                  <Link href={`/certificate/${cert.issued.code}`}
                    className="rounded border border-cyber-amber bg-cyber-amber px-3 py-1.5 font-bold text-cyber-void hover:bg-cyber-amber-bright">
                    LIHAT / CETAK
                  </Link>
                  {cert.eligible && (
                    <button onClick={claimCertificate} disabled={busy}
                      className="rounded border border-cyber-border px-3 py-1.5 text-zinc-300 hover:border-cyber-amber disabled:opacity-50">
                      PERBARUI ANGKA
                    </button>
                  )}
                </div>
              </div>
            ) : cert.eligible ? (
              <button onClick={claimCertificate} disabled={busy}
                className="w-full rounded border border-cyber-amber bg-cyber-amber py-2 text-xs font-bold text-cyber-void hover:bg-cyber-amber-bright disabled:opacity-50">
                {busy ? "MENERBITKAN..." : "AMBIL SERTIFIKAT"}
              </button>
            ) : (
              <ul className="list-disc pl-4 text-[11px] text-zinc-500">
                {cert.missing.map((m) => <li key={m}>{m}</li>)}
              </ul>
            )}
            {certMsg && <p className="text-[11px] text-red-300">{certMsg}</p>}
          </div>

          {/* Menjalankan worker */}
          <div className="cyber-box p-6 lg:col-span-2">
            <div className="text-xs font-bold text-cyber-amber-bright uppercase tracking-wider font-mono">Jalankan Worker Anda (Peran Compute Node)</div>
            <p className="mt-1 text-[11px] text-zinc-400">
              Kredit hanya bertambah bila hasil worker Anda sama dengan hasil worker lain (replikasi + quorum).
            </p>
            <TerminalCode
              title="Terminal • Kontrol Worker WSL2"
              code={`./hpc.sh worker-status   # cek token di .env\n./hpc.sh worker-up 1      # jalankan 1 worker sandbox (1 CPU, 512 MB)\n./hpc.sh worker-logs      # pantau tugas yang dikerjakan`}
            />
          </div>
        </div>

        {/* Job berjalan */}
        <div className="cyber-box p-6">
          <div className="text-xs font-bold text-cyber-amber-bright uppercase tracking-wider font-mono">Antrean Tugas Komputasi (FIFO)</div>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[10px] text-zinc-500">
                  <th className="py-1 pr-3">JOB</th><th className="pr-3">JENIS</th><th className="pr-3">TAHAP</th>
                  <th className="pr-3">TUGAS SELESAI</th><th className="pr-3">RESOURCE / TUGAS</th><th>KODE</th>
                </tr>
              </thead>
              <tbody>
                {[...activeJobs, ...doneJobs].map((j) => (
                  <tr key={j.id} className="border-t border-cyber-border/50">
                    <td className="py-1.5 pr-3 font-bold">#{j.id} <span className="text-[10px] text-zinc-500">{j.status}</span></td>
                    <td className="pr-3">{j.kind}</td>
                    <td className="pr-3 tabular-nums">{Math.min(j.current_stage + 1, j.n_stages)}/{j.n_stages}</td>
                    <td className="pr-3 tabular-nums">{j.done}/{j.total}</td>
                    <td className="pr-3 text-zinc-400">{j.resources.cpus} CPU • {j.resources.memory_mb} MB • {j.resources.timeout_s} s</td>
                    <td className="text-zinc-400">
                      {j.code ? `${j.code.repo_url.replace("https://github.com/", "")} @ ${j.code.sha.slice(0, 10)}` : "bawaan worker"}
                      {j.kind === "heat2d" && j.status === "done" && (
                        <a href={`/api/jobs/${j.id}/heatmap`} target="_blank" className="ml-2 text-cyber-amber-bright hover:underline">heatmap</a>
                      )}
                    </td>
                  </tr>
                ))}
                {!jobs.length && <tr><td colSpan={6} className="py-2 text-zinc-500">Belum ada job.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>

        {/* Riwayat tugas */}
        <div className="cyber-box p-6">
          <div className="text-xs font-bold text-cyber-amber-bright uppercase tracking-wider font-mono">Riwayat Tugas Terakhir Anda (25 Tugas)</div>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[10px] text-zinc-500">
                  <th className="py-1 pr-3">TUGAS</th><th className="pr-3">JOB</th><th className="pr-3">TAHAP</th>
                  <th className="pr-3">DURASI</th><th className="pr-3">HASIL</th><th>KREDIT</th>
                </tr>
              </thead>
              <tbody>
                {me.recent.map((a) => (
                  <tr key={a.id} className="border-t border-cyber-border/50">
                    <td className="py-1.5 pr-3">#{a.task_id}</td>
                    <td className="pr-3">#{a.job_id} <span className="text-zinc-500">{a.kind}</span></td>
                    <td className="pr-3 tabular-nums">{a.n_stages > 1 ? `${a.stage + 1}/${a.n_stages}` : "-"}</td>
                    <td className="pr-3 tabular-nums">{a.seconds != null ? `${Number(a.seconds).toFixed(2)} s` : "-"}</td>
                    <td className={`pr-3 ${OUTCOME_STYLE[a.outcome] || ""}`}>{a.outcome}</td>
                    <td className="tabular-nums">{a.outcome === "tervalidasi" ? `+${a.credit}` : "0"}</td>
                  </tr>
                ))}
                {!me.recent.length && (
                  <tr><td colSpan={6} className="py-2 text-zinc-500">Belum ada tugas. Jalankan worker Anda dengan ./hpc.sh worker-up.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* ===================================================================== */}
      {/* FLOATING CONSENT MODAL (SETELAH LOGOUT / SELESAI KERJA)              */}
      {/* ===================================================================== */}
      {showConsentModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
          <div className="relative w-full max-w-lg rounded-xl border border-cyber-amber/80 bg-cyber-void p-6 sm:p-7 shadow-2xl shadow-amber-950/50">
            {/* Header Modal */}
            <div className="flex items-center justify-between border-b border-cyber-border pb-4">
              <div className="flex items-center space-x-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-cyber-amber bg-cyber-surface text-cyber-amber-bright text-base">
                  ⭐
                </div>
                <div>
                  <h3 className="font-bold text-sm text-white">
                    Papan Apresiasi Kontributor
                  </h3>
                  <span className="font-mono text-[10px] text-cyber-amber-bright">
                    APPRECIATION CONSENT CONFIRMATION
                  </span>
                </div>
              </div>

              {/* Close Button */}
              <button
                type="button"
                disabled={consentSubmitting}
                onClick={() => setShowConsentModal(false)}
                className="rounded border border-cyber-border bg-cyber-surface px-2 py-1 text-xs text-zinc-400 hover:border-cyber-amber hover:text-white transition-colors"
              >
                ✕
              </button>
            </div>

            {/* Content Modal */}
            <div className="mt-4 space-y-3 font-sans text-xs">
              <p className="text-zinc-200 leading-relaxed">
                Terima kasih banyak atas kontribusi daya komputasi dari node <strong>{me.worker.name}</strong> untuk simulasi komputasi terbuka IdleScale!
              </p>
              <p className="text-zinc-400 leading-relaxed">
                Sebelum Anda mengakhiri sesi komputasi dan keluar, apakah Anda bersedia dicantumkan di <strong>Papan Apresiasi (Appreciation Board)</strong> publik proyek ini?
              </p>

              {/* Warning Notice Box */}
              <div className="rounded-lg border border-amber-500/40 bg-amber-950/20 p-3.5 text-amber-200 space-y-1.5 font-mono text-[11px]">
                <div className="flex items-center space-x-2 font-bold text-cyber-amber-bright">
                  <span>⚠️</span>
                  <span>PERINGATAN PRIVASI & TAUTAN PROFIL:</span>
                </div>
                <p className="leading-relaxed text-zinc-300 font-sans">
                  Jika Anda memilih <strong>&quot;Tampilkan Profil Saya&quot;</strong>, kartu apresiasi Anda akan memuat foto profil, nama, serta <strong>tombol tautan langsung yang mengarahkan pengunjung ke profil GitHub Anda (github.com/{me.worker.github_username || "username"})</strong>.
                </p>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="mt-6 flex flex-col sm:flex-row gap-3">
              <button
                type="button"
                disabled={consentSubmitting}
                onClick={() => handleConfirmLogout(true)}
                className="flex flex-1 items-center justify-center space-x-2 rounded-lg border border-cyber-amber bg-cyber-amber py-3 font-mono text-xs font-bold text-cyber-void shadow-amber-glow transition-all hover:bg-cyber-amber-bright hover:shadow-amber-glow-lg disabled:opacity-50"
              >
                <span>{consentSubmitting ? "MENYIMPAN..." : "✓ YA, TAMPILKAN DI APRESIASI"}</span>
              </button>

              <button
                type="button"
                disabled={consentSubmitting}
                onClick={() => handleConfirmLogout(false)}
                className="flex items-center justify-center rounded-lg border border-cyber-border bg-cyber-surface px-5 py-3 font-mono text-xs text-zinc-300 hover:border-zinc-500 hover:text-white transition-colors disabled:opacity-50"
              >
                <span>TIDAK, KELUAR SAJA</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
