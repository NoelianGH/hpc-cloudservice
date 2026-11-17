"use client";
import React, { useEffect, useState } from "react";
import Link from "next/link";

interface Contributor {
  name: string;
  github_username: string;
  avatar_url: string;
  github_url: string;
  credits: number;
  badge: string | null;
  joined_at: string | null;
  consent_at?: string | null;
}

interface AppreciationResponse {
  contributors: Contributor[];
  total: number;
}

export default function AppreciationPage() {
  const [data, setData] = useState<AppreciationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/appreciation", { cache: "no-store" })
      .then(async (res) => {
        const d = await res.json().catch(() => ({ contributors: [], total: 0 }));
        return d;
      })
      .then((d) => {
        setData(d || { contributors: [], total: 0 });
        if (d?.error) {
          setError(d.error);
        } else {
          setError(null);
        }
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Gagal menghubungi server.");
        setLoading(false);
      });
  }, []);

  return (
    <div className="relative min-h-screen py-12 px-4 sm:px-6 lg:px-8 font-sans">
      {/* Background glow radial */}
      <div className="pointer-events-none absolute left-1/2 top-10 -translate-x-1/2 h-[400px] w-[750px] rounded-full bg-cyber-amber-deep/15 blur-[120px]" />

      <div className="mx-auto max-w-7xl">
        {/* Header Section */}
        <div className="text-center max-w-3xl mx-auto">
          <div className="inline-flex items-center space-x-2 rounded-full border border-cyber-amber/40 bg-cyber-surface/90 px-3.5 py-1 text-xs text-cyber-amber-bright shadow-amber-glow-sm">
            <span className="h-2 w-2 rounded-full bg-cyber-amber-bright animate-ping"></span>
            <span className="font-mono uppercase tracking-wider">Hall of Contributors • IdleScale</span>
          </div>

          <h1 className="mt-4 text-3xl font-extrabold tracking-tight text-white sm:text-4xl lg:text-5xl">
            Contributor Appreciation Board
          </h1>
          <p className="mt-3 text-sm sm:text-base text-zinc-300 leading-relaxed font-normal">
            Our deepest gratitude to the dedicated volunteers donating idle CPU power to advance open scientific
            computing across the <strong>IdleScale</strong> community network.
          </p>

          {/* Privacy & Consent Notice Banner */}
          <div className="mt-6 rounded-lg border border-cyber-amber/30 bg-cyber-surface/80 p-4 text-left text-xs text-zinc-300 shadow-lg">
            <div className="flex items-start space-x-3">
              <span className="text-cyber-amber-bright text-base mt-0.5">ℹ</span>
              <div className="leading-relaxed">
                <span className="font-semibold text-white">Privacy &amp; Consent Transparency:</span>
                <p className="mt-1 text-zinc-400">
                  This board exclusively features contributors who have given explicit consent upon concluding their computing session.
                  Click on any contributor card to directly explore their official GitHub profile and portfolio.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Counter Bar */}
        <div className="mt-10 flex flex-wrap items-center justify-between border-b border-cyber-border/70 pb-4 gap-3 text-xs">
          <div className="flex items-center space-x-2">
            <span className="font-mono text-zinc-400">TOTAL VERIFIED CONTRIBUTORS:</span>
            <span className="font-mono font-bold text-cyber-amber-bright text-sm">
              {data?.total ?? 0} CONTRIBUTORS
            </span>
          </div>
          <div className="flex items-center space-x-3 text-[11px] text-zinc-400">
            <span className="flex items-center space-x-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-400"></span>
              <span>Active GitHub Profile</span>
            </span>
            <span>•</span>
            <span className="text-zinc-500">Click any card to open GitHub</span>
          </div>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="py-20 text-center">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-cyber-amber border-t-transparent"></div>
            <p className="mt-3 font-mono text-xs text-zinc-400">Loading appreciation board contributors...</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="my-10 rounded-lg border border-red-500/50 bg-red-950/40 p-4 text-center text-xs text-red-300 font-mono">
            Peringatan: {error}
          </div>
        )}

        {/* 4-COLUMN APPRECIATION GRID */}
        {!loading && data && data.contributors.length > 0 && (
          <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5 sm:gap-6">
            {data.contributors.map((c) => (
              <a
                key={c.github_username}
                href={c.github_url}
                target="_blank"
                rel="noopener noreferrer"
                title={`Kunjungi profil GitHub @${c.github_username}`}
                className="group relative flex flex-col justify-between overflow-hidden rounded-xl border border-cyber-border/80 bg-cyber-void p-5 transition-all duration-300 hover:-translate-y-1.5 hover:border-cyber-amber hover:shadow-amber-glow cursor-pointer text-left"
              >
                {/* Subtle top amber highlight on hover */}
                <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-cyber-amber to-transparent opacity-0 transition-opacity group-hover:opacity-100" />

                <div>
                  {/* Top card bar: Avatar and GitHub Icon */}
                  <div className="flex items-start justify-between">
                    <div className="relative">
                      {/* GitHub Avatar PP */}
                      <img
                        src={c.avatar_url}
                        alt={c.name}
                        className="h-14 w-14 rounded-full border-2 border-cyber-border object-cover transition-all group-hover:border-cyber-amber-bright group-hover:shadow-amber-glow-sm"
                        onError={(e) => {
                          // Fallback jika avatar gagal dimuat
                          (e.target as HTMLImageElement).src = `https://ui-avatars.com/api/?name=${encodeURIComponent(
                            c.name
                          )}&background=18181b&color=f59e0b`;
                        }}
                      />
                      <span className="absolute bottom-0 right-0 h-3.5 w-3.5 rounded-full border-2 border-cyber-void bg-emerald-500" />
                    </div>

                    {/* GitHub Link Button Pill */}
                    <div className="flex items-center space-x-1 rounded-full border border-cyber-border bg-cyber-surface/90 px-2.5 py-1 text-[11px] font-mono text-zinc-400 group-hover:border-cyber-amber/70 group-hover:text-cyber-amber-bright transition-colors">
                      <svg
                        className="h-3.5 w-3.5 fill-current"
                        viewBox="0 0 24 24"
                      >
                        <path
                          fillRule="evenodd"
                          clipRule="evenodd"
                          d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
                        />
                      </svg>
                      <span>Profil &rarr;</span>
                    </div>
                  </div>

                  {/* Name & GitHub Username */}
                  <div className="mt-4">
                    <h3 className="font-bold text-sm text-white group-hover:text-cyber-amber-bright transition-colors line-clamp-1">
                      {c.name}
                    </h3>
                    <p className="font-mono text-xs text-zinc-400 group-hover:text-zinc-300 transition-colors">
                      @{c.github_username}
                    </p>
                  </div>
                </div>

                {/* Bottom stats & badge */}
                <div className="mt-5 border-t border-cyber-border/60 pt-3">
                  <div className="flex items-center justify-between text-xs">
                    <div className="font-mono">
                      <span className="text-[10px] text-zinc-500 uppercase block">Total Kredit</span>
                      <span className="font-bold text-cyber-amber-bright tabular-nums">
                        {c.credits} pts
                      </span>
                    </div>

                    {c.badge && (
                      <span className="rounded bg-cyber-amber-darkest/90 border border-cyber-amber/50 px-2 py-0.5 font-mono text-[10px] font-semibold text-cyber-amber-bright">
                        {c.badge.toUpperCase()}
                      </span>
                    )}
                  </div>
                </div>
              </a>
            ))}
          </div>
        )}

        {/* Empty State jika belum ada relawan yang consent */}
        {!loading && data && data.contributors.length === 0 && (
          <div className="my-12 rounded-xl border border-cyber-border bg-cyber-surface/50 p-10 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full border border-cyber-amber/40 bg-cyber-surface text-cyber-amber-bright text-xl">
              ⭐
            </div>
            <h3 className="mt-4 font-bold text-base text-white">No Profiles Displayed Yet</h3>
            <p className="mt-2 text-xs text-zinc-400 max-w-md mx-auto leading-relaxed">
              This appreciation board strictly enforces privacy-first consent. Contributor profiles only appear here 
              after volunteers explicitly choose <strong>&quot;Show My Profile&quot;</strong> upon ending their compute session.
            </p>
            <div className="mt-6 flex justify-center gap-3">
              <Link
                href="/join"
                className="rounded border border-cyber-amber bg-cyber-amber px-5 py-2 text-xs font-semibold text-cyber-void shadow-amber-glow hover:bg-cyber-amber-bright transition-all"
              >
                Join as Volunteer &rarr;
              </Link>
              <Link
                href="/dashboard"
                className="rounded border border-cyber-border px-5 py-2 text-xs font-semibold text-zinc-300 hover:border-cyber-amber transition-all"
              >
                Open Dashboard
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
