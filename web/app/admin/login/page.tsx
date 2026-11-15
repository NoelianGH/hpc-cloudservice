"use client";
import React, { useState } from "react";

export default function AdminLoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setLoading(true);
    try {
      const res = await fetch("/api/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setErrorMsg(typeof data.detail === "string" ? data.detail : "Login gagal.");
        return;
      }
      setPassword("");
      // Navigasi penuh (bukan client-side) agar middleware membaca cookie sesi yang baru
      window.location.assign("/admin");
    } catch (err: any) {
      setErrorMsg("Tidak dapat menghubungi server: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative py-16 px-4 sm:px-6 lg:px-8">
      <div className="pointer-events-none absolute left-1/2 top-10 -translate-x-1/2 h-[300px] w-[500px] rounded-full bg-cyber-amber-deep/15 blur-[90px]" />

      <div className="mx-auto max-w-md">
        <div className="text-center">
          <span className="font-mono text-xs font-semibold uppercase tracking-widest text-cyber-amber-bright">
            // RESTRICTED AREA
          </span>
          <h1 className="mt-2 font-mono text-2xl font-extrabold tracking-tight text-white sm:text-3xl">
            ADMIN CONSOLE LOGIN
          </h1>
          <p className="mt-2 font-mono text-xs text-zinc-400">
            Khusus admin head node. Masuk dengan email dan password admin yang diatur lewat{" "}
            <code className="text-cyber-amber-bright">./hpc.sh admin-setup</code>.
          </p>
        </div>

        {errorMsg && (
          <div
            role="alert"
            className="mt-6 rounded border border-red-500/50 bg-red-950/40 p-3 font-mono text-xs text-red-300"
          >
            [ERROR]: {errorMsg}
          </div>
        )}

        <div className="cyber-box mt-6 p-6 sm:p-8">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="admin-email" className="block font-mono text-[11px] text-zinc-300">
                ADMIN EMAIL
              </label>
              <input
                id="admin-email"
                type="email"
                required
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@example.com"
                className="mt-1 w-full rounded border border-cyber-border bg-cyber-black px-3 py-2 font-mono text-xs text-white placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
              />
            </div>

            <div>
              <label htmlFor="admin-password" className="block font-mono text-[11px] text-zinc-300">
                PASSWORD
              </label>
              <input
                id="admin-password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="mt-1 w-full rounded border border-cyber-border bg-cyber-black px-3 py-2 font-mono text-xs text-white placeholder-zinc-600 focus:border-cyber-amber focus:outline-none focus:ring-1 focus:ring-cyber-amber"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="mt-6 flex w-full items-center justify-center space-x-2 rounded border border-cyber-amber bg-cyber-amber py-3 font-mono text-xs font-bold text-cyber-void shadow-amber-glow transition-all hover:bg-cyber-amber-bright hover:shadow-amber-glow-lg disabled:opacity-50"
            >
              <span>{loading ? "MEMVERIFIKASI..." : "MASUK KE ADMIN CONSOLE"}</span>
              <span>&rarr;</span>
            </button>
          </form>

          <p className="mt-6 border-t border-cyber-border pt-4 text-center font-mono text-[10px] text-zinc-500">
            5 kali salah password akan mengunci login selama 15 menit.
          </p>
        </div>
      </div>
    </div>
  );
}
