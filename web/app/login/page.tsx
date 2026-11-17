"use client";
import React, { useEffect, useState } from "react";
import Link from "next/link";

/**
 * Login website relawan dengan EMAIL + PASSWORD (dibuat saat Register).
 * Token worker (hpc_w_...) khusus untuk CLI/worker; di sini hanya dipakai sekali oleh akun lama
 * dari './hpc.sh worker-login' yang belum punya password, lalu password dibuat di dashboard.
 * Server menyimpan SESI web di cookie httpOnly selama 7 hari, jadi tidak perlu login ulang.
 */
export default function LoginPage() {
  const [mode, setMode] = useState<"password" | "token">("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [workerToken, setWorkerToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);

  useEffect(() => {
    setExpired(new URLSearchParams(window.location.search).has("expired"));
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setLoading(true);
    try {
      const res = await fetch("/api/volunteer/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(mode === "password" ? { email: email.trim(), password } : { token: workerToken.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setErrorMsg(data.detail || "Login ditolak koordinator.");
        return;
      }
      // Navigasi penuh agar middleware dan navbar membaca cookie sesi yang baru dibuat
      window.location.href = "/dashboard";
    } catch (err: any) {
      setErrorMsg("Gagal menghubungi server: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const input =
    "mt-1 w-full rounded border border-cyber-border bg-cyber-black px-3 py-2 font-mono text-xs text-white placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber";

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

        {expired && !errorMsg && (
          <div className="mt-6 rounded border border-cyber-amber/50 bg-cyber-amber-darkest/40 p-3 font-mono text-xs text-cyber-amber-bright">
            Sesi login Anda sudah berakhir. Silakan masuk lagi.
          </div>
        )}

        {errorMsg && (
          <div className="mt-6 rounded border border-red-500/50 bg-red-950/40 p-3 font-mono text-xs text-red-300">
            Peringatan: {errorMsg}
          </div>
        )}

        <div className="cyber-box mt-6 p-6 sm:p-8">
          <form onSubmit={handleLogin} className="space-y-4">
            {mode === "password" ? (
              <>
                <div>
                  <label className="block font-mono text-[11px] text-zinc-300">EMAIL</label>
                  <input type="email" required autoComplete="email" value={email}
                    onChange={(e) => setEmail(e.target.value)} placeholder="nama@kampus.ac.id" className={input} />
                </div>
                <div>
                  <label className="block font-mono text-[11px] text-zinc-300">PASSWORD</label>
                  <div className="relative mt-1">
                    <input
                      type={showPassword ? "text" : "password"}
                      required
                      autoComplete="current-password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      className={`${input} mt-0 pr-10`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-cyber-amber-bright focus:outline-none p-1 transition-colors"
                      title={showPassword ? "Sembunyikan password" : "Lihat password"}
                      aria-label={showPassword ? "Sembunyikan password" : "Lihat password"}
                    >
                      {showPassword ? (
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
              </>
            ) : (
              <div>
                <label className="block font-mono text-[11px] text-zinc-300">WORKER_TOKEN</label>
                <textarea rows={3} required value={workerToken} onChange={(e) => setWorkerToken(e.target.value)}
                  placeholder="hpc_w_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" className={`${input} text-cyber-amber-bright`} />
                <p className="mt-1 font-mono text-[10px] text-zinc-500">
                  Hanya untuk akun yang dibuat lewat <code>./hpc.sh worker-login</code> dan belum punya password.
                  Setelah masuk, buat password di dashboard; berikutnya login cukup dengan email + password.
                </p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || (mode === "password" ? !email.trim() || !password : !workerToken.trim())}
              className="mt-6 flex w-full items-center justify-center space-x-2 rounded border border-cyber-amber bg-cyber-amber py-3 font-mono text-xs font-bold text-cyber-void shadow-amber-glow transition-all hover:bg-cyber-amber-bright hover:shadow-amber-glow-lg disabled:opacity-50"
            >
              <span>{loading ? "MEMERIKSA..." : "MASUK"}</span>
              <span>&rarr;</span>
            </button>

            <button
              type="button"
              onClick={() => { setMode(mode === "password" ? "token" : "password"); setErrorMsg(null); }}
              className="w-full text-center font-mono text-[11px] text-zinc-400 hover:text-cyber-amber-bright"
            >
              {mode === "password" ? "Akun lama tanpa password? Masuk dengan token worker" : "Kembali ke login email + password"}
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
