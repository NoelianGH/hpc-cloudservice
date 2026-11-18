"use client";
/**
 * Peran relawan sebagai DEVELOPER: tombol AMBIL JOBDESK (jobdesk tertua di antrean, FIFO),
 * akses COMPUTE NODE untuk jobdesk itu (perintah ssh + TOKEN NODE, login dari command prompt),
 * status CI terdistribusi setiap push, dan tombol ajukan review (sistem membuka Pull Request).
 * Setelah admin menyetujui, akses compute node berakhir; login website tetap.
 */
import React, { useCallback, useEffect, useState } from "react";
import { CiBadge } from "../admin/ProjectTabs";
import TerminalCode from "@/components/TerminalCode";

type NodeAccess = {
  username: string; token: string; node: string | null; ready: boolean; node_online: boolean;
  sessions: number; last_login_at: string | null; ssh_command: string; ssh_online_command: string | null;
  expires_at: string | null; parked?: boolean; parked_at?: string | null; last_node?: string | null;
  idle_minutes?: number;
};

type Jobdesk = {
  id: number; title: string; description: string; kind: string; credit: number; status: string; branch: string | null;
  note: string | null; last_sha: string | null; last_ci_job: number | null; last_ci_status: string | null;
  assigned_at: string | null; done_at: string | null; pr_number: number | null; pr_url: string | null;
  merged_sha: string | null; git?: string[]; node?: NodeAccess | null;
  node_revoked?: { reason: string; at: string; expired: boolean } | null;
};
type CiRun = {
  job_id: number; branch: string; sha: string; status: string; step: string; shards: number; shards_done: number;
  nodes: number; wall_s: number | null; tests_total: number | null; tests_failed: number | null;
  shards_failed: string[] | null; build_error: string | null; created_at: string;
};
type Data = {
  project: {
    enabled: boolean; repo_url: string | null; app_name: string; require_ci_pass: boolean; max_active: number;
    auto_assign?: boolean; node_access?: boolean; github_token?: boolean;
  };
  active: Jobdesk[]; history: Jobdesk[]; queue_open: number; online: boolean; ci: CiRun[];
  node_capacity?: { nodes: number; total: number; used: number; free: number } | null;
};

const STATUS_LABEL: Record<string, string> = {
  in_progress: "SEDANG DIKERJAKAN", review: "MENUNGGU REVIEW ADMIN", done: "SELESAI", open: "DIKEMBALIKAN", cancelled: "DIBATALKAN",
};
const btn = "rounded border px-3 py-1.5 text-[11px] font-bold transition-colors disabled:opacity-40";

