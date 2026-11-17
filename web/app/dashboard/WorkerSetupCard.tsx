"use client";
import React, { useEffect, useState } from "react";
import TerminalCode from "@/components/TerminalCode";

/**
 * Cara menjalankan compute node + token worker untuk CLI.
 *
 * Worker dijalankan dari REPO WORKER (repo B, yang juga dikerjakan relawan lewat jobdesk), bukan
 * dari repo platform. Repo worker punya ./hpc.sh sendiri: setup / up / logs / status / down.
 * Token worker (hpc_w_...) hanya untuk CLI; website memakai email + password.
 */
type Project = { repo_url: string | null; coordinator_url: string | null };

export default function WorkerSetupCard({ online, notify }: { online: boolean; notify: (msg: string, tone?: "ok" | "err") => void }) {
  const [project, setProject] = useState<Project | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [showToken, setShowToken] = useState(false);
  const [confirmRotate, setConfirmRotate] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch("/api/project", { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => setProject(d.project || null))
      .catch(() => setProject(null));
  }, []);

  const loadToken = async () => {
    const r = await fetch("/api/volunteer/cli-token", { cache: "no-store" });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) {
      notify(d.detail || "Token tidak bisa diambil.", "err");
      return null;
    }
    setToken(d.worker_token);
    return d.worker_token as string | null;
  };

  const reveal = async () => {
    if (!showToken && !token) await loadToken();
    setShowToken(!showToken);
  };

  const copySetup = async () => {
    const t = token || (await loadToken());
    if (!t) return;
    await navigator.clipboard.writeText(`./hpc.sh setup ${project?.coordinator_url || "<COORDINATOR_URL>"} ${t}`);
    notify("Perintah setup (berisi token Anda) disalin. Tempel di terminal folder repo worker.");
  };

  const rotate = async () => {
    setBusy(true);
    const r = await fetch("/api/volunteer/cli-token", { method: "POST" });
    const d = await r.json().catch(() => ({}));
    setBusy(false);
    setConfirmRotate(false);
    if (!r.ok) {
      notify(d.detail || "Gagal membuat token baru.", "err");
      return;
    }
    setToken(d.worker_token);
    setShowToken(true);
    notify("Token baru dibuat. Jalankan lagi './hpc.sh setup' dengan token baru, lalu './hpc.sh up'.");
  };

  const repo = (project?.repo_url || "https://github.com/ChanceClover/hpc-cloudservice-worker").replace(/\/$/, "");
  const dir = repo.split("/").pop();
  const coord = project?.coordinator_url || "<COORDINATOR_URL>";
  const masked = token ? `${token.slice(0, 10)}${"•".repeat(16)}` : "hpc_w_••••••••••••••••";

  const steps = [
    "# 1. Clone repo worker (sekali saja), di Ubuntu WSL2",
    `git clone ${repo}.git ~/${dir}`,
    `cd ~/${dir} && chmod +x hpc.sh`,
    "",
    "# 2. Simpan alamat koordinator + token worker Anda ke .env",
    `./hpc.sh setup ${coord} ${showToken && token ? token : "<TOKEN_WORKER>"}`,
    "",
    "# 3. Nyalakan worker (Docker Desktop harus menyala), lalu pantau",
    "./hpc.sh up",
    "./hpc.sh logs",
    "",
    "# Lainnya: ./hpc.sh status | ./hpc.sh down | ./hpc.sh update",
  ].join("\n");

  return (
    <div className="cyber-box p-6 lg:col-span-2 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs font-bold text-cyber-amber-bright uppercase tracking-wider font-mono">
          Jalankan Worker Anda (Compute Node)
        </div>
        <span className={`rounded px-2 py-0.5 text-[10px] font-bold ${online ? "bg-emerald-950/60 text-emerald-300" : "bg-cyber-black text-zinc-400"}`}>
          {online ? "● WORKER ONLINE" : "○ WORKER OFFLINE"}
        </span>
      </div>
      <p className="text-[11px] text-zinc-400">
        Worker berjalan dari <strong className="text-zinc-200">repo worker</strong> ({repo.replace("https://github.com/", "")}),
        repo yang sama dengan tempat Anda mengerjakan jobdesk. Perintah <code>./hpc.sh</code> di bawah dijalankan di
        folder repo itu. Kredit hanya bertambah bila hasil worker Anda sama dengan worker lain (replikasi + quorum).
      </p>
      {!project?.coordinator_url && (
        <p className="rounded border border-cyber-amber-deep bg-cyber-amber-darkest/40 p-2 text-[11px] text-cyber-amber-bright">
          Alamat koordinator belum diumumkan admin (<code>./hpc.sh head-online</code>). Minta alamat HTTPS-nya ke admin, atau
          pakai <code>http://host.docker.internal:8000</code> bila worker satu laptop dengan head node.
        </p>
      )}

      <TerminalCode title="Terminal • Ubuntu WSL2 • folder repo worker" code={steps} />

      {/* Token worker untuk CLI */}
      <div className="rounded border border-cyber-border bg-cyber-black/60 p-3 space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-[10px] uppercase text-zinc-400">Token Worker untuk CLI (rahasia)</span>
          <span className="text-[10px] text-zinc-500">Website memakai email + password, bukan token ini.</span>
        </div>
        <div className="overflow-x-auto rounded bg-cyber-surface p-2 font-mono text-[11px] text-cyber-amber-bright select-all">
          {showToken && token ? token : masked}
        </div>
        <div className="flex flex-wrap gap-2 text-[11px]">
          <button onClick={reveal} className="rounded border border-cyber-border px-3 py-1 text-zinc-300 hover:border-cyber-amber hover:text-cyber-amber-bright">
            {showToken ? "SEMBUNYIKAN" : "TAMPILKAN"}
          </button>
          <button onClick={copySetup} className="rounded border border-cyber-amber bg-cyber-amber px-3 py-1 font-bold text-cyber-void hover:bg-cyber-amber-bright">
            SALIN PERINTAH SETUP
          </button>
          {!confirmRotate ? (
            <button onClick={() => setConfirmRotate(true)} className="rounded border border-cyber-border px-3 py-1 text-zinc-400 hover:border-red-500 hover:text-red-400">
              BUAT TOKEN BARU
            </button>
          ) : (
            <span className="flex flex-wrap items-center gap-2 rounded border border-red-500/50 bg-red-950/30 px-2 py-1 text-red-200">
              Token lama langsung tidak berlaku dan worker yang memakainya berhenti. Lanjut?
              <button disabled={busy} onClick={rotate} className="rounded bg-red-600 px-2 py-0.5 font-bold text-white disabled:opacity-50">
                {busy ? "..." : "YA, BUAT BARU"}
              </button>
              <button onClick={() => setConfirmRotate(false)} className="text-zinc-300 underline">batal</button>
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
