"use client";
import React, { useState, useEffect } from "react";
import Link from "next/link";
import TerminalCode from "@/components/TerminalCode";

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<"overview" | "tasks" | "nodes" | "security">("overview");
  const [tokenVisible, setTokenVisible] = useState(false);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // User state from localStorage
  const [workerInfo, setWorkerInfo] = useState({
    name: "worker-node-primary",
    id: "w-8f2a10b4",
    github: "authorized-developer",
    email: "volunteer@hpc-cloud.local",
    token: "hpc_w_98a7c6b5e4d3c2b1a0f9e8d7c6b5a412",
  });

  useEffect(() => {
    if (typeof window !== "undefined") {
      const storedToken = localStorage.getItem("hpc_worker_token");
      const storedId = localStorage.getItem("hpc_worker_id");
      const storedName = localStorage.getItem("hpc_worker_name");
      const storedGithub = localStorage.getItem("hpc_github_username");
      const storedEmail = localStorage.getItem("hpc_email");

      if (storedToken) {
        setWorkerInfo({
          name: storedName || "volunteer-node",
          id: storedId || "w-active",
          github: storedGithub || "github-user",
          email: storedEmail || "volunteer@hpc.local",
          token: storedToken,
        });
      }
    }

    // Fetch cluster stats
    fetch("/api/stats")
      .then((res) => res.json())
      .then((data) => {
        setStats(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const totalDone = stats?.tasks?.done ?? 42;
  const totalPending = stats?.tasks?.pending ?? 8;
  const credits = 156;

  return (
    <div className="min-h-screen py-8 px-4 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        {/* Top HUD Telemetry Ribbon */}
        <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-cyber-border pb-4 gap-4">
          <div>
            <div className="flex items-center space-x-2">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 animate-ping"></span>
              <span className="font-mono text-xs font-bold uppercase tracking-widest text-cyber-amber-bright">
                // HPC COMMAND CENTER &bull; TELEMETRY ONLINE
              </span>
            </div>
            <h1 className="mt-1 font-mono text-2xl font-extrabold text-white sm:text-3xl">
              VOLUNTEER NODE DASHBOARD
            </h1>
          </div>

          {/* Quick HUD Metrics */}
          <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
            <div className="rounded border border-cyber-border bg-cyber-surface px-3 py-1.5 text-zinc-300">
              COORDINATOR: <span className="text-cyber-amber-bright">127.0.0.1:8000</span>
            </div>
            <div className="rounded border border-cyber-border bg-cyber-surface px-3 py-1.5 text-zinc-300">
              CONSENSUS: <span className="text-emerald-400">QUORUM 2/4</span>
            </div>
            <div className="rounded border border-cyber-border bg-cyber-surface px-3 py-1.5 text-zinc-300">
              STATUS: <span className="text-emerald-400 font-bold">READY TO PULL</span>
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="mt-6 flex space-x-2 border-b border-cyber-border font-mono text-xs">
          {[
            { key: "overview", label: "NODE TELEMETRY & TASKS" },
            { key: "tasks", label: "ACTIVE JOB QUEUE" },
            { key: "nodes", label: "CLUSTER NODES MESH" },
            { key: "security", label: "TOKEN & CREDENTIALS" },
          ].map((t) => (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key as any)}
              className={`border-b-2 px-4 py-2.5 font-bold transition-all ${
                activeTab === t.key
                  ? "border-cyber-amber text-cyber-amber-bright bg-cyber-surface/50 shadow-amber-glow-sm"
                  : "border-transparent text-zinc-400 hover:text-white"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* =================================================================== */}
        {/* TAB 1: OVERVIEW & TELEMETRY */}
        {/* =================================================================== */}
        {activeTab === "overview" && (
          <div className="mt-6 space-y-6">
            {/* Top Stat Cards */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 font-mono">
              <div className="cyber-box p-4 border-l-2 border-l-cyber-amber">
                <span className="text-[10px] text-zinc-400">NODE STATUS</span>
                <div className="mt-1 flex items-center justify-between">
                  <span className="text-xl font-bold text-emerald-400">ACTIVE // AUTH</span>
                  <span className="text-xs text-cyber-amber-bright">[ONLINE]</span>
                </div>
                <p className="mt-2 text-[10px] text-zinc-500">Node ID: {workerInfo.id}</p>
              </div>

              <div className="cyber-box p-4 border-l-2 border-l-cyber-amber">
                <span className="text-[10px] text-zinc-400">TASKS EXECUTED (DONE)</span>
                <div className="mt-1 flex items-center justify-between">
                  <span className="text-2xl font-bold text-white">{totalDone}</span>
                  <span className="text-xs text-emerald-400 font-bold">+100%</span>
                </div>
                <p className="mt-2 text-[10px] text-zinc-500">Pending in queue: {totalPending}</p>
              </div>

              <div className="cyber-box p-4 border-l-2 border-l-cyber-amber">
                <span className="text-[10px] text-zinc-400">VOLUNTEER CREDITS</span>
                <div className="mt-1 flex items-center justify-between">
                  <span className="text-2xl font-bold text-cyber-amber-bright">{credits}</span>
                  <span className="text-xs text-cyber-amber-light">PTS</span>
                </div>
                <p className="mt-2 text-[10px] text-zinc-500">Quorum validated calculations</p>
              </div>

              <div className="cyber-box p-4 border-l-2 border-l-cyber-amber">
                <span className="text-[10px] text-zinc-400">LEASE DURATION</span>
                <div className="mt-1 flex items-center justify-between">
                  <span className="text-2xl font-bold text-white">30s</span>
                  <span className="text-xs text-emerald-400">AUTO-BEAT</span>
                </div>
                <p className="mt-2 text-[10px] text-zinc-500">Failover threshold: ~30 seconds</p>
              </div>
            </div>

            {/* Middle Section: Node Credentials & Quick Runner */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              {/* Left Column: Authorized Worker Identity */}
              <div className="cyber-box p-6 lg:col-span-1 space-y-4">
                <div className="flex items-center justify-between border-b border-cyber-border pb-3">
                  <span className="font-mono text-xs font-bold text-cyber-amber-bright">
                    // AUTHORIZED CREDENTIALS
                  </span>
                  <span className="rounded bg-emerald-950 px-2 py-0.5 font-mono text-[10px] text-emerald-400 border border-emerald-800">
                    VERIFIED
                  </span>
                </div>

                <div className="space-y-3 font-mono text-xs">
                  <div>
                    <span className="text-zinc-500 block text-[10px]">GITHUB REPUTATION IDENTIFIER:</span>
                    <span className="text-white font-bold">@{workerInfo.github}</span>
                  </div>

                  <div>
                    <span className="text-zinc-500 block text-[10px]">WORKER NODE ID:</span>
                    <span className="text-cyber-amber-bright">{workerInfo.id}</span>
                  </div>

                  <div>
                    <span className="text-zinc-500 block text-[10px]">REGISTERED EMAIL:</span>
                    <span className="text-zinc-300">{workerInfo.email}</span>
                  </div>

                  <div className="pt-2 border-t border-cyber-border/60">
                    <div className="flex items-center justify-between text-[10px] text-zinc-500 mb-1">
                      <span>WORKER_TOKEN:</span>
                      <button
                        type="button"
                        onClick={() => setTokenVisible(!tokenVisible)}
                        className="text-cyber-amber-bright hover:underline"
                      >
                        {tokenVisible ? "HIDE [x]" : "PEEK [o]"}
                      </button>
                    </div>
                    <div className="rounded bg-cyber-black p-2.5 font-mono text-[11px] text-cyber-amber-bright border border-cyber-amber/30 select-all break-all">
                      {tokenVisible
                        ? workerInfo.token
                        : "••••••••••••••••••••••••••••••••••••••••••••"}
                    </div>
                  </div>
                </div>

                <div className="pt-2">
                  <Link
                    href="/register"
                    className="block text-center rounded border border-cyber-border bg-cyber-surface py-2 font-mono text-xs text-zinc-300 hover:border-cyber-amber hover:text-cyber-amber-bright"
                  >
                    + Register Additional Worker Node
                  </Link>
                </div>
              </div>

              {/* Right Column: Execution Terminal */}
              <div className="cyber-box p-6 lg:col-span-2">
                <div className="flex items-center justify-between border-b border-cyber-border pb-3">
                  <span className="font-mono text-xs font-bold text-cyber-amber-bright">
                    // RUN COMPUTE NODE IN DOCKER
                  </span>
                  <span className="font-mono text-[10px] text-zinc-400">
                    PULL ARCHITECTURE &bull; SANDBOXED
                  </span>
                </div>

                <p className="mt-3 font-mono text-xs text-zinc-400 leading-relaxed">
                  Start your volunteer worker using your authenticated token. Once online, the worker will continuously pull tasks, compute Monte Carlo or Mandelbrot algorithms in isolation, send heartbeats, and submit results for quorum consensus.
                </p>

                <TerminalCode
                  title="START COMPUTE CONTAINER // BASH"
                  code={`# 1. Update konfigurasi .env dengan token Anda\n./hpc.sh worker-status\n\n# 2. Jalankan 1 atau 2 worker relawan\n./hpc.sh worker-up 2\n\n# 3. Pantau log proses dan tugas yang selesai\n./hpc.sh worker-logs`}
                />

                <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3 font-mono text-xs">
                  <div className="rounded border border-cyber-border bg-cyber-black p-3">
                    <span className="text-[10px] text-zinc-500">TASK KINDS AVAILABLE:</span>
                    <ul className="mt-1 space-y-1 text-zinc-300 text-[11px]">
                      <li>&bull; <strong className="text-cyber-amber-light">montecarlo_pi</strong> (30M samples per task)</li>
                      <li>&bull; <strong className="text-cyber-amber-light">mandelbrot</strong> (2000px horizontal strip)</li>
                    </ul>
                  </div>

                  <div className="rounded border border-cyber-border bg-cyber-black p-3">
                    <span className="text-[10px] text-zinc-500">FAULT TOLERANCE & SECURITY:</span>
                    <p className="mt-1 text-zinc-300 text-[11px]">
                      Workers that disconnect mid-task lose lease after 30s. Tasks automatically failover to neighboring nodes.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Task Queue Table Preview */}
            <div className="cyber-box p-6">
              <div className="flex items-center justify-between border-b border-cyber-border pb-3">
                <span className="font-mono text-xs font-bold text-cyber-amber-bright">
                  // RECENT COMPUTE JOBS & CONSENSUS AUDIT
                </span>
                <span className="font-mono text-[10px] text-zinc-500">AUTO-REFRESH: 3000ms</span>
              </div>

              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-left font-mono text-xs text-zinc-300">
                  <thead className="bg-cyber-black text-[10px] text-zinc-400 uppercase tracking-wider border-b border-cyber-border">
                    <tr>
                      <th className="py-2.5 px-3">JOB ID</th>
                      <th className="py-2.5 px-3">ALGORITHM</th>
                      <th className="py-2.5 px-3">TASKS PROGRESS</th>
                      <th className="py-2.5 px-3">DURATION</th>
                      <th className="py-2.5 px-3">RESULT / ACCURACY</th>
                      <th className="py-2.5 px-3">CONSENSUS STATUS</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-cyber-border/60">
                    <tr className="hover:bg-cyber-surface/40 transition-colors">
                      <td className="py-3 px-3 font-bold text-cyber-amber-bright">#108</td>
                      <td className="py-3 px-3 text-white">montecarlo_pi</td>
                      <td className="py-3 px-3">20 / 20 tasks</td>
                      <td className="py-3 px-3">14s</td>
                      <td className="py-3 px-3 text-emerald-400 font-bold">π ≈ 3.1415926</td>
                      <td className="py-3 px-3"><span className="rounded bg-emerald-950 px-2 py-0.5 text-[10px] text-emerald-400 border border-emerald-800">QUORUM MET</span></td>
                    </tr>
                    <tr className="hover:bg-cyber-surface/40 transition-colors">
                      <td className="py-3 px-3 font-bold text-cyber-amber-bright">#107</td>
                      <td className="py-3 px-3 text-white">mandelbrot</td>
                      <td className="py-3 px-3">20 / 20 tasks</td>
                      <td className="py-3 px-3">22s</td>
                      <td className="py-3 px-3 text-zinc-300">500 max_iter render</td>
                      <td className="py-3 px-3"><span className="rounded bg-emerald-950 px-2 py-0.5 text-[10px] text-emerald-400 border border-emerald-800">QUORUM MET</span></td>
                    </tr>
                    <tr className="hover:bg-cyber-surface/40 transition-colors">
                      <td className="py-3 px-3 font-bold text-cyber-amber-bright">#109</td>
                      <td className="py-3 px-3 text-white">montecarlo_pi</td>
                      <td className="py-3 px-3 text-cyber-amber-bright">12 / 20 tasks</td>
                      <td className="py-3 px-3 text-zinc-400">in progress...</td>
                      <td className="py-3 px-3 text-zinc-500">computing samples...</td>
                      <td className="py-3 px-3"><span className="rounded bg-amber-950 px-2 py-0.5 text-[10px] text-amber-300 border border-amber-800">COMPUTING</span></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* =================================================================== */}
        {/* TAB 2: ACTIVE JOBS */}
        {/* =================================================================== */}
        {activeTab === "tasks" && (
          <div className="cyber-box mt-6 p-6">
            <h3 className="font-mono text-sm font-bold text-cyber-amber-bright mb-2">
              // ACTIVE DISTRIBUTED TASK PIPELINE
            </h3>
            <p className="font-mono text-xs text-zinc-400 mb-6">
              Detailed task partitioning, assignment leases, and replica consensus.
            </p>

            <div className="space-y-4 font-mono text-xs">
              <div className="rounded border border-cyber-border bg-cyber-black p-4">
                <div className="flex justify-between items-center text-cyber-amber-light font-bold mb-2">
                  <span>JOB #109: MONTE CARLO PI (30M SAMPLES / TASK)</span>
                  <span className="text-emerald-400">60% COMPLETE</span>
                </div>
                <div className="w-full bg-cyber-surface h-2 rounded overflow-hidden">
                  <div className="bg-cyber-amber h-full w-[60%]"></div>
                </div>
                <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] text-zinc-400">
                  <div>Assigned Workers: <span className="text-white">2 active</span></div>
                  <div>Replica Target: <span className="text-white">2 per task</span></div>
                  <div>Lease Window: <span className="text-white">30 seconds</span></div>
                  <div>Est. Remaining: <span className="text-white">~6 seconds</span></div>
                </div>
              </div>

              <div className="rounded border border-cyber-border bg-cyber-black p-4">
                <div className="flex justify-between items-center text-cyber-amber-light font-bold mb-2">
                  <span>JOB #110: MANDELBROT STRIP ACCUMULATOR</span>
                  <span className="text-amber-400">PENDING WORKERS</span>
                </div>
                <div className="w-full bg-cyber-surface h-2 rounded overflow-hidden">
                  <div className="bg-cyber-amber-deep h-full w-[10%]"></div>
                </div>
                <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] text-zinc-400">
                  <div>Assigned Workers: <span className="text-white">Waiting claim</span></div>
                  <div>Replica Target: <span className="text-white">2 per task</span></div>
                  <div>Total Slices: <span className="text-white">20 horizontal strips</span></div>
                  <div>Status: <span className="text-cyber-amber-bright">Awaiting Nodes</span></div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* =================================================================== */}
        {/* TAB 3: MESH */}
        {/* =================================================================== */}
        {activeTab === "nodes" && (
          <div className="cyber-box mt-6 p-6">
            <h3 className="font-mono text-sm font-bold text-cyber-amber-bright mb-2">
              // CLUSTER NODES MESH TELEMETRY
            </h3>
            <p className="font-mono text-xs text-zinc-400 mb-6">
              Active verified volunteer compute instances currently connected to the coordinator.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 font-mono text-xs">
              <div className="rounded border border-cyber-border bg-cyber-black p-4">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-white font-bold">{workerInfo.name} (YOU)</span>
                  <span className="text-emerald-400 text-[10px] font-bold">[ONLINE]</span>
                </div>
                <p className="text-zinc-500 text-[11px]">ID: {workerInfo.id}</p>
                <p className="text-zinc-400 text-[11px]">GitHub: @{workerInfo.github}</p>
                <div className="mt-3 pt-2 border-t border-cyber-border flex justify-between text-zinc-400 text-[11px]">
                  <span>Status: Active</span>
                  <span className="text-cyber-amber-bright">Credits: {credits}</span>
                </div>
              </div>

              <div className="rounded border border-cyber-border bg-cyber-black p-4">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-white font-bold">worker-curang (CHEAT TEST)</span>
                  <span className="text-red-400 text-[10px] font-bold">[POISON DISCARDED]</span>
                </div>
                <p className="text-zinc-500 text-[11px]">ID: w-cheat01</p>
                <p className="text-zinc-400 text-[11px]">GitHub: @test-cheater</p>
                <div className="mt-3 pt-2 border-t border-cyber-border flex justify-between text-zinc-400 text-[11px]">
                  <span>Consensus: Rejected</span>
                  <span className="text-zinc-500">Credits: 0</span>
                </div>
              </div>

              <div className="rounded border border-cyber-border bg-cyber-black p-4">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-white font-bold">titan-rig-02</span>
                  <span className="text-emerald-400 text-[10px] font-bold">[ONLINE]</span>
                </div>
                <p className="text-zinc-500 text-[11px]">ID: w-rig02a</p>
                <p className="text-zinc-400 text-[11px]">GitHub: @contributor-dev</p>
                <div className="mt-3 pt-2 border-t border-cyber-border flex justify-between text-zinc-400 text-[11px]">
                  <span>Status: Active</span>
                  <span className="text-cyber-amber-bright">Credits: 88</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* =================================================================== */}
        {/* TAB 4: SECURITY & TOKEN */}
        {/* =================================================================== */}
        {activeTab === "security" && (
          <div className="cyber-box mt-6 p-6">
            <h3 className="font-mono text-sm font-bold text-cyber-amber-bright mb-2">
              // CRYPTOGRAPHIC TOKEN & ACCESS SETTINGS
            </h3>
            <p className="font-mono text-xs text-zinc-400 mb-6">
              Manage your individual worker authorization token generated during OTP email verification.
            </p>

            <div className="space-y-4 font-mono text-xs">
              <div className="rounded border border-cyber-border bg-cyber-black p-4">
                <span className="text-zinc-400 block mb-1">CURRENT ACTIVE WORKER TOKEN</span>
                <div className="rounded bg-cyber-surface p-3 text-cyber-amber-bright font-mono text-xs border border-cyber-amber/30 select-all break-all">
                  {workerInfo.token}
                </div>
                <p className="mt-2 text-[10px] text-zinc-500">
                  This token authenticates your compute node to coordinator endpoints: <code>/api/register</code>, <code>/api/tasks/claim</code>, <code>/api/heartbeat</code>, and <code>/api/tasks/submit</code>.
                </p>
              </div>

              <div className="rounded border border-amber-500/30 bg-cyber-amber-darkest/30 p-4 text-amber-200">
                <h4 className="font-bold text-cyber-amber-bright mb-1">[SECURITY NOTICE]</h4>
                <p className="text-[11px]">
                  Never share your worker token publicly. If your token is compromised, you can re-run the verification flow at <code>/register</code> using your verified GitHub account to issue a replacement token.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

