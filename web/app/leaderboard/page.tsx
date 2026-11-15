"use client";
import React, { useEffect, useState } from "react";
import Link from "next/link";

type Row = {
  rank: number; name: string; github_username: string | null; credits: number; badge: string | null;
  tasks_validated: number; reject_pct: number; compute_seconds: number; jobs_joined: number;
  online: boolean; verified: boolean;
};
type Data = {
  leaderboard: Row[];
  totals: { volunteers: number; verified: number; credits: number; certificates: number };
  rules: { badges: { name: string; credits: number }[]; certificate_min_credits: number; certificate_max_reject_pct: number };
};

export default function LeaderboardPage() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = () =>
      fetch("/api/leaderboard", { cache: "no-store" })
        .then(async (r) => {
          const d = await r.json();
          if (!r.ok) throw new Error(d.detail || "Koordinator tidak dapat dihubungi.");
          setData(d);
          setError(null);
        })
        .catch((e) => setError(e.message));
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 font-mono sm:px-6 lg:px-8">
      <span className="text-xs font-bold uppercase tracking-widest text-cyber-amber-bright">// LEADERBOARD RELAWAN</span>
      <h1 className="mt-1 text-2xl font-extrabold text-white sm:text-3xl">PAPAN PERINGKAT KONTRIBUTOR</h1>
      <p className="mt-2 max-w-3xl text-xs text-zinc-400">
        Satu kredit = satu tugas yang hasilnya sama dengan quorum (minimal 2 worker berbeda menghasilkan hash yang
        identik). Hasil palsu tidak menambah kredit dan menaikkan persentase &quot;ditolak&quot;.
      </p>

      {error && <div className="mt-6 rounded border border-red-500/50 bg-red-950/40 p-3 text-xs text-red-300">[ERROR]: {error}</div>}

      {data && (
        <>
          <div className="mt-6 grid grid-cols-2 gap-3 text-xs md:grid-cols-4">
            {[
              ["RELAWAN AKTIF", data.totals.volunteers],
              ["TERVERIFIKASI GITHUB", data.totals.verified],
              ["TOTAL KREDIT", data.totals.credits],
              ["SERTIFIKAT TERBIT", data.totals.certificates],
            ].map(([k, v]) => (
              <div key={k as string} className="cyber-box p-3">
                <div className="text-[10px] text-zinc-500">{k}</div>
                <div className="text-xl font-bold text-white tabular-nums">{v}</div>
              </div>
            ))}
          </div>

          <div className="cyber-box mt-6 overflow-x-auto p-4">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[10px] text-zinc-500">
                  <th className="py-1 pr-3">#</th><th className="pr-3">RELAWAN</th><th className="pr-3">LENCANA</th>
                  <th className="pr-3">KREDIT</th><th className="pr-3">TUGAS VALID</th><th className="pr-3">DITOLAK</th>
                  <th className="pr-3">KOMPUTASI</th><th>STATUS</th>
                </tr>
              </thead>
              <tbody>
                {data.leaderboard.map((r) => (
                  <tr key={r.rank} className="border-t border-cyber-border/50">
                    <td className={`py-1.5 pr-3 font-bold ${r.rank <= 3 ? "text-cyber-amber-bright" : ""}`}>{r.rank}</td>
                    <td className="pr-3">
                      <span className="text-white">{r.name}</span>{" "}
                      {r.github_username ? (
                        <a href={`https://github.com/${r.github_username}`} target="_blank" rel="noreferrer" className="text-zinc-400 hover:text-cyber-amber-bright">
                          @{r.github_username}
                        </a>
                      ) : (
                        <span className="text-zinc-600">anonim</span>
                      )}
                    </td>
                    <td className="pr-3">{r.badge || "-"}</td>
                    <td className="pr-3 font-bold tabular-nums text-cyber-amber-bright">{r.credits}</td>
                    <td className="pr-3 tabular-nums">{r.tasks_validated}</td>
                    <td className={`pr-3 tabular-nums ${r.reject_pct > 10 ? "text-red-300" : ""}`}>{r.reject_pct}%</td>
                    <td className="pr-3 tabular-nums text-zinc-400">{Math.round(r.compute_seconds / 60)} mnt</td>
                    <td className={r.online ? "text-emerald-400" : "text-zinc-500"}>{r.online ? "online" : "offline"}</td>
                  </tr>
                ))}
                {!data.leaderboard.length && <tr><td colSpan={8} className="py-2 text-zinc-500">Belum ada relawan.</td></tr>}
              </tbody>
            </table>
          </div>

          <div className="mt-6 grid gap-4 text-xs md:grid-cols-2">
            <div className="cyber-box p-4">
              <div className="font-bold text-cyber-amber-bright">// LENCANA</div>
              <ul className="mt-2 space-y-1 text-zinc-300">
                {data.rules.badges.map((b) => <li key={b.name}>{b.name}: ≥ {b.credits} kredit</li>)}
              </ul>
            </div>
            <div className="cyber-box p-4">
              <div className="font-bold text-cyber-amber-bright">// SERTIFIKAT KONTRIBUTOR</div>
              <p className="mt-2 text-zinc-300">
                Kredit ≥ {data.rules.certificate_min_credits}, hasil ditolak ≤ {data.rules.certificate_max_reject_pct}%, akun
                terverifikasi GitHub + OTP. Ambil dari <Link href="/dashboard" className="text-cyber-amber-bright hover:underline">dashboard relawan</Link>.
                Setiap sertifikat punya kode yang bisa dicek keasliannya oleh siapa pun.
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
