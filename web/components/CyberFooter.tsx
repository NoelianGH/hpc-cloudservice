import React from "react";
import Link from "next/link";

export default function CyberFooter() {
  return (
    <footer className="mt-auto border-t border-cyber-border bg-cyber-void py-8 font-mono text-xs text-zinc-500">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-8 md:grid-cols-4">
          <div className="space-y-3">
            <div className="flex items-center space-x-2 text-zinc-200">
              <span className="h-2 w-2 rounded-full bg-cyber-amber-bright"></span>
              <span className="font-bold tracking-wider text-cyber-amber-light">HPC // CLOUD SERVICE</span>
            </div>
            <p className="text-[11px] leading-relaxed text-zinc-400">
              High-Performance Volunteer Computing powered by sandboxed Docker compute nodes, automated GitHub anti-fake verification, and multi-replica task validation.
            </p>
          </div>

          <div>
            <h4 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-zinc-300">
              // TELEMETRY
            </h4>
            <ul className="space-y-1.5 text-[11px]">
              <li>Protocol: <span className="text-zinc-300">Pull Model / Replicated Lease</span></li>
              <li>Consensus: <span className="text-cyber-amber-bright">Quorum 2 of 4</span></li>
              <li>Sandboxing: <span className="text-emerald-400">Cap-drop ALL / Read-Only</span></li>
              <li>Encryption: <span className="text-zinc-300">TLS 1.3 / Bearer Tokens</span></li>
            </ul>
          </div>

          <div>
            <h4 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-zinc-300">
              // QUICK COMMANDS
            </h4>
            <ul className="space-y-1.5 text-[11px]">
              <li><code className="text-cyber-amber-light">./hpc.sh head-up</code></li>
              <li><code className="text-cyber-amber-light">./hpc.sh worker-login</code></li>
              <li><code className="text-cyber-amber-light">./hpc.sh worker-up 2</code></li>
              <li><code className="text-cyber-amber-light">./hpc.sh stats</code></li>
            </ul>
          </div>

          <div>
            <h4 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-zinc-300">
              // NAVIGATION
            </h4>
            <div className="flex flex-col space-y-1 text-[11px]">
              <Link href="/" className="hover:text-cyber-amber-light">&gt; Overview</Link>
              <Link href="/register" className="hover:text-cyber-amber-light">&gt; Register Worker Node</Link>
              <Link href="/login" className="hover:text-cyber-amber-light">&gt; Sign In</Link>
              <Link href="/dashboard" className="hover:text-cyber-amber-light">&gt; Command Center</Link>
            </div>
          </div>
        </div>

        <div className="mt-8 flex flex-col items-center justify-between border-t border-cyber-border/60 pt-6 sm:flex-row">
          <p className="text-[10px] text-zinc-500">
            [SYS-ID: 0x7F-HPC] CLOUD SERVICE HPC &bull; SECURE VOLUNTEER COMPUTING PLATFORM
          </p>
          <div className="mt-2 flex space-x-4 text-[10px] sm:mt-0">
            <span className="text-emerald-500">&bull; ALL SYSTEMS OPERATIONAL</span>
          </div>
        </div>
      </div>
    </footer>
  );
}

