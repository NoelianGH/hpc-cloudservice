"use client";
import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import JobdeskCard from "./JobdeskCard";

// Data dari koordinator (lewat /api/volunteer/me dan /api/jobs).
type Me = {
  worker: {
    id: string;
    name: string;
    worker_name?: string;
    worker_node_name?: string;
    first_name?: string;
    last_name?: string;
    username?: string;
    github_username: string | null;
    email: string | null;
    status: string;
    created_at: string;
    online: boolean;
    last_seen: string;
    has_password?: boolean;
    has_consented?: boolean;
    show_in_appreciation?: boolean;
  };
  stats: {
    credits: number;
    rank: number | null;
    of: number;
    badge: string | null;
    next_badge: { name: string; credits: number } | null;
    tasks_validated: number;
    tasks_rejected: number;
    tasks_expired: number;
    reject_pct: number;
    jobs_joined: number;
    compute_seconds: number;
    jobdesks_done?: number;
    jobdesks_active?: number;
    reviews_approved?: number;
    reviews_revised?: number;
    accept_pct?: number | null;
  };
  certificate: {
    eligible: boolean;
    missing: string[];
    min_credits: number;
    min_accept_pct: number;
    progress_pct: number;
    issued: { code: string; issued_at: string; credits: number } | null;
  };
  recent: Array<{
    id: number;
    task_id: number;
    job_id: number;
    kind: string;
    stage: number;
    n_stages: number;
    outcome: string;
    credit: number;
    seconds: number | null;
    started_at: string;
  }>;
};

type Job = {
  id: number;
  kind: string;
  status: string;
  n_stages: number;
  current_stage: number;
  total: number;
  done: number;
  code: { repo_url: string; sha: string } | null;
  resources: { cpus: number; memory_mb: number; timeout_s: number };
  result: any;
  result_branch: string | null;
  seconds: number | null;
};

const OUTCOME_STYLE: Record<string, string> = {
  tervalidasi: "text-emerald-400",
  ditolak: "text-red-400",
  expired: "text-zinc-500",
  running: "text-cyber-amber-bright",
  "menunggu validasi": "text-zinc-300",
};

