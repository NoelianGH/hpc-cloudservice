import React from "react";
import Link from "next/link";

export default function CyberFooter() {
  return (
    <footer className="mt-auto border-t border-cyber-border bg-cyber-void py-10 font-sans text-xs text-zinc-400">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-8 md:grid-cols-4">
          <div className="space-y-3">
            <div className="flex items-center space-x-2 text-zinc-100">
              <div className="flex h-6 w-6 items-center justify-center rounded border border-cyber-amber bg-cyber-surface">
                <svg
                  className="h-3.5 w-3.5 text-cyber-amber-bright"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2" />
                </svg>
              </div>
              <span className="font-extrabold text-sm tracking-tight text-white">
                Idle<span className="text-cyber-amber-bright">Scale</span> Cloud
              </span>
            </div>
            <p className="text-xs leading-relaxed text-zinc-400 font-normal">
              Platform komputasi terdistribusi generasi baru. Memanfaatkan kapasitas idle perangkat komputer global dengan isolasi kontainer Docker yang aman dan verifikasi reputasi node.
            </p>
          </div>

          <div>
            <h4 className="mb-3 text-xs font-bold uppercase tracking-wider text-zinc-200">
              Spesifikasi Jaringan
            </h4>
            <ul className="space-y-1.5 text-xs text-zinc-400 font-mono">
              <li>Arsitektur: <span className="text-zinc-200">Pull Model / Replicated Lease</span></li>
              <li>Konsensus: <span className="text-cyber-amber-bright">Quorum 2 of 4</span></li>
              <li>Isolasi: <span className="text-emerald-400">Cap-drop ALL / Read-Only</span></li>
              <li>Enkripsi: <span className="text-zinc-200">TLS 1.3 / Bearer Tokens</span></li>
            </ul>
          </div>

          <div>
            <h4 className="mb-3 text-xs font-bold uppercase tracking-wider text-zinc-200">
              Perintah CLI
            </h4>
            <ul className="space-y-1.5 text-xs font-mono">
              <li><code className="text-cyber-amber-light hover:underline">./hpc.sh head-up</code></li>
              <li><code className="text-cyber-amber-light hover:underline">./hpc.sh worker-login</code></li>
              <li><code className="text-cyber-amber-light hover:underline">./hpc.sh worker-up 2</code></li>
              <li><code className="text-cyber-amber-light hover:underline">./hpc.sh stats</code></li>
            </ul>
          </div>

          <div>
            <h4 className="mb-3 text-xs font-bold uppercase tracking-wider text-zinc-200">
              Navigasi Cepat
            </h4>
            <div className="flex flex-col space-y-1.5 text-xs">
              <Link href="/" className="hover:text-cyber-amber-bright transition-colors">&rarr; Overview</Link>
              <Link href="/join" className="hover:text-cyber-amber-bright transition-colors">&rarr; Panduan Relawan</Link>
              <Link href="/appreciation" className="hover:text-cyber-amber-bright transition-colors">&rarr; Papan Apresiasi</Link>
              <Link href="/register" className="hover:text-cyber-amber-bright transition-colors">&rarr; Daftar Node Relawan</Link>
              <Link href="/login" className="hover:text-cyber-amber-bright transition-colors">&rarr; Masuk Akun</Link>
              <Link href="/dashboard" className="hover:text-cyber-amber-bright transition-colors">&rarr; Command Center</Link>
            </div>
          </div>
        </div>

        <div className="mt-10 flex flex-col items-center justify-between border-t border-cyber-border/70 pt-6 sm:flex-row text-xs text-zinc-500">
          <p>
            &copy; 2026 IdleScale Network. Distributed Volunteer Supercomputing Grid.
          </p>
          <div className="mt-3 flex items-center space-x-2 sm:mt-0">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span className="text-emerald-400 font-mono text-[11px]">ALL SYSTEMS OPERATIONAL</span>
          </div>
        </div>
      </div>
    </footer>
  );
}

