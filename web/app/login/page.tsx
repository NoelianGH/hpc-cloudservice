"use client";
import React, { useState } from "react";
import Link from "next/link";

/**
 * Login relawan. Satu-satunya kredensial relawan adalah WORKER_TOKEN (hpc_w_...) yang
 * didapat setelah verifikasi GitHub + OTP email. Token dicek ke koordinator lewat
 * /api/volunteer/login; bila sah, server menyimpannya di cookie httpOnly.
 */
export default function LoginPage() {
  const [workerToken, setWorkerToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setLoading(true);
    try {
      const res = await fetch("/api/volunteer/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: workerToken.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setErrorMsg(data.detail || "Token ditolak koordinator.");
        return;
      }
      // Navigasi penuh agar middleware membaca cookie sesi yang baru dibuat
      window.location.href = "/dashboard";
    } catch (err: any) {
      setErrorMsg("Gagal menghubungi server: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative py-16 px-4 sm:px-6 lg:px-8">
      <div className="pointer-events-none absolute left-1/2 top-10 -translate-x-1/2 h-[300px] w-[500px] rounded-full bg-cyber-amber-deep/15 blur-[90px]" />

      <div className="mx-auto max-w-md">
        <div className="text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl border border-cyber-amber/60 bg-cyber-surface shadow-amber-glow-sm">
            <svg
              className="h-6 w-6 text-cyber-amber-bright"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2" />
              <line x1="12" y1="22" x2="12" y2="12" />
              <line x1="22" y1="8.5" x2="12" y2="12" />
              <line x1="2" y1="8.5" x2="12" y2="12" />
            </svg>
          </div>
          <span className="font-mono text-xs font-semibold uppercase tracking-wider text-cyber-amber-bright">
            Portal Masuk Relawan
          </span>
          <h1 className="mt-2 font-mono text-2xl font-extrabold tracking-tight text-white sm:text-3xl">
            MASUK KE DASHBOARD RELAWAN
          </h1>
          <p className="mt-2 font-mono text-xs text-zinc-400">
            Lihat perolehan kredit, peringkat leaderboard, riwayat tugas, dan klaim sertifikat resmi Anda.
          </p>
        </div>

        {errorMsg && (
          <div className="mt-6 rounded border border-red-500/50 bg-red-950/40 p-3 font-mono text-xs text-red-300">
            Peringatan: {errorMsg}
          </div>
        )}

        <div className="cyber-box mt-6 p-6 sm:p-8">
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block font-mono text-[11px] text-zinc-300">WORKER_TOKEN</label>
              <textarea
                rows={3}
                required
                value={workerToken}
                onChange={(e) => setWorkerToken(e.target.value)}
                placeholder="hpc_w_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                className="mt-1 w-full rounded border border-cyber-border bg-cyber-black px-3 py-2 font-mono text-xs text-cyber-amber-bright placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
              />
              <p className="mt-1 font-mono text-[10px] text-zinc-500">
                Token diterbitkan setelah verifikasi GitHub + OTP email (halaman Register atau{" "}
                <code>./hpc.sh worker-login</code>). Ada juga di file <code>.env</code> Anda. Token bersama
                (WORKER_TOKEN dari .env contoh) tidak bisa dipakai login karena tidak punya profil relawan.
              </p>
            </div>

            <button
              type="submit"
              disabled={loading || !workerToken.trim()}
              className="mt-6 flex w-full items-center justify-center space-x-2 rounded border border-cyber-amber bg-cyber-amber py-3 font-mono text-xs font-bold text-cyber-void shadow-amber-glow transition-all hover:bg-cyber-amber-bright hover:shadow-amber-glow-lg disabled:opacity-50"
            >
              <span>{loading ? "MEMERIKSA TOKEN..." : "MASUK"}</span>
              <span>&rarr;</span>
            </button>
          </form>

          <div className="mt-6 border-t border-cyber-border pt-4 text-center font-mono text-xs text-zinc-400">
            Belum jadi relawan?{" "}
            <Link href="/join" className="text-cyber-amber-bright hover:underline">
              Cara bergabung &rarr;
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