function Stat({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  accent?: string;
}) {
  return (
    <div className="cyber-box p-4 border-l-2 border-l-cyber-amber">
      <span className="text-[10px] text-zinc-400 font-mono">{label}</span>
      <div className={`mt-1 text-2xl font-bold tabular-nums ${accent || "text-white"}`}>{value}</div>
      {sub && <p className="mt-1 text-[10px] text-zinc-500 font-mono">{sub}</p>}
    </div>
  );
}

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<"dashboard" | "progress" | "profile">("dashboard");
  const [me, setMe] = useState<Me | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [certMsg, setCertMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showConsentModal, setShowConsentModal] = useState(false);
  const [consentSubmitting, setConsentSubmitting] = useState(false);
  const [toast, setToast] = useState<{ msg: string; tone: "ok" | "err" } | null>(null);

  // Form State untuk Edit Profil
  const [profileFirstName, setProfileFirstName] = useState("");
  const [profileLastName, setProfileLastName] = useState("");
  const [profileUsername, setProfileUsername] = useState("");
  const [profileWorkerNodeName, setProfileWorkerNodeName] = useState("");
  const [profileEmail, setProfileEmail] = useState("");
  const [profileGithub, setProfileGithub] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);
  const [showInAppreciation, setShowInAppreciation] = useState(false);
  const [togglingConsent, setTogglingConsent] = useState(false);

  // State untuk Floating Menu Ubah Kata Sandi
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [showCurrentPw, setShowCurrentPw] = useState(false);
  const [showNewPw, setShowNewPw] = useState(false);
  const [showConfirmPw, setShowConfirmPw] = useState(false);
  const [pwSubmitting, setPwSubmitting] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);

  const notify = useCallback((msg: string, tone: "ok" | "err" = "ok") => {
    setToast({ msg, tone });
    window.setTimeout(() => setToast((t) => (t?.msg === msg ? null : t)), 5000);
  }, []);

  const profileInitialized = useRef(false);

  const load = useCallback(async (forceProfile = false) => {
    const r = await fetch("/api/volunteer/me", { cache: "no-store" });
    if (r.status === 401 || r.status === 403) {
      window.location.href = "/login?expired=1";
      return;
    }
    const d = await r.json();
    if (!r.ok) {
      setError(d.detail || "Koordinator tidak dapat dihubungi.");
      return;
    }
    setError(null);
    setMe(d);

    // Inisialisasi input profil hanya saat pertama kali dimuat atau setelah berhasil disimpan.
    // Ini mencegah ketikan pengguna di form profil tertimpa oleh polling interval 5 detik.
    if (!profileInitialized.current || forceProfile) {
      profileInitialized.current = true;
      setProfileFirstName(d.worker.first_name || "");
      setProfileLastName(d.worker.last_name || "");
      setProfileUsername(d.worker.username || "");
      setProfileWorkerNodeName(d.worker.worker_node_name || d.worker.name || "");
      setProfileEmail(d.worker.email || "");
      setProfileGithub(d.worker.github_username || "");
      setShowInAppreciation(Boolean(d.worker.show_in_appreciation));
    }

    const j = await fetch("/api/jobs", { cache: "no-store" })
      .then((x) => x.json())
      .catch(() => ({ jobs: [] }));
    setJobs(j.jobs || []);
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(() => load(false), 5000);
    return () => clearInterval(t);
  }, [load]);

  const handleLogoutClick = async () => {
    // Peringatan modal consent HANYA muncul pada saat PERTAMA KALI logout (belum pernah memberikan pilihan)
    if (!me?.worker.has_consented) {
      setShowConsentModal(true);
      return;
    }

    // Jika sudah pernah memilih, langsung logout tanpa popup
    try {
      await fetch("/api/volunteer/logout", { method: "POST" }).catch(() => undefined);
    } finally {
      window.location.href = "/login";
    }
  };

  const handleToggleAppreciation = async () => {
    const nextVal = !showInAppreciation;
    setTogglingConsent(true);
    try {
      const res = await fetch("/api/volunteer/appreciation-consent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ consent: nextVal }),
      });
      if (res.ok) {
        setShowInAppreciation(nextVal);
        if (me) {
          setMe({
            ...me,
            worker: {
              ...me.worker,
              show_in_appreciation: nextVal,
              has_consented: true,
            },
          });
        }
        notify(
          nextVal
            ? "Profil Anda sekarang DITAMPILKAN di Contributor Appreciation Board!"
            : "Profil Anda sekarang DISEMBUNYIKAN dari Contributor Appreciation Board.",
          "ok"
        );
      } else {
        notify("Gagal memperbarui izin apresiasi.", "err");
      }
    } catch (err: any) {
      notify("Terjadi kesalahan: " + err.message, "err");
    } finally {
      setTogglingConsent(false);
    }
  };

  const handleConfirmLogout = async (giveConsent: boolean) => {
    setConsentSubmitting(true);
    try {
      await fetch("/api/volunteer/appreciation-consent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ consent: giveConsent }),
      }).catch(() => undefined);

      await fetch("/api/volunteer/logout", { method: "POST" }).catch(() => undefined);

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
    notify("Sertifikat kontributor berhasil diterbitkan!");
    await load();
  };

  // Simpan perubahan profil
  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profileFirstName.trim()) {
      notify("First Name wajib diisi.", "err");
      return;
    }
    setSavingProfile(true);
    const fullName = `${profileFirstName.trim()} ${profileLastName.trim()}`.trim();
    try {
      const res = await fetch("/api/volunteer/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: profileWorkerNodeName.trim() || fullName,
          worker_name: profileWorkerNodeName.trim(),
          first_name: profileFirstName.trim(),
          last_name: profileLastName.trim(),
          username: profileUsername.trim(),
          email: profileEmail.trim(),
          github_username: profileGithub.trim().replace(/^@/, ""),
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        notify(data.detail || "Gagal memperbarui profil.", "err");
        return;
      }
      notify("Profil berhasil disimpan!", "ok");
      await load(true);
    } catch (err: any) {
      notify("Terjadi kesalahan: " + err.message, "err");
    } finally {
      setSavingProfile(false);
    }
  };

  // Simpan kata sandi baru
  const handleSavePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwError(null);
    if (newPw.length < 8) {
      setPwError("Password baru minimal 8 karakter.");
      return;
    }
    if (newPw !== confirmPw) {
      setPwError("Konfirmasi password baru tidak cocok.");
      return;
    }
    setPwSubmitting(true);
    try {
      const res = await fetch("/api/volunteer/password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          password: newPw,
          current_password: currentPw || null,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setPwError(data.detail || "Gagal mengubah kata sandi.");
        return;
      }
      notify("Kata sandi berhasil diubah! Gunakan password baru saat login berikutnya.", "ok");
      setShowPasswordModal(false);
      setCurrentPw("");
      setNewPw("");
      setConfirmPw("");
      await load();
    } catch (err: any) {
      setPwError("Terjadi kesalahan: " + err.message);
    } finally {
      setPwSubmitting(false);
    }
  };

  if (error) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 font-mono text-xs">
        <div className="rounded border border-red-500/50 bg-red-950/40 p-4 text-red-300">[ERROR]: {error}</div>
      </div>
    );
  }
  if (!me) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-20 font-mono text-xs text-center text-zinc-400">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-cyber-amber border-t-transparent mb-3" />
        <p>Memuat Command Center &amp; Data Relawan...</p>
      </div>
    );
  }

  const s = me.stats;
  const cert = me.certificate;
  const nb = s.next_badge;
  const activeJobs = jobs.filter((j) => j.status === "running");
  const doneJobs = jobs.filter((j) => j.status !== "running").slice(0, 8);
  const volunteerDisplayName =
    [me.worker.first_name, me.worker.last_name].filter(Boolean).join(" ") ||
    me.worker.username ||
    me.worker.name;

  return (
    <div className="min-h-screen py-6 px-4 sm:px-6 lg:px-8 font-sans">
      {/* Toast Alert Popup */}
      {toast && (
        <div
          className={`fixed bottom-6 right-6 z-50 flex items-center space-x-2 rounded-lg border px-4 py-3 font-mono text-xs shadow-xl backdrop-blur-md transition-all ${
            toast.tone === "err"
              ? "border-red-500/80 bg-red-950/90 text-red-200"
              : "border-cyber-amber/80 bg-cyber-void/95 text-cyber-amber-bright"
          }`}
        >
          <span>{toast.tone === "err" ? "⚠️" : "✓"}</span>
          <span>{toast.msg}</span>
        </div>
      )}

      <div className="mx-auto max-w-7xl">
        <div className="flex flex-col lg:flex-row gap-6">

          {/* ================================================================= */}
          {/* SIDEBAR DASHBOARD                                                */}
          {/* ================================================================= */}
          <aside className="w-full lg:w-72 flex-shrink-0 flex flex-col justify-between cyber-box p-5 rounded-xl border border-cyber-border/80 bg-cyber-void/90 backdrop-blur-sm self-start lg:sticky lg:top-20">
            <div>
              {/* Volunteer Identity Profile Box */}
              <div className="flex items-center space-x-3 pb-5 border-b border-cyber-border/70">
                <div className="relative">
                  <img
                    src={
                      me.worker.github_username
                        ? `https://github.com/${me.worker.github_username}.png`
                        : `https://ui-avatars.com/api/?name=${encodeURIComponent(volunteerDisplayName)}&background=18181b&color=f59e0b`
                    }
                    alt={volunteerDisplayName}
                    className="h-12 w-12 rounded-full border-2 border-cyber-amber/60 object-cover"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src = `https://ui-avatars.com/api/?name=${encodeURIComponent(
                        volunteerDisplayName
                      )}&background=18181b&color=f59e0b`;
                    }}
                  />
                  <span
                    className={`absolute bottom-0 right-0 h-3 w-3 rounded-full border-2 border-cyber-void ${
                      me.worker.online ? "bg-emerald-400" : "bg-zinc-500"
                    }`}
                    title={me.worker.online ? "Worker Online" : "Worker Offline"}
                  />
                </div>
                <div className="overflow-hidden">
                  <h2 className="font-bold text-sm text-white truncate">{volunteerDisplayName}</h2>
                  <p className="font-mono text-xs text-cyber-amber-bright truncate">
                    {me.worker.github_username ? `@${me.worker.github_username}` : "Tanpa GitHub"}
                  </p>
                  <div className="mt-1 flex items-center space-x-1.5">
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${
                        me.worker.online ? "bg-emerald-400 animate-ping" : "bg-zinc-500"
                      }`}
                    />
                    <span className="font-mono text-[10px] text-zinc-400 uppercase">
                      {me.worker.online ? "Online" : "Offline"}
                    </span>
                    {s.badge && (
                      <span className="rounded bg-cyber-amber-darkest/90 border border-cyber-amber/50 px-1.5 py-0.2 font-mono text-[9px] font-bold text-cyber-amber-bright">
                        {s.badge}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Sidebar Navigation Tabs */}
              <nav className="mt-5 space-y-1.5">
                <button
                  type="button"
                  onClick={() => setActiveTab("dashboard")}
                  className={`w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-lg text-xs font-semibold font-mono tracking-wider transition-all text-left ${
                    activeTab === "dashboard"
                      ? "border border-cyber-amber bg-cyber-amber/15 text-cyber-amber-bright shadow-amber-glow-sm"
                      : "border border-transparent text-zinc-300 hover:bg-cyber-surface hover:text-white"
                  }`}
                >
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                  </svg>
                  <span>DASHBOARD</span>
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab("progress")}
                  className={`w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-lg text-xs font-semibold font-mono tracking-wider transition-all text-left ${
                    activeTab === "progress"
                      ? "border border-cyber-amber bg-cyber-amber/15 text-cyber-amber-bright shadow-amber-glow-sm"
                      : "border border-transparent text-zinc-300 hover:bg-cyber-surface hover:text-white"
                  }`}
                >
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  <span>PROGRESS &amp; WORK LIST</span>
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab("profile")}
                  className={`w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-lg text-xs font-semibold font-mono tracking-wider transition-all text-left ${
                    activeTab === "profile"
                      ? "border border-cyber-amber bg-cyber-amber/15 text-cyber-amber-bright shadow-amber-glow-sm"
                      : "border border-transparent text-zinc-300 hover:bg-cyber-surface hover:text-white"
                  }`}
                >
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                  <span>PROFIL SAYA</span>
                </button>
              </nav>
            </div>

            {/* Bottom of Sidebar: TOMBOL KELUAR */}
            <div className="mt-8 pt-5 border-t border-cyber-border/70">
              <button
                type="button"
                onClick={handleLogoutClick}
                className="w-full flex items-center justify-center space-x-2 rounded-lg border border-red-500/40 bg-red-950/20 py-2.5 font-mono text-xs font-semibold text-red-300 hover:border-red-500 hover:bg-red-950/50 hover:text-red-200 transition-all"
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                <span>KELUAR</span>
              </button>
            </div>
          </aside>

          {/* ================================================================= */}
          {/* MAIN CONTENT AREA                                                 */}
          {/* ================================================================= */}
          <main className="flex-1 space-y-6 min-w-0">

            {/* TAB 1: DASHBOARD UTAMA */}
            {activeTab === "dashboard" && (
              <div className="space-y-6">
                {/* Header Welcome Bar */}
                <div className="cyber-box p-6 rounded-xl border border-cyber-border">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                    <div>
                      <span className="font-mono text-xs font-bold uppercase tracking-wider text-cyber-amber-bright">
                        Command Center Relawan • IdleScale Cloud
                      </span>
                      <h1 className="mt-1 text-2xl font-extrabold text-white sm:text-3xl">
                        Selamat Datang, {volunteerDisplayName}
                      </h1>
                      <p className="mt-1 text-xs text-zinc-400 font-mono">
                        ID: {me.worker.id} &bull; Bergabung: {new Date(me.worker.created_at).toLocaleDateString("id-ID")}
                      </p>
                    </div>
                    {s.badge && (
                      <div className="inline-flex items-center space-x-1.5 self-start sm:self-auto rounded-lg border border-cyber-amber bg-cyber-amber-darkest/70 px-3 py-1.5 font-mono text-xs font-bold text-cyber-amber-bright">
                        <span>⭐</span>
                        <span>LENCANA {s.badge.toUpperCase()}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* 4 Stat Cards */}
                <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                  <Stat
                    label="KREDIT TERVALIDASI"
                    value={s.credits}
                    accent="text-cyber-amber-bright"
                    sub={nb ? `${nb.credits - s.credits} kredit lagi menuju ${nb.name}` : "Lencana tertinggi tercapai"}
                  />
                  <Stat
                    label="PERINGKAT LEADERBOARD"
                    value={s.rank ? `#${s.rank}` : "-"}
                    sub={`dari ${s.of} relawan aktif`}
                  />
                  <Stat
                    label="TUGAS SELESAI"
                    value={s.jobdesks_done ?? 0}
                    sub={`${s.jobdesks_active ?? 0} sedang dikerjakan • ${s.tasks_validated} tugas CI/komputasi`}
                  />
                  <Stat
                    label="HASIL DITERIMA"
                    value={s.accept_pct == null ? "-" : `${s.accept_pct}%`}
                    accent={s.accept_pct == null ? undefined : "text-emerald-400"}
                    sub={`${s.reviews_approved ?? 0} disetujui • ${s.reviews_revised ?? 0} diminta revisi`}
                  />
                </div>

                {/* Sertifikat & Worker Setup Grid */}
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                  {/* Card Sertifikat */}
                  <div className="cyber-box p-6 space-y-3 rounded-xl">
                    <div className="text-xs font-bold text-cyber-amber-bright uppercase tracking-wider font-mono">
                      Sertifikat Kontributor Resmi
                    </div>
                    <div className="h-2 w-full rounded bg-cyber-black overflow-hidden">
                      <div className="h-2 rounded bg-cyber-amber transition-all duration-500" style={{ width: `${cert.progress_pct}%` }} />
                    </div>
                    <p className="text-[11px] text-zinc-400 leading-relaxed font-mono">
                      Syarat: kredit &ge; {cert.min_credits} &amp; hasil diterima &ge; {cert.min_accept_pct}%. Progres: {cert.progress_pct}%.
                    </p>
                    {cert.issued ? (
                      <div className="space-y-2 text-xs pt-1">
                        <p className="text-emerald-400 font-mono">Kode Sertifikat: {cert.issued.code}</p>
                        <div className="flex gap-2">
                          <Link
                            href={`/certificate/${cert.issued.code}`}
                            className="rounded border border-cyber-amber bg-cyber-amber px-3.5 py-1.5 font-bold font-mono text-xs text-cyber-void hover:bg-cyber-amber-bright transition-all"
                          >
                            LIHAT / CETAK
                          </Link>
                          {cert.eligible && (
                            <button
                              type="button"
                              onClick={claimCertificate}
                              disabled={busy}
                              className="rounded border border-cyber-border px-3.5 py-1.5 text-zinc-300 hover:border-cyber-amber font-mono text-xs disabled:opacity-50 transition-colors"
                            >
                              PERBARUI ANGKA
                            </button>
                          )}
                        </div>
                      </div>
                    ) : cert.eligible ? (
                      <button
                        type="button"
                        onClick={claimCertificate}
                        disabled={busy}
                        className="w-full rounded border border-cyber-amber bg-cyber-amber py-2 text-xs font-bold font-mono text-cyber-void hover:bg-cyber-amber-bright shadow-amber-glow disabled:opacity-50 transition-all"
                      >
                        {busy ? "MENERBITKAN..." : "KLAIM SERTIFIKAT SEKARANG"}
                      </button>
                    ) : (
                      <ul className="list-disc pl-4 text-[11px] text-zinc-500 font-mono space-y-1">
                        {cert.missing.map((m) => (
                          <li key={m}>{m}</li>
                        ))}
                      </ul>
                    )}
                    {certMsg && <p className="text-[11px] text-red-300 font-mono">{certMsg}</p>}
                  </div>

                </div>
              </div>
            )}

            {/* TAB 2: PROGRESS & WORK LIST */}
            {activeTab === "progress" && (
              <div className="space-y-6">
                {/* Jobdesk Card */}
                <JobdeskCard />

                {/* Antrean Tugas Komputasi FIFO */}
                <div className="cyber-box p-6 rounded-xl border border-cyber-border">
                  <div className="flex items-center justify-between border-b border-cyber-border pb-3">
                    <div>
                      <span className="text-xs font-bold text-cyber-amber-bright uppercase tracking-wider font-mono">
                        Antrean Beban Komputasi Ilmiah (Job FIFO)
                      </span>
                      <p className="text-[11px] text-zinc-400 font-mono mt-0.5">
                        Daftar job komputasi paralel aktif dan baru selesai di jaringan klaster.
                      </p>
                    </div>
                    <span className="rounded bg-cyber-surface px-2.5 py-1 font-mono text-[11px] text-zinc-300 border border-cyber-border">
                      {jobs.length} Total Job
                    </span>
                  </div>

                  <div className="mt-3 overflow-x-auto">
                    <table className="w-full text-xs font-mono">
                      <thead>
                        <tr className="text-left text-[10px] text-zinc-500 border-b border-cyber-border/40 pb-2">
                          <th className="py-2 pr-3">JOB ID</th>
                          <th className="pr-3">ALGORITMA</th>
                          <th className="pr-3">TAHAP</th>
                          <th className="pr-3">PROGRES TUGAS</th>
                          <th className="pr-3">RESOURCE</th>
                          <th>STATUS</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...activeJobs, ...doneJobs].map((j) => (
                          <tr key={j.id} className="border-t border-cyber-border/40 hover:bg-cyber-surface/30">
                            <td className="py-2.5 pr-3 font-bold text-white">#{j.id}</td>
                            <td className="pr-3 text-cyber-amber-bright font-semibold">{j.kind}</td>
                            <td className="pr-3 tabular-nums">
                              {Math.min(j.current_stage + 1, j.n_stages)} / {j.n_stages}
                            </td>
                            <td className="pr-3 tabular-nums text-zinc-300">
                              {j.done} / {j.total} selesai
                            </td>
                            <td className="pr-3 text-zinc-400">
                              {j.resources.cpus} CPU &bull; {j.resources.memory_mb} MB
                            </td>
                            <td>
                              <span
                                className={`rounded px-2 py-0.5 text-[10px] uppercase font-bold ${
                                  j.status === "running"
                                    ? "bg-amber-950/80 text-amber-300 border border-amber-600/50 animate-pulse"
                                    : "bg-emerald-950/80 text-emerald-300 border border-emerald-600/50"
                                }`}
                              >
                                {j.status}
                              </span>
                            </td>
                          </tr>
                        ))}
                        {!jobs.length && (
                          <tr>
                            <td colSpan={6} className="py-4 text-center text-zinc-500">
                              Belum ada job antrean. Jalankan job via <code>./hpc.sh job</code>.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Riwayat Tugas Worker Anda */}
                <div className="cyber-box p-6 rounded-xl border border-cyber-border">
                  <div className="flex items-center justify-between border-b border-cyber-border pb-3">
                    <div>
                      <span className="text-xs font-bold text-cyber-amber-bright uppercase tracking-wider font-mono">
                        Riwayat Pengerjaan Tugas Worker (Work List)
                      </span>
                      <p className="text-[11px] text-zinc-400 font-mono mt-0.5">
                        25 tugas komputasi terakhir yang dieksekusi oleh mesin laptop/node Anda.
                      </p>
                    </div>
                    <span className="rounded bg-cyber-surface px-2.5 py-1 font-mono text-[11px] text-zinc-300 border border-cyber-border">
                      {me.recent.length} Tugas
                    </span>
                  </div>

                  <div className="mt-3 overflow-x-auto">
                    <table className="w-full text-xs font-mono">
                      <thead>
                        <tr className="text-left text-[10px] text-zinc-500 border-b border-cyber-border/40 pb-2">
                          <th className="py-2 pr-3">TASK ID</th>
                          <th className="pr-3">JOB INDUK</th>
                          <th className="pr-3">TAHAP</th>
                          <th className="pr-3">DURASI</th>
                          <th className="pr-3">KONSENSUS HASIL</th>
                          <th>POIN KREDIT</th>
                        </tr>
                      </thead>
                      <tbody>
                        {me.recent.map((a) => (
                          <tr key={a.id} className="border-t border-cyber-border/40 hover:bg-cyber-surface/30">
                            <td className="py-2.5 pr-3 text-white font-semibold">#{a.task_id}</td>
                            <td className="pr-3 text-zinc-300">
                              #{a.job_id} <span className="text-zinc-500 text-[10px]">({a.kind})</span>
                            </td>
                            <td className="pr-3 tabular-nums text-zinc-400">
                              {a.n_stages > 1 ? `${a.stage + 1} / ${a.n_stages}` : "1 / 1"}
                            </td>
                            <td className="pr-3 tabular-nums text-zinc-300">
                              {a.seconds != null ? `${Number(a.seconds).toFixed(2)} s` : "-"}
                            </td>
                            <td className={`pr-3 font-semibold ${OUTCOME_STYLE[a.outcome] || "text-zinc-300"}`}>
                              {a.outcome}
                            </td>
                            <td className="tabular-nums font-bold text-cyber-amber-bright">
                              {a.outcome === "tervalidasi" ? `+${a.credit} pts` : "0 pts"}
                            </td>
                          </tr>
                        ))}
                        {!me.recent.length && (
                          <tr>
                            <td colSpan={6} className="py-4 text-center text-zinc-500">
                              Belum ada tugas diselesaikan. Jalankan worker Anda: <code>./hpc.sh worker-up 1</code>
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 3: PROFIL SAYA (EDIT PROFIL & UBAH KATA SANDI) */}
            {activeTab === "profile" && (
              <div className="space-y-6">
                <div className="cyber-box p-6 sm:p-8 rounded-xl border border-cyber-border">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-cyber-border pb-4 gap-3">
                    <div>
                      <span className="font-mono text-xs font-bold uppercase tracking-wider text-cyber-amber-bright">
                        Pengaturan Akun Relawan
                      </span>
                      <h2 className="mt-1 text-2xl font-extrabold text-white">Profil Pengguna</h2>
                      <p className="mt-1 text-xs text-zinc-400 font-mono">
                        Perbarui informasi nama tampilan, tautan akun GitHub, dan kelola kata sandi akun Anda.
                      </p>
                    </div>

                    {/* Tombol Ubah Password Floating Menu */}
                    <button
                      type="button"
                      onClick={() => {
                        setShowPasswordModal(true);
                        setPwError(null);
                      }}
                      className="inline-flex items-center space-x-2 rounded-lg border border-cyber-amber/80 bg-cyber-amber/15 px-4 py-2 font-mono text-xs font-bold text-cyber-amber-bright hover:bg-cyber-amber hover:text-cyber-void shadow-amber-glow-sm transition-all"
                    >
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                      </svg>
                      <span>UBAH KATA SANDI</span>
                    </button>
                  </div>

                  {/* Form Edit Profil (Sesuai Struktur Register & Database) */}
                  <form onSubmit={handleSaveProfile} className="mt-6 space-y-6">
                    {/* [1] PERSONAL & CREDENTIALS */}
                    <div className="space-y-4">
                      <div className="border-b border-cyber-border/60 pb-2 font-mono text-xs text-cyber-amber-bright font-semibold">
                        [1] DATA PRIBADI &amp; KREDENSIAL
                      </div>

                      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                        <div>
                          <label className="block font-mono text-xs text-zinc-300 font-semibold mb-1">
                            FIRST NAME <span className="text-cyber-amber-bright">*</span>
                          </label>
                          <input
                            type="text"
                            required
                            value={profileFirstName}
                            onChange={(e) => setProfileFirstName(e.target.value)}
                            placeholder="e.g. Noel"
                            className="w-full rounded-lg border border-cyber-border bg-cyber-black px-3.5 py-2.5 font-mono text-xs text-white placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
                          />
                        </div>

                        <div>
                          <label className="block font-mono text-xs text-zinc-300 font-semibold mb-1">
                            LAST NAME <span className="font-sans text-[10px] text-zinc-500 font-normal">(opsional)</span>
                          </label>
                          <input
                            type="text"
                            value={profileLastName}
                            onChange={(e) => setProfileLastName(e.target.value)}
                            placeholder="e.g. Pratama"
                            className="w-full rounded-lg border border-cyber-border bg-cyber-black px-3.5 py-2.5 font-mono text-xs text-white placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
                          />
                        </div>

                        <div>
                          <label className="block font-mono text-xs text-zinc-300 font-semibold mb-1">
                            PREFERRED USERNAME <span className="text-cyber-amber-bright">*</span>
                          </label>
                          <input
                            type="text"
                            required
                            value={profileUsername}
                            onChange={(e) => setProfileUsername(e.target.value)}
                            placeholder="e.g. noel_hpc"
                            className="w-full rounded-lg border border-cyber-border bg-cyber-black px-3.5 py-2.5 font-mono text-xs text-white placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
                          />
                        </div>

                        <div>
                          <label className="block font-mono text-xs text-zinc-300 font-semibold mb-1">
                            ALAMAT EMAIL TERDAFTAR <span className="text-cyber-amber-bright">*</span>
                          </label>
                          <input
                            type="email"
                            required
                            value={profileEmail}
                            onChange={(e) => setProfileEmail(e.target.value)}
                            placeholder="email@kampus.ac.id"
                            className="w-full rounded-lg border border-cyber-border bg-cyber-black px-3.5 py-2.5 font-mono text-xs text-white placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
                          />
                        </div>
                      </div>
                    </div>

                    {/* [2] GITHUB VERIFICATION & NODE IDENTITY */}
                    <div className="space-y-4 pt-2">
                      <div className="border-b border-cyber-border/60 pb-2 font-mono text-xs text-cyber-amber-bright font-semibold">
                        [2] IDENTITAS GITHUB &amp; WORKER NODE
                      </div>

                      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                        <div>
                          <label className="block font-mono text-xs text-zinc-300 font-semibold mb-1">
                            USERNAME GITHUB <span className="text-cyber-amber-bright">*</span>
                          </label>
                          <div className="relative">
                            <span className="absolute left-3 top-1/2 -translate-y-1/2 font-mono text-xs text-zinc-500">
                              @
                            </span>
                            <input
                              type="text"
                              required
                              value={profileGithub}
                              onChange={(e) => setProfileGithub(e.target.value)}
                              placeholder="username-github"
                              className="w-full rounded-lg border border-cyber-border bg-cyber-black pl-8 pr-3.5 py-2.5 font-mono text-xs text-white placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
                            />
                          </div>
                        </div>

                        <div>
                          <label className="block font-mono text-xs text-zinc-300 font-semibold mb-1">
                            WORKER NODE DISPLAY NAME <span className="font-sans text-[10px] text-zinc-500 font-normal">(opsional)</span>
                          </label>
                          <input
                            type="text"
                            value={profileWorkerNodeName}
                            onChange={(e) => setProfileWorkerNodeName(e.target.value)}
                            placeholder="e.g. laptop-noel-node"
                            className="w-full rounded-lg border border-cyber-border bg-cyber-black px-3.5 py-2.5 font-mono text-xs text-white placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
                          />
                        </div>
                      </div>
                    </div>

                    {/* Metadata Non-editable */}
                    <div className="mt-4 rounded-lg border border-cyber-border/70 bg-cyber-surface/40 p-4 font-mono text-xs grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div>
                        <span className="text-[10px] text-zinc-500 uppercase block">Worker ID</span>
                        <span className="font-bold text-zinc-200">{me.worker.id}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-zinc-500 uppercase block">Bergabung Sejak</span>
                        <span className="text-zinc-200">
                          {new Date(me.worker.created_at).toLocaleDateString("id-ID", {
                            day: "numeric",
                            month: "long",
                            year: "numeric",
                          })}
                        </span>
                      </div>
                      <div>
                        <span className="text-[10px] text-zinc-500 uppercase block">Status Akun</span>
                        <span className="text-emerald-400 font-bold uppercase">{me.worker.status}</span>
                      </div>
                    </div>

                    {/* Toggle Switch: Contributor Appreciation Board */}
                    <div className="rounded-xl border border-cyber-border bg-cyber-surface/60 p-5 space-y-3">
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                        <div>
                          <div className="flex items-center space-x-2">
                            <span className="font-mono text-[11px] font-bold text-cyber-amber-bright uppercase tracking-wider">
                              Privasi &amp; Appreciation Board
                            </span>
                            <span
                              className={`rounded px-2 py-0.5 font-mono text-[10px] font-bold ${
                                showInAppreciation
                                  ? "bg-emerald-950/80 text-emerald-300 border border-emerald-600/50"
                                  : "bg-zinc-800 text-zinc-400 border border-zinc-700"
                              }`}
                            >
                              {showInAppreciation ? "TAMPIL PUBLIK" : "DISEMBUNYIKAN"}
                            </span>
                          </div>
                          <h4 className="text-sm font-bold text-white mt-1">
                            Tampilkan Profil di Contributor Appreciation Board
                          </h4>
                          <p className="text-xs text-zinc-400 leading-relaxed font-sans mt-1 max-w-xl">
                            Jika diaktifkan, profil GitHub Anda, nama lengkap, dan jumlah perolehan kredit akan
                            ditampilkan secara terbuka di halaman Contributor Appreciation Board. Matikan toggle ini
                            kapan saja jika Anda ingin profil disembunyikan.
                          </p>
                        </div>

                        {/* Switch Control */}
                        <button
                          type="button"
                          onClick={handleToggleAppreciation}
                          disabled={togglingConsent}
                          className={`relative inline-flex h-7 w-12 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                            showInAppreciation ? "bg-cyber-amber" : "bg-zinc-700"
                          } ${togglingConsent ? "opacity-50" : ""}`}
                          role="switch"
                          aria-checked={showInAppreciation}
                          title={showInAppreciation ? "Klik untuk mematikan tampilan profil" : "Klik untuk menampilkan profil"}
                        >
                          <span
                            className={`pointer-events-none inline-block h-6 w-6 transform rounded-full bg-cyber-void shadow ring-0 transition duration-200 ease-in-out ${
                              showInAppreciation ? "translate-x-5" : "translate-x-0"
                            }`}
                          />
                        </button>
                      </div>
                    </div>

                    <div className="pt-2 flex justify-end">
                      <button
                        type="submit"
                        disabled={savingProfile}
                        className="flex items-center space-x-2 rounded-lg border border-cyber-amber bg-cyber-amber px-6 py-2.5 font-mono text-xs font-bold text-cyber-void shadow-amber-glow hover:bg-cyber-amber-bright hover:shadow-amber-glow-lg disabled:opacity-50 transition-all"
                      >
                        <span>{savingProfile ? "MENYIMPAN PERUBAHAN..." : "SIMPAN PERUBAHAN PROFIL"}</span>
                        <span>&rarr;</span>
                      </button>
                    </div>
                  </form>
                </div>

                {/* SERTIFIKASI KONTRIBUTOR RESMI (HANYA MUNCUL JIKA MEMENUHI SYARAT ATAU SUDAH DITERBITKAN) */}
                {(cert.eligible || Boolean(cert.issued)) && (
                  <div className="cyber-box p-6 sm:p-8 rounded-xl border border-cyber-amber/60 bg-cyber-surface/60 space-y-5">
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-cyber-border/80 pb-4 gap-3">
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="font-mono text-xs font-bold uppercase tracking-wider text-cyber-amber-bright">
                            Sertifikasi Kelayakan Kontributor
                          </span>
                          <span
                            className={`rounded px-2 py-0.5 font-mono text-[10px] font-bold ${
                              cert.issued
                                ? "bg-emerald-950/80 text-emerald-300 border border-emerald-600/50"
                                : "bg-cyber-amber/20 text-cyber-amber-bright border border-cyber-amber/50"
                            }`}
                          >
                            {cert.issued ? `TERBIT: ${cert.issued.code}` : "MEMENUHI SYARAT KELAYAKAN"}
                          </span>
                        </div>
                        <h3 className="mt-1 text-xl font-bold text-white">Sertifikat Kontributor Resmi</h3>
                        <p className="mt-1 text-xs text-zinc-400 font-mono">
                          Pengakuan resmi atas kontribusi sukarela sumber daya komputasi ilmiah Anda.
                        </p>
                      </div>

                      {/* Tombol Aksi */}
                      <div className="flex items-center gap-2 self-start sm:self-auto">
                        {cert.issued ? (
                          <>
                            <Link
                              href={`/certificate/${cert.issued.code}`}
                              className="inline-flex items-center space-x-2 rounded-lg border border-cyber-amber bg-cyber-amber px-4 py-2 font-mono text-xs font-bold text-cyber-void shadow-amber-glow hover:bg-cyber-amber-bright hover:shadow-amber-glow-lg transition-all"
                            >
                              <span>LIHAT / CETAK SERTIFIKAT</span>
                              <span>&rarr;</span>
                            </Link>
                            {cert.eligible && (
                              <button
                                type="button"
                                onClick={claimCertificate}
                                disabled={busy}
                                className="inline-flex items-center rounded-lg border border-cyber-border bg-cyber-surface px-3 py-2 font-mono text-xs text-zinc-300 hover:border-cyber-amber hover:text-white disabled:opacity-50 transition-colors"
                              >
                                {busy ? "MEMPERBARUI..." : "PERBARUI ANGKA"}
                              </button>
                            )}
                          </>
                        ) : (
                          <button
                            type="button"
                            onClick={claimCertificate}
                            disabled={busy}
                            className="inline-flex items-center space-x-2 rounded-lg border border-cyber-amber bg-cyber-amber px-5 py-2 font-mono text-xs font-bold text-cyber-void shadow-amber-glow hover:bg-cyber-amber-bright hover:shadow-amber-glow-lg disabled:opacity-50 transition-all"
                          >
                            <span>{busy ? "MENERBITKAN..." : "KLAIM & TERBITKAN SERTIFIKAT"}</span>
                            <span>⭐</span>
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Preview Sertifikat Box */}
                    <div className="relative rounded-lg border-2 border-double border-cyber-amber/60 bg-cyber-black/80 p-6 text-center space-y-3">
                      <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-cyber-amber-bright">
                        IDLESCALE VOLUNTEER COMPUTING PLATFORM
                      </div>
                      <div className="text-xs text-zinc-400 font-sans">Diberikan secara terhormat kepada:</div>
                      <div className="text-2xl sm:text-3xl font-extrabold text-white tracking-wide">
                        {[profileFirstName.trim(), profileLastName.trim()].filter(Boolean).join(" ") || me.worker.name}
                      </div>
                      <div className="font-mono text-xs text-cyber-amber-bright">
                        {profileGithub.trim()
                          ? `@${profileGithub.trim().replace(/^@/, "")}`
                          : me.worker.github_username
                          ? `@${me.worker.github_username}`
                          : "Verified Contributor"}
                      </div>

                      <p className="mx-auto max-w-xl font-sans text-xs text-zinc-300 leading-relaxed pt-2">
                        Atas dedikasi sumber daya komputasi ilmiah dengan perolehan{" "}
                        <span className="font-bold text-cyber-amber-bright">{s.credits} kredit</span> dari{" "}
                        <span className="font-bold text-white">{s.jobdesks_done ?? 0} jobdesk selesai</span> dan{" "}
                        <span className="font-bold text-white">{s.tasks_validated} tugas komputasi tervalidasi</span>{" "}
                        (hasil diterima:{" "}
                        <span className="font-bold text-emerald-400">{s.accept_pct == null ? "-" : `${s.accept_pct}%`}</span>).
                      </p>

                      <div className="pt-3 border-t border-cyber-border/60 flex flex-wrap items-center justify-between gap-2 font-mono text-[11px] text-zinc-400">
                        <span>
                          Status:{" "}
                          <strong className="text-emerald-400">
                            {cert.issued ? `Aktif (${cert.issued.code})` : "Siap Diterbitkan"}
                          </strong>
                        </span>
                        <span>
                          {cert.issued
                            ? `Diterbitkan: ${new Date(cert.issued.issued_at).toLocaleDateString("id-ID", {
                                day: "numeric",
                                month: "long",
                                year: "numeric",
                              })}`
                            : `Minimal Kredit: ${cert.min_credits}`}
                        </span>
                      </div>
                    </div>

                    {certMsg && (
                      <p className="text-xs text-red-300 font-mono bg-red-950/40 border border-red-500/40 rounded p-2.5">
                        {certMsg}
                      </p>
                    )}

                    <div className="rounded-lg border border-cyber-border/70 bg-cyber-void/60 p-3.5 text-[11px] font-mono text-zinc-400 flex items-start space-x-2">
                      <span className="text-cyber-amber-bright text-sm leading-none">ℹ</span>
                      <span>
                        Nama pada sertifikat di atas dicetak sesuai dengan <strong>First Name</strong> dan{" "}
                        <strong>Last Name</strong> profil Anda (
                        <strong className="text-white">
                          {[profileFirstName.trim(), profileLastName.trim()].filter(Boolean).join(" ") || me.worker.name}
                        </strong>
                        ). Jika Anda mengubah nama di atas, simpan profil terlebih dahulu kemudian perbarui sertifikat.
                      </span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </main>
        </div>
      </div>

      {/* ===================================================================== */}
      {/* FLOATING MODAL: UBAH KATA SANDI (DENGAN TOMBOL HIDE & SEEN)           */}
      {/* ===================================================================== */}
      {showPasswordModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
          <div className="relative w-full max-w-md rounded-xl border border-cyber-amber/80 bg-cyber-void p-6 sm:p-7 shadow-2xl shadow-amber-950/50">
            {/* Header Modal */}
            <div className="flex items-center justify-between border-b border-cyber-border pb-4">
              <div className="flex items-center space-x-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-cyber-amber bg-cyber-surface text-cyber-amber-bright text-sm">
                  🔒
                </div>
                <div>
                  <h3 className="font-bold text-sm text-white">Ubah Kata Sandi Akun</h3>
                  <span className="font-mono text-[10px] text-cyber-amber-bright">
                    PASSWORD CREDENTIAL SETTINGS
                  </span>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setShowPasswordModal(false)}
                className="rounded border border-cyber-border bg-cyber-surface px-2 py-1 text-xs text-zinc-400 hover:border-cyber-amber hover:text-white transition-colors"
              >
                ✕
              </button>
            </div>

            {pwError && (
              <div className="mt-4 rounded border border-red-500/50 bg-red-950/40 p-3 font-mono text-xs text-red-300">
                Peringatan: {pwError}
              </div>
            )}

            <form onSubmit={handleSavePassword} className="mt-5 space-y-4">
              {/* Password Saat Ini (Opsional jika baru pertama kali set) */}
              <div>
                <label className="block font-mono text-[11px] text-zinc-300 mb-1">
                  KATA SANDI SAAT INI (JIKA ADA)
                </label>
                <div className="relative">
                  <input
                    type={showCurrentPw ? "text" : "password"}
                    value={currentPw}
                    onChange={(e) => setCurrentPw(e.target.value)}
                    placeholder="••••••••••••"
                    className="w-full rounded-lg border border-cyber-border bg-cyber-black px-3.5 py-2 pr-10 font-mono text-xs text-white placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
                  />
                  <button
                    type="button"
                    onClick={() => setShowCurrentPw(!showCurrentPw)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-cyber-amber-bright p-1"
                    title={showCurrentPw ? "Sembunyikan password" : "Lihat password"}
                  >
                    {showCurrentPw ? (
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18" />
                      </svg>
                    ) : (
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              {/* Password Baru */}
              <div>
                <label className="block font-mono text-[11px] text-zinc-300 mb-1">
                  KATA SANDI BARU (MIN. 8 KARAKTER) *
                </label>
                <div className="relative">
                  <input
                    type={showNewPw ? "text" : "password"}
                    required
                    minLength={8}
                    value={newPw}
                    onChange={(e) => setNewPw(e.target.value)}
                    placeholder="••••••••••••"
                    className="w-full rounded-lg border border-cyber-border bg-cyber-black px-3.5 py-2 pr-10 font-mono text-xs text-white placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
                  />
                  <button
                    type="button"
                    onClick={() => setShowNewPw(!showNewPw)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-cyber-amber-bright p-1"
                    title={showNewPw ? "Sembunyikan password" : "Lihat password"}
                  >
                    {showNewPw ? (
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18" />
                      </svg>
                    ) : (
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              {/* Konfirmasi Password Baru */}
              <div>
                <label className="block font-mono text-[11px] text-zinc-300 mb-1">
                  KONFIRMASI KATA SANDI BARU *
                </label>
                <div className="relative">
                  <input
                    type={showConfirmPw ? "text" : "password"}
                    required
                    value={confirmPw}
                    onChange={(e) => setConfirmPw(e.target.value)}
                    placeholder="••••••••••••"
                    className="w-full rounded-lg border border-cyber-border bg-cyber-black px-3.5 py-2 pr-10 font-mono text-xs text-white placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPw(!showConfirmPw)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-cyber-amber-bright p-1"
                    title={showConfirmPw ? "Sembunyikan password" : "Lihat password"}
                  >
                    {showConfirmPw ? (
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18" />
                      </svg>
                    ) : (
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              <div className="mt-6 flex justify-end space-x-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowPasswordModal(false)}
                  className="rounded-lg border border-cyber-border bg-cyber-surface px-4 py-2 font-mono text-xs text-zinc-300 hover:text-white transition-colors"
                >
                  BATAL
                </button>
                <button
                  type="submit"
                  disabled={pwSubmitting}
                  className="rounded-lg border border-cyber-amber bg-cyber-amber px-5 py-2 font-mono text-xs font-bold text-cyber-void shadow-amber-glow hover:bg-cyber-amber-bright disabled:opacity-50 transition-all"
                >
                  {pwSubmitting ? "MENYIMPAN..." : "SIMPAN KATA SANDI BARU"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

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
                  <h3 className="font-bold text-sm text-white">Contributor Appreciation Board</h3>
                  <span className="font-mono text-[10px] text-cyber-amber-bright">
                    APPRECIATION CONSENT CONFIRMATION
                  </span>
                </div>
              </div>

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
                Terima kasih banyak atas kontribusi daya komputasi dari node <strong>{me.worker.name}</strong> untuk simulasi terbuka IdleScale!
              </p>
              <p className="text-zinc-400 leading-relaxed">
                Sebelum Anda mengakhiri sesi komputasi dan keluar, apakah Anda bersedia dicantumkan di <strong>Contributor Appreciation Board</strong> publik proyek ini?
              </p>

              {/* Warning Notice Box */}
              <div className="rounded-lg border border-amber-500/40 bg-amber-950/20 p-3.5 text-amber-200 space-y-1.5 font-mono text-[11px]">
                <div className="flex items-center space-x-2 font-bold text-cyber-amber-bright">
                  <span>⚠️</span>
                  <span>PERINGATAN PRIVASI &amp; TAUTAN PROFIL:</span>
                </div>
                <p className="leading-relaxed text-zinc-300 font-sans">
                  Jika Anda memilih <strong>&quot;Tampilkan Profil Saya&quot;</strong>, kartu apresiasi Anda akan memuat foto profil, nama, serta <strong>tombol tautan langsung yang mengarahkan pengunjung ke profil GitHub Anda (github.com/{me.worker.github_username || "username"})</strong>.
                </p>
              </div>

              {/* Informative Note: Only shown once */}
              <div className="rounded-lg border border-cyber-amber/50 bg-cyber-amber-darkest/40 p-3 text-cyber-amber-bright space-y-1 font-mono text-[11px]">
                <div className="flex items-center space-x-1.5 font-bold">
                  <span>💡</span>
                  <span>KONFIRMASI INI HANYA MUNCUL SEKALI:</span>
                </div>
                <p className="text-zinc-300 font-sans leading-relaxed">
                  Pilihan Anda akan disimpan. Setelah ini, Anda dapat menyalakan atau mematikan izin tampilan profil kapan saja melalui <strong>tombol toggle di tab Profil Saya</strong>.
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
