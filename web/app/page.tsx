import Link from "next/link";
import TerminalCode from "@/components/TerminalCode";

export default function HomePage() {
  return (
    <div className="relative overflow-hidden py-12 lg:py-20">
      {/* Glow effect behind hero */}
      <div className="pointer-events-none absolute left-1/2 top-0 -translate-x-1/2 h-[450px] w-[800px] rounded-full bg-cyber-amber-deep/15 blur-[120px]" />

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Hero Section */}
        <div className="text-center">
          <div className="inline-flex items-center space-x-2 rounded border border-cyber-amber/40 bg-cyber-surface/90 px-3 py-1 font-mono text-xs text-cyber-amber-bright shadow-amber-glow-sm">
            <span className="h-1.5 w-1.5 rounded-full bg-cyber-amber-bright animate-ping"></span>
            <span>VOLUNTEER HIGH-PERFORMANCE COMPUTING PLATFORM</span>
          </div>

          <h1 className="mt-6 font-mono text-3xl font-extrabold tracking-tight text-white sm:text-5xl lg:text-6xl">
            HARNESS DISTRIBUTED <br />
            <span className="bg-gradient-to-r from-amber-400 via-amber-500 to-yellow-600 bg-clip-text text-transparent glow-text-amber">
              SUPERCOMPUTING POWER
            </span>
          </h1>

          <p className="mx-auto mt-6 max-w-2xl font-mono text-sm text-zinc-400 sm:text-base leading-relaxed">
            Contribute CPU idle power to scientific computing via lightweight sandboxed Docker containers.
            Protected by real-time GitHub anti-fake worker validation, multi-replica quorum verification, and automated cryptographic lease management.
          </p>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-4 font-mono text-xs">
            <Link
              href="/register"
              className="flex items-center space-x-2 rounded border border-cyber-amber-light bg-cyber-amber px-6 py-3 font-semibold text-cyber-void shadow-amber-glow transition-all hover:bg-cyber-amber-bright hover:scale-105"
            >
              <span>REGISTER WORKER NODE</span>
              <span>&gt;</span>
            </Link>

            <Link
              href="/dashboard"
              className="flex items-center space-x-2 rounded border border-cyber-border bg-cyber-surface px-6 py-3 text-zinc-300 transition-all hover:border-cyber-amber hover:text-cyber-amber-bright hover:shadow-amber-glow-sm"
            >
              <span>ACCESS COMMAND CENTER</span>
            </Link>
          </div>
        </div>

        {/* 3 Pillars / Feature Grid */}
        <div className="mt-16 grid grid-cols-1 gap-6 sm:grid-cols-3">
          {/* Card 1: Anti-Fake Worker Gate */}
          <div className="cyber-box p-6 transition-all hover:border-cyber-amber/60 hover:shadow-amber-glow-sm">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-cyber-amber-bright">01 // SECURITY</span>
              <span className="font-mono text-[10px] text-zinc-500">[AUTH GATE]</span>
            </div>
            <h3 className="mt-3 font-mono text-base font-bold text-gray-100">
              GitHub Anti-Fake Worker
            </h3>
            <p className="mt-2 font-mono text-xs text-zinc-400 leading-relaxed">
              Every worker is analyzed using GitHub reputation factors: account age (min. 30 days), public repository count, followers, and profile completeness to prevent Sybil bot attacks.
            </p>
            <div className="mt-4 border-t border-cyber-border pt-3">
              <span className="font-mono text-[10px] text-emerald-400">
                [✓] OTP Email Authentication Included
              </span>
            </div>
          </div>

          {/* Card 2: Sandboxed Sandbox Compute */}
          <div className="cyber-box p-6 transition-all hover:border-cyber-amber/60 hover:shadow-amber-glow-sm">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-cyber-amber-bright">02 // ISOLATION</span>
              <span className="font-mono text-[10px] text-zinc-500">[SANDBOX]</span>
            </div>
            <h3 className="mt-3 font-mono text-base font-bold text-gray-100">
              Sandboxed Docker Node
            </h3>
            <p className="mt-2 font-mono text-xs text-zinc-400 leading-relaxed">
              Non-root execution, read-only rootfs, `cap_drop: [ALL]`, no host filesystem access, restricted CPU/RAM quotas, and isolated network communication to the coordinator.
            </p>
            <div className="mt-4 border-t border-cyber-border pt-3">
              <span className="font-mono text-[10px] text-emerald-400">
                [✓] Safe for Volunteer Laptops
              </span>
            </div>
          </div>

          {/* Card 3: Replicated Quorum */}
          <div className="cyber-box p-6 transition-all hover:border-cyber-amber/60 hover:shadow-amber-glow-sm">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-cyber-amber-bright">03 // CONSENSUS</span>
              <span className="font-mono text-[10px] text-zinc-500">[VALIDATOR]</span>
            </div>
            <h3 className="mt-3 font-mono text-base font-bold text-gray-100">
              Replicated Quorum (2 of 4)
            </h3>
            <p className="mt-2 font-mono text-xs text-zinc-400 leading-relaxed">
              Tasks are replicated across multiple volunteer nodes. The validator compares computed results with tolerance checks. Cheat attempts are discarded and honest nodes receive credits.
            </p>
            <div className="mt-4 border-t border-cyber-border pt-3">
              <span className="font-mono text-[10px] text-emerald-400">
                [✓] Automatic Poisoning Defense
              </span>
            </div>
          </div>
        </div>

        {/* Quick Start Terminal Snippet */}
        <div className="mt-16 cyber-box p-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-cyber-border pb-4">
            <div>
              <span className="font-mono text-xs text-cyber-amber-bright">// RAPID DEPLOYMENT</span>
              <h2 className="mt-1 font-mono text-lg font-bold text-white">
                Launch Your Compute Worker in 3 Commands
              </h2>
            </div>
            <Link
              href="/register"
              className="mt-3 sm:mt-0 font-mono text-xs text-cyber-amber-bright hover:underline"
            >
              Get Verified Token First &rarr;
            </Link>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div>
              <p className="font-mono text-xs text-zinc-400">
                1. Clone the repository and generate your local credentials:
              </p>
              <TerminalCode
                title="TERMINAL // STEP 1"
                code={`git clone https://github.com/USERNAME/cloud-hpc.git\ncd cloud-hpc\n./hpc.sh`}
              />

              <p className="mt-4 font-mono text-xs text-zinc-400">
                2. Authenticate your worker via CLI (or use the web token):
              </p>
              <TerminalCode
                title="TERMINAL // STEP 2"
                code={`./hpc.sh worker-login`}
              />
            </div>

            <div>
              <p className="font-mono text-xs text-zinc-400">
                3. Spin up compute nodes to start pulling tasks:
              </p>
              <TerminalCode
                title="TERMINAL // STEP 3"
                code={`# Jalankan 2 worker sandbox\n./hpc.sh worker-up 2\n\n# Pantau eksekusi log realtime\n./hpc.sh worker-logs`}
              />

              <div className="mt-4 rounded border border-cyber-amber/30 bg-cyber-amber-darkest/30 p-3 font-mono text-xs text-amber-200">
                <span className="font-bold text-cyber-amber-bright">[INFO]:</span> Every task computation earns compute credits that are tracked on your dashboard.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