export default function JobdeskCard() {
  const [d, setD] = useState<Data | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [showCode, setShowCode] = useState(false);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    const r = await fetch("/api/volunteer/jobdesk", { cache: "no-store" });
    if (r.ok) setD(await r.json());
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  const post = async (path: string, ok: string) => {
    setBusy(true);
    setMsg(null);
    const r = await fetch(`/api/volunteer/jobdesk/${path}`, { method: "POST" });
    const body = await r.json().catch(() => ({}));
    setBusy(false);
    if (!r.ok) {
      setMsg({ ok: false, text: typeof body.detail === "string" ? body.detail : `Error ${r.status}` });
      return;
    }
    const pr = body.pull_request;
    setMsg({ ok: true, text: pr?.url ? `${ok} Pull Request: ${pr.url}` : ok });
    await load();
  };

  const copyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!d) return null;
  const repo = d.project.repo_url;

  return (
    <section className="cyber-box p-4 sm:p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-cyber-border pb-2">
        <h2 className="text-xs font-bold text-cyber-amber-bright uppercase tracking-wider">Jobdesk Pengembang Saya</h2>
        {repo && (
          <a href={repo} target="_blank" rel="noreferrer" className="text-[11px] text-zinc-400 underline">
            {d.project.app_name} &bull; {repo.replace("https://github.com/", "")}
          </a>
        )}
      </div>

      {!d.project.enabled && (
        <p className="text-xs text-zinc-400">Admin belum menghubungkan repo proyek. Sementara ini Anda tetap bisa menyumbang komputasi (di bawah).</p>
      )}

      {msg && (
        <div className={`mb-3 rounded border p-2 text-[11px] ${msg.ok ? "border-emerald-700/60 bg-emerald-950/40 text-emerald-300" : "border-red-500/50 bg-red-950/40 text-red-300"}`}>
          {msg.text}
        </div>
      )}

      {d.active.map((j) => (
        <div key={j.id} className="mb-4 rounded border border-cyber-border bg-black/30 p-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <span className="text-[10px] font-bold text-cyber-amber-bright">{STATUS_LABEL[j.status]}</span>
              <h3 className="text-base font-bold text-white">
                <span className="text-zinc-500">#{j.id}</span> {j.title}{" "}
                <span className="text-[10px] uppercase text-zinc-400">({j.kind}, {j.credit} kredit)</span>
              </h3>
              {j.description && <p className="mt-1 whitespace-pre-line text-[11px] text-zinc-400">{j.description}</p>}
              {j.note && <p className="mt-1 text-[11px] text-cyber-amber-bright">Catatan admin: {j.note}</p>}
            </div>
            <div className="text-right text-[11px]">
              <CiBadge status={j.last_ci_status} />
              {j.last_sha && repo && (
                <div className="mt-1">
                  <a href={`${repo}/commit/${j.last_sha}`} target="_blank" rel="noreferrer" className="text-zinc-500 underline">commit {j.last_sha.slice(0, 7)}</a>
                </div>
              )}
            </div>
          </div>

          {j.node && <NodeBox n={j.node} showCode={showCode} setShowCode={setShowCode} copied={copied} onCopy={copyCode}
            onRotate={() => post(`${j.id}/node-code`, "Token node baru dibuat. Sesi SSH yang sedang jalan tidak terputus; git di node memakai token baru.")}
            onResume={() => post(`${j.id}/node-resume`, "Compute node siap untuk Anda. Login lagi dengan perintah ssh di bawah dan token yang sama.")} busy={busy} />}
          {!j.node && j.node_revoked && d.project.node_access && (
            <p className="mt-3 rounded border border-cyber-amber-deep bg-cyber-amber-darkest/40 p-2 text-[11px] text-cyber-amber-bright">
              {j.node_revoked.expired
                ? "Token node jobdesk ini sudah kedaluwarsa, jadi akses compute node dicabut. "
                : `Akses compute node dicabut (${j.node_revoked.reason}). `}
              Pekerjaan yang sudah di-push tetap aman di branch {j.branch}. Minta admin menerbitkan token node baru
              (BERI AKSES NODE) bila Anda masih melanjutkan jobdesk ini.
            </p>
          )}

          {j.status === "in_progress" && j.git && (
            <div className="mt-3">
              <p className="mb-1 text-[10px] uppercase text-zinc-500">
                {j.node ? "Setelah login ke compute node" : "Kerjakan di branch"} <span className="text-white">{j.node ? `(branch ${j.branch})` : j.branch}</span>
                {j.node ? ":" : " (VS Code / terminal):"}
              </p>
              <pre className="overflow-x-auto rounded bg-black/60 p-2 text-[11px] leading-5 text-emerald-300">{j.git.join("\n")}</pre>
              <p className="mt-1 text-[10px] text-zinc-500">
                Setiap push otomatis di-build dan dites terdistribusi di compute node relawan. Hasilnya muncul di sini dan sebagai
                centang di GitHub.{d.project.require_ci_pass ? " Jobdesk hanya bisa diajukan bila CI commit terakhir LULUS." : ""}
              </p>
            </div>
          )}

          {j.status === "in_progress" && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button disabled={busy} onClick={() => post(`${j.id}/submit`, "Jobdesk diajukan. Admin akan meninjau kode Anda.")} className={`${btn} border-emerald-700 bg-emerald-950/60 text-emerald-300 hover:bg-emerald-900/60`}>
                AJUKAN REVIEW
              </button>
              <span className="text-[10px] text-zinc-500">
                Sistem membuka Pull Request ke main; admin menyetujui = PR di-merge
                {j.node ? " dan akses compute node berakhir (login website tetap)" : ""}. Bisa juga dari node: <code>jobdesk ajukan</code>.
              </span>
            </div>
          )}
          {j.pr_url && (
            <a href={j.pr_url} target="_blank" rel="noreferrer" className="mt-2 block text-[11px] text-sky-300 underline">
              Pull Request #{j.pr_number}
            </a>
          )}
        </div>
      ))}

      {d.project.enabled && !d.project.auto_assign && d.active.length < (d.project.max_active || 1) && (
        <div className="mb-3 rounded border border-cyber-border bg-black/30 p-3">
          <div className="flex flex-wrap items-center gap-3">
            <button disabled={busy || d.queue_open === 0 || (!!d.node_capacity && d.node_capacity.free <= 0)} onClick={() => post("take", "Jobdesk didapat. Akses compute node sedang disiapkan (beberapa detik).")}
              className={`${btn} border-cyber-amber bg-cyber-amber/20 px-4 py-2 text-cyber-amber-bright hover:bg-cyber-amber/30`}>
              AMBIL JOBDESK
            </button>
            <span className="text-[11px] text-zinc-400">
              {d.queue_open > 0
                ? `${d.queue_open} jobdesk di antrean. Anda mendapat yang paling lama menunggu (FIFO), tidak bisa memilih.`
                : "Antrean jobdesk kosong. Tunggu admin menambahkan jobdesk."}
            </span>
          </div>
          {d.node_capacity && (
            <p className={`mt-2 text-[10px] ${d.node_capacity.free > 0 ? "text-zinc-500" : "text-cyber-amber-bright"}`}>
              Slot compute node: {d.node_capacity.free} kosong dari {d.node_capacity.total} ({d.node_capacity.nodes} node online).
              {d.node_capacity.free <= 0 && " Semua penuh: jobdesk tetap di antrean. Node dilepas otomatis saat relawan tidak aktif, jadi coba lagi beberapa menit lagi."}
            </p>
          )}
          {d.project.node_access && (
            <p className="mt-2 text-[10px] text-zinc-500">
              Setiap jobdesk mendapat akses compute node sendiri: login dari command prompt PC Anda dengan <code>ssh</code>,
              repo proyek sudah siap di sana, dan hanya branch jobdesk Anda yang bisa di-push.
            </p>
          )}
        </div>
      )}

      {d.project.enabled && d.project.auto_assign && (
        <div className="space-y-1 text-[11px] text-zinc-400">
          {!d.online && (
            <p className="rounded border border-cyber-amber-deep bg-cyber-amber-darkest/40 p-2 text-cyber-amber-bright">
              Worker CPU Anda OFFLINE (<code>./hpc.sh up</code> di folder repo worker).{" "}
              {d.active.length
                ? "Jobdesk Anda tetap milik Anda; tugas komputasi yang sedang dikerjakan node Anda otomatis dipindah ke compute node lain."
                : "Jobdesk baru hanya di-assign ke relawan yang compute node-nya online."}
            </p>
          )}
          {d.active.length === 0 && (
            <p>
              {d.queue_open > 0
                ? d.online
                  ? "Menunggu giliran: jobdesk berikutnya di antrean akan di-assign otomatis ke Anda (FIFO)."
                  : "Ada jobdesk di antrean. Nyalakan compute node Anda untuk mendapat jobdesk otomatis."
                : "Antrean jobdesk kosong. Anda akan mendapat jobdesk otomatis begitu admin menambahkannya."}
            </p>
          )}
          <p className="text-[10px] text-zinc-600">Antrean jobdesk: {d.queue_open} &bull; jobdesk di-assign oleh sistem, bukan dipilih.</p>
        </div>
      )}

      {d.ci.length > 0 && (
        <div className="mt-4">
          <p className="mb-1 text-[10px] uppercase text-zinc-500">CI branch saya</p>
          <table className="w-full text-[11px]">
            <tbody>
              {d.ci.slice(0, 5).map((r) => (
                <tr key={r.job_id} className="border-t border-cyber-border/40">
                  <td className="py-1.5 pr-2 text-zinc-300">{r.sha.slice(0, 7)}</td>
                  <td className="py-1.5 pr-2"><CiBadge status={r.status} /></td>
                  <td className="py-1.5 pr-2 text-zinc-400">
                    {r.status === "running"
                      ? `${r.step}${r.shards ? ` ${r.shards_done}/${r.shards} file test` : ""}, ${r.nodes} node`
                      : r.build_error || (r.shards_failed?.length ? `gagal: ${r.shards_failed.join(", ")}` : `${r.tests_total ?? 0} test, ${r.nodes} node, ${r.wall_s} s`)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {d.history.length > 0 && (
        <p className="mt-3 text-[10px] text-zinc-500">
          Riwayat: {d.history.map((h) => `#${h.id} ${h.title} (${STATUS_LABEL[h.status] || h.status})`).join(" • ")}
        </p>
      )}
    </section>
  );
}

function NodeBox({ n, showCode, setShowCode, copied, onCopy, onRotate, onResume, busy }: {
  n: NodeAccess; showCode: boolean; setShowCode: (v: boolean) => void; copied: boolean;
  onCopy: (code: string) => void; onRotate: () => void; onResume: () => void; busy: boolean;
}) {
  const state = n.parked
    ? { text: "NODE DILEPAS (TIDAK AKTIF)", cls: "text-cyber-amber-bright" }
    : !n.node
    ? { text: "MENUNGGU COMPUTE NODE", cls: "text-cyber-amber-bright" }
    : !n.node_online
      ? { text: `COMPUTE NODE ${n.node} OFFLINE`, cls: "text-red-400" }
      : !n.ready
        ? { text: `MENYIAPKAN DI ${n.node}...`, cls: "text-sky-300" }
        : { text: `SIAP DI ${n.node}`, cls: "text-emerald-400" };
  return (
    <div className="mt-3 rounded border border-cyber-border bg-black/40 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[10px] uppercase text-zinc-500">
          Akses compute node &bull; <span className={`font-bold ${state.cls}`}>{state.text}</span>
          {n.sessions > 0 && <span className="text-emerald-400"> &bull; {n.sessions} sesi sedang login</span>}
        </p>
        <span className="text-[10px] text-zinc-500">user <span className="text-white">{n.username}</span></span>
      </div>
      {n.parked ? (
        <div className="my-3 rounded border border-cyber-amber-deep bg-cyber-amber-darkest/40 p-3 text-[11px] text-cyber-amber-bright">
          <p>
            Sesi Anda diputus karena tidak ada aktivitas selama {n.idle_minutes || 30} menit, dan compute node
            {n.last_node ? ` ${n.last_node}` : ""} dilepas untuk relawan lain. Jobdesk tetap milik Anda, token node tidak
            berubah, dan folder kerja Anda (termasuk yang belum di-push) tetap ada.
          </p>
          <button disabled={busy} onClick={onResume}
            className={`${btn} mt-2 border-cyber-amber bg-cyber-amber/20 text-cyber-amber-bright hover:bg-cyber-amber/30`}>
            MASUK LAGI KE NODE
          </button>
          <span className="ml-2 text-[10px] text-zinc-400">Bila semua node sedang dipakai, coba lagi beberapa menit lagi.</span>
        </div>
      ) : (
        <TerminalCode title="Command Prompt / Terminal di PC Anda (jaringan yang sama dengan head)" code={n.ssh_command} />
      )}
      {!n.parked && n.ssh_online_command && (
        <TerminalCode title="Dari jaringan lain (sekali pasang: winget install Cloudflare.cloudflared)" code={n.ssh_online_command} />
      )}
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className="text-zinc-400">Token node (password ssh, juga dipakai git di node):</span>
        <code className="rounded bg-black/60 px-2 py-1 text-amber-200">{showCode ? n.token : "hpc_ng_••••-••••-••••-••••-••••"}</code>
        <button onClick={() => setShowCode(!showCode)} className={`${btn} border-cyber-border text-zinc-300 hover:border-cyber-amber`}>
          {showCode ? "SEMBUNYIKAN" : "TAMPILKAN"}
        </button>
        <button onClick={() => onCopy(n.token)} className={`${btn} border-cyber-border text-zinc-300 hover:border-cyber-amber`}>
          {copied ? "TERSALIN ✓" : "SALIN"}
        </button>
        <button disabled={busy} onClick={onRotate} className={`${btn} border-cyber-border text-zinc-400 hover:border-cyber-amber`}>
          GANTI TOKEN
        </button>
      </div>
      {n.expires_at && (
        <p className="mt-2 text-[10px] text-zinc-400">
          Token berlaku sampai <span className="text-white">{new Date(n.expires_at).toLocaleString("id-ID")}</span>
          {" "}(atau sampai jobdesk disetujui). Setelah itu akses dicabut; minta admin menerbitkan ulang bila belum selesai.
        </p>
      )}
      <p className="mt-2 text-[10px] text-zinc-500">
        Saat mengetik password di ssh, karakternya memang tidak tampil. Satu compute node dipakai satu relawan; di node, perintah{" "}
        <code>uji</code> menjalankan kontainer untuk testing (mis. aplikasi + database).
        {n.idle_minutes ? ` Tidak aktif ${n.idle_minutes} menit = sesi diputus dan node dilepas (jobdesk, token, dan folder tetap).` : ""}
        {" "}Setelah admin menyetujui, sesi SSH diputus dan user {n.username} dihapus. Ambil jobdesk berikutnya di website untuk akses baru.
      </p>
    </div>
  );
}
