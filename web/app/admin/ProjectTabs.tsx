"use client";
/**
 * Tab "JOBDESK" dan "CI REPO B" di dashboard admin.
 * - Jobdesk: papan tugas (seperti Jira) untuk proyek perangkat lunak di repo B. Relawan
 *   mengambil jobdesk FIFO dan bekerja di branch sendiri; admin meninjau dan menyetujui.
 * - CI: setiap push ke repo B dibuild + dites terdistribusi di compute node relawan.
 */
import React, { useCallback, useEffect, useState } from "react";

type Project = {
  enabled: boolean; repo_url: string | null; app_name: string; default_branch: string; branch_prefix: string;
  github_token: boolean; webhook: boolean; poll_seconds: number; require_ci_pass: boolean; max_active: number;
  ci_replicas: number; ci_resources: { cpus: number; memory_mb: number; timeout_s: number };
  auto_assign?: boolean; node_access?: boolean;
};
type Jobdesk = {
  id: number; title: string; description: string; kind: string; credit: number; status: string;
  worker_id: string | null; worker_name: string | null; github_username: string | null; branch: string | null;
  note: string | null; last_sha: string | null; last_ci_job: number | null; last_ci_status: string | null;
  pr_number: number | null; pr_url: string | null; merged_sha: string | null; worker_online: boolean;
  created_at: string; assigned_at: string | null; submitted_at: string | null; done_at: string | null; updated_at: string;
  node_user?: string | null; node_name?: string | null; node_sessions?: number | null; node_ready?: boolean | null;
  node_last_login?: string | null; node_expires_at?: string | null; node_last_revoke?: string | null;
};
type NodeRow = {
  name: string; ip: string | null; last_seen: string; max_users: number; online: boolean; users: number; ssh_port: number | null;
};
type NodesData = {
  enabled: boolean; nodes: NodeRow[]; ssh: { host: string; port: number; online_hosts: Record<string, string> };
  capacity: { nodes: number; total: number; used: number; free: number }; git_token: boolean;
};
type JdEvent = { jobdesk_id: number; at: string; actor: string; event: string; detail: string | null };
type CiTask = {
  id: number; stage: number; status: string; file: string | null; workers: string[] | null; a_status: string[] | null;
  passed: boolean | null; tests: number | null; failures: number | null; build_ok: boolean | null; error: string | null;
};
type CiRun = {
  job_id: number; branch: string; sha: string; source: string; jobdesk_id: number | null; status: string; step: string;
  shards: number; shards_done: number; nodes: number; wall_s: number | null; compute_s: number | null;
  speedup_est: number | null; tests_total: number | null; tests_failed: number | null; shards_failed: string[] | null;
  created_at: string; finished_at: string | null; build_error: string | null; tasks?: CiTask[];
};

const th = "px-2 py-2 text-left text-[10px] font-semibold uppercase text-zinc-500";
const td = "px-2 py-2 align-top";
const btn = "rounded border px-2 py-1 text-[10px] font-bold transition-colors disabled:opacity-40";
const input = "w-full rounded border border-cyber-border bg-black/40 px-2 py-1.5 text-xs text-white outline-none focus:border-cyber-amber";

const CI_STYLE: Record<string, string> = {
  passed: "border-emerald-800 bg-emerald-950 text-emerald-400",
  failed: "border-red-800 bg-red-950 text-red-300",
  error: "border-red-800 bg-red-950 text-red-300",
  running: "border-sky-800 bg-sky-950 text-sky-300",
  cancelled: "border-zinc-700 bg-zinc-900 text-zinc-400",
};
const CI_LABEL: Record<string, string> = {
  passed: "LULUS", failed: "GAGAL", error: "ERROR", running: "BERJALAN", cancelled: "DIBATALKAN",
};

export function CiBadge({ status }: { status: string | null }) {
  if (!status) return <span className="text-[10px] text-zinc-600">belum ada push</span>;
  return (
    <span className={`inline-block rounded border px-1.5 py-0.5 text-[10px] font-bold ${CI_STYLE[status] || "border-zinc-700 text-zinc-300"}`}>
      CI {CI_LABEL[status] || status.toUpperCase()}
    </span>
  );
}

function ago(iso: string | null | undefined): string {
  if (!iso) return "-";
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s} dtk lalu`;
  if (s < 3600) return `${Math.floor(s / 60)} mnt lalu`;
  if (s < 86400) return `${Math.floor(s / 3600)} jam lalu`;
  return `${Math.floor(s / 86400)} hari lalu`;
}

function useAdminApi(onUnauthorized: () => void) {
  const call = useCallback(
    async <T,>(path: string, body?: unknown): Promise<T> => {
      const res = await fetch(`/api/admin/${path}`, {
        cache: "no-store",
        ...(body !== undefined
          ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
          : {}),
      });
      if (res.status === 401) {
        onUnauthorized();
        throw new Error("Sesi admin habis.");
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Error ${res.status}`);
      return data as T;
    },
    [onUnauthorized]
  );
  return call;
}

function Panel({ title, right, children }: { title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="cyber-box p-4 sm:p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-cyber-border pb-2">
        <h2 className="text-xs font-bold text-cyber-amber-bright uppercase tracking-wider">{title}</h2>
        {right}
      </div>
      {children}
    </section>
  );
}

function Msg({ error, notice }: { error: string | null; notice: string | null }) {
  return (
    <>
      {error && <div role="alert" className="rounded border border-red-500/50 bg-red-950/40 p-3 text-xs text-red-300">[ERROR]: {error}</div>}
      {notice && <div className="rounded border border-emerald-700/60 bg-emerald-950/40 p-3 text-xs text-emerald-300">{notice}</div>}
    </>
  );
}

export function ProjectBanner({ p }: { p: Project | null }) {
  if (!p) return null;
  if (!p.enabled) {
    return (
      <div className="rounded border border-cyber-amber-deep bg-cyber-amber-darkest/40 p-3 text-xs text-cyber-amber-bright">
        Repo proyek (repo B) belum diatur. Isi <code>PROJECT_REPO_URL</code> di <code>.env</code> head node, lalu{" "}
        <code>./hpc.sh head-up</code>. Contoh isi repo B ada di folder <code>contoh-repo-b/</code>.
      </div>
    );
  }
  const warn: string[] = [];
  if (!p.github_token) warn.push(p.node_access
    ? "PROJECT_GIT_TOKEN kosong: relawan tidak bisa clone/push dari compute node, dan branch, Pull Request, merge, serta centang CI harus manual"
    : "PROJECT_GIT_TOKEN kosong: branch jobdesk, undangan collaborator, Pull Request, merge, dan centang CI di GitHub harus manual");
  if (!p.webhook && !p.poll_seconds) warn.push("webhook dan polling mati: push tidak akan terdeteksi");
  return (
    <div className="rounded border border-cyber-border bg-cyber-surface/60 p-3 text-[11px] text-zinc-300">
      <span className="font-bold text-white">{p.app_name}</span> &bull;{" "}
      <a href={p.repo_url || "#"} target="_blank" rel="noreferrer" className="text-cyber-amber-bright underline">{p.repo_url}</a>{" "}
      &bull; branch jobdesk <code>{p.branch_prefix}&lt;id&gt;-&lt;judul&gt;</code> &bull; deteksi push:{" "}
      {[p.webhook && "webhook", p.poll_seconds > 0 && `polling ${p.poll_seconds}s`].filter(Boolean).join(" + ") || "-"} &bull; CI{" "}
      {p.ci_replicas}x replika, {p.ci_resources.memory_mb} MB, {p.ci_resources.timeout_s} s/tugas
      {warn.map((w) => (
        <div key={w} className="mt-1 text-cyber-amber-bright">! {w}</div>
      ))}
    </div>
  );
}

// =============================================================================
// Tab: Jobdesk (papan tugas)
// =============================================================================
const COLUMNS: { key: string; label: string; hint: string }[] = [
  { key: "open", label: "ANTRE (FIFO)", hint: "relawan menekan AMBIL JOBDESK di website dan mendapat yang paling atas" },
  { key: "in_progress", label: "DIKERJAKAN", hint: "relawan ngoding di branch-nya sampai selesai" },
  { key: "review", label: "REVIEW", hint: "CI lulus, PR dibuka sistem; setujui = merge PR" },
  { key: "done", label: "SELESAI", hint: "PR di-merge, kredit diberikan" },
];

export function JobdeskTab({ onUnauthorized }: { onUnauthorized: () => void }) {
  const call = useAdminApi(onUnauthorized);
  const [rows, setRows] = useState<Jobdesk[]>([]);
  const [events, setEvents] = useState<JdEvent[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [kind, setKind] = useState("fitur");
  const [credit, setCredit] = useState(10);
  const [showDone, setShowDone] = useState(false);
  const [nodes, setNodes] = useState<NodesData | null>(null);

  const load = useCallback(async () => {
    try {
      const d = await call<{ jobdesks: Jobdesk[]; events: JdEvent[]; project: Project }>("jobdesks");
      setRows(d.jobdesks);
      setEvents(d.events);
      setProject(d.project);
      setError(null);
      if (d.project?.node_access) setNodes(await call<NodesData>("nodes"));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [call]);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  const act = async (key: string, path: string, body: unknown, msg: string) => {
    setBusy(key);
    try {
      await call(path, body);
      setNotice(msg);
      setTimeout(() => setNotice(null), 4000);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const create = (e: React.FormEvent) => {
    e.preventDefault();
    act("create", "jobdesks", { title, description: desc, kind, credit }, `Jobdesk "${title}" masuk antrean.`).then(() => {
      setTitle("");
      setDesc("");
    });
  };

  const action = (d: Jobdesk, a: string, label: string, askNote = false) => {
    let note = "";
    if (askNote) {
      const v = window.prompt(`Catatan untuk "${d.title}" (opsional):`, "");
      if (v === null) return;
      note = v;
    }
    act(`${a}-${d.id}`, `jobdesks/${d.id}/action`, { action: a, note }, `Jobdesk #${d.id}: ${label}.`);
  };

  const repo = project?.repo_url;
  const cols = showDone ? [...COLUMNS, { key: "cancelled", label: "DIBATALKAN", hint: "" }] : COLUMNS;

  return (
    <div className="space-y-6">
      <ProjectBanner p={project} />
      <Msg error={error} notice={notice} />

      {nodes?.enabled && (
        <Panel title="COMPUTE NODE RELAWAN (SSH PER JOBDESK)">
          <div className="flex flex-wrap gap-2 text-[11px]">
            {nodes.nodes.map((n) => (
              <span key={n.name} className="rounded border border-cyber-border bg-black/30 px-2 py-1">
                <span className={n.online ? "text-emerald-400" : "text-red-400"}>●</span>{" "}
                <span className="font-bold text-white">{n.name}</span>{" "}
                <span className="text-zinc-400">
                  {n.online ? "online" : `offline ${ago(n.last_seen)}`} &bull; {n.users}/{n.max_users} relawan &bull; port {n.ssh_port ?? nodes.ssh.port}
                  {nodes.ssh.online_hosts[n.name] ? " • internet" : ""}
                </span>
              </span>
            ))}
            {!nodes.nodes.length && <span className="text-cyber-amber-bright">Belum ada compute node yang terhubung. Jalankan <code>./hpc.sh head-up</code> (layanan node).</span>}
          </div>
          <p className="mt-2 text-[10px] text-zinc-500">
            Slot: <span className={nodes.capacity.free > 0 ? "text-emerald-400" : "text-cyber-amber-bright"}>{nodes.capacity.free} kosong</span> dari {nodes.capacity.total}
            {" "}&bull; relawan login: <code>ssh -p &lt;port node&gt; jd&lt;id&gt;@{nodes.ssh.host}</code>
            {Object.keys(nodes.ssh.online_hosts).length ? " • internet aktif (cloudflared)" : " • internet: jalankan ./hpc.sh head-online"}
            {" "}&bull; push hanya ke branch jobdesk lewat gerbang git koordinator &bull; akses dicabut otomatis saat SETUJUI / BATAL.
          </p>
        </Panel>
      )}

      <Panel title="BUAT JOBDESK BARU (MASUK ANTREAN FIFO)">
        <form onSubmit={create} className="grid gap-3 md:grid-cols-6">
          <label className="md:col-span-3 text-[10px] uppercase text-zinc-400">
            Judul (fitur / bug di repo B)
            <input className={input} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="mis. Halaman form pengaduan" required minLength={3} maxLength={120} />
          </label>
          <label className="text-[10px] uppercase text-zinc-400">
            Jenis
            <select className={input} value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="fitur">fitur</option>
              <option value="bug">bug</option>
              <option value="lainnya">lainnya</option>
            </select>
          </label>
          <label className="text-[10px] uppercase text-zinc-400">
            Kredit
            <input className={input} type="number" min={0} max={1000} value={credit} onChange={(e) => setCredit(Number(e.target.value))} />
          </label>
          <div className="flex items-end">
            <button disabled={busy === "create" || !project?.enabled} className={`${btn} w-full border-cyber-amber bg-cyber-amber/20 py-2 text-cyber-amber-bright hover:bg-cyber-amber/30`}>
              + TAMBAH
            </button>
          </div>
          <label className="md:col-span-6 text-[10px] uppercase text-zinc-400">
            Deskripsi &amp; kriteria selesai
            <textarea className={`${input} h-16`} value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Apa yang harus dibuat, file mana, test apa yang harus ada..." />
          </label>
        </form>
      </Panel>

      <Panel
        title="PAPAN JOBDESK"
        right={
          <label className="flex cursor-pointer items-center gap-1.5 text-[10px] text-zinc-400">
            <input type="checkbox" checked={showDone} onChange={(e) => setShowDone(e.target.checked)} className="accent-amber-500" />
            tampilkan yang dibatalkan
          </label>
        }
      >
        <div className={`grid gap-3 ${showDone ? "lg:grid-cols-5" : "lg:grid-cols-4"} md:grid-cols-2`}>
          {cols.map((c) => {
            const list = rows.filter((r) => r.status === c.key);
            return (
              <div key={c.key} className="rounded border border-cyber-border bg-black/30 p-2">
                <div className="mb-2 flex items-baseline justify-between">
                  <span className="text-[11px] font-bold text-white">{c.label}</span>
                  <span className="text-[10px] tabular-nums text-zinc-500">{list.length}</span>
                </div>
                <p className="mb-2 text-[10px] text-zinc-600">{c.hint}</p>
                <div className="space-y-2">
                  {list.map((d) => (
                    <div key={d.id} className="rounded border border-cyber-border bg-cyber-surface/70 p-2 text-[11px]">
                      <div className="flex items-start justify-between gap-2">
                        <span className="font-bold text-white">
                          <span className="text-zinc-500">#{d.id}</span> {d.title}
                        </span>
                        <span className={`shrink-0 rounded px-1 text-[9px] font-bold uppercase ${d.kind === "bug" ? "bg-red-950 text-red-300" : "bg-sky-950 text-sky-300"}`}>{d.kind}</span>
                      </div>
                      {d.description && <p className="mt-1 line-clamp-2 text-[10px] text-zinc-400">{d.description}</p>}
                      <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] text-zinc-400">
                        <span className="text-cyber-amber-bright">{d.credit} kredit</span>
                        {d.worker_name && (
                          <span>
                            &bull;{" "}
                            <span title={d.worker_online ? "compute node online" : "compute node offline"} className={d.worker_online ? "text-emerald-400" : "text-zinc-600"}>●</span>{" "}
                            {d.worker_name}
                            {d.github_username && <span className="text-zinc-500"> (@{d.github_username})</span>}
                          </span>
                        )}
                        {d.status === "open" && <span>&bull; menunggu {ago(d.created_at)}</span>}
                      </div>
                      {d.branch && d.status !== "open" && (
                        <div className="mt-1 break-all text-[10px]">
                          <a href={repo ? `${repo}/tree/${d.branch}` : "#"} target="_blank" rel="noreferrer" className="text-zinc-300 underline decoration-zinc-600">
                            {d.branch}
                          </a>
                          {d.last_sha && (
                            <a href={repo ? `${repo}/commit/${d.last_sha}` : "#"} target="_blank" rel="noreferrer" className="ml-1 text-zinc-500">
                              @{d.last_sha.slice(0, 7)}
                            </a>
                          )}
                        </div>
                      )}
                      {d.status !== "open" && d.status !== "cancelled" && (
                        <div className="mt-1.5"><CiBadge status={d.last_ci_status} /></div>
                      )}
                      {d.pr_url && (
                        <a href={d.pr_url} target="_blank" rel="noreferrer" className="mt-1 block text-[10px] text-sky-300 underline">
                          Pull Request #{d.pr_number}{d.merged_sha ? " (merged)" : ""}
                        </a>
                      )}
                      {d.note && <p className="mt-1 text-[10px] text-cyber-amber-bright">Catatan: {d.note}</p>}
                      {project?.node_access && ["in_progress", "review"].includes(d.status) && (
                        <p className="mt-1 text-[10px] text-zinc-400">
                          {d.node_user ? (
                            <>
                              node: <span className="text-white">{d.node_user}</span>@{d.node_name || "menunggu"}{" "}
                              {d.node_sessions ? <span className="text-emerald-400">&bull; {d.node_sessions} sesi login</span>
                                : d.node_last_login ? <span>&bull; login terakhir {ago(d.node_last_login)}</span>
                                : <span>&bull; {d.node_ready ? "belum pernah login" : "disiapkan"}</span>}
                              {d.node_expires_at && <span> &bull; token berlaku s/d {new Date(d.node_expires_at).toLocaleString("id-ID")}</span>}
                            </>
                          ) : <span className="text-cyber-amber-bright">akses compute node dicabut{d.node_last_revoke ? `: ${d.node_last_revoke}` : ""}</span>}
                        </p>
                      )}
                      <div className="mt-2 flex flex-wrap gap-1">
                        {d.status === "review" && (
                          <>
                            <button disabled={!!busy} onClick={() => action(d, "approve", d.pr_number ? "PR di-merge, kredit diberikan" : "disetujui, kredit diberikan")} className={`${btn} border-emerald-800 bg-emerald-950/60 text-emerald-300 hover:bg-emerald-900/60`}>{d.pr_number ? "SETUJUI & MERGE" : "SETUJUI"}</button>
                            <button disabled={!!busy} onClick={() => action(d, "revise", "dikembalikan untuk revisi", true)} className={`${btn} border-cyber-amber-deep text-cyber-amber-bright hover:bg-cyber-amber/20`}>MINTA REVISI</button>
                          </>
                        )}
                        {["open", "in_progress", "review"].includes(d.status) && (
                          <button disabled={!!busy} onClick={() => window.confirm(`Batalkan jobdesk #${d.id}?`) && action(d, "cancel", "dibatalkan")} className={`${btn} border-red-900 text-red-400 hover:bg-red-950`}>BATAL</button>
                        )}
                        {project?.node_access && ["in_progress", "review"].includes(d.status) && (d.node_user ? (
                          <button disabled={!!busy} onClick={() => window.confirm(`Cabut akses compute node ${d.node_user}? Sesi SSH-nya langsung diputus; jobdesk tetap milik relawan.`) && act(`revoke-${d.id}`, `jobdesks/${d.id}/revoke-node`, { reason: "" }, `Akses compute node jobdesk #${d.id} dicabut.`)} className={`${btn} border-red-900 text-red-400 hover:bg-red-950`}>CABUT NODE</button>
                        ) : (
                          <>
                            <button disabled={!!busy} onClick={() => act(`grant-${d.id}`, `jobdesks/${d.id}/grant-node`, {}, `Akses compute node jobdesk #${d.id} diterbitkan ulang (token node baru).`)} className={`${btn} border-cyber-border text-zinc-300 hover:border-cyber-amber`}>BERI AKSES NODE</button>
                            <button disabled={!!busy} onClick={() => window.confirm(`Kembalikan jobdesk #${d.id} ke antrean? Relawan ${d.worker_name || ""} dilepas; branch dan commit yang sudah di-push tetap, relawan berikutnya (FIFO) melanjutkan.`) && action(d, "requeue", "dikembalikan ke antrean")} className={`${btn} border-cyber-border text-zinc-300 hover:border-cyber-amber`}>KEMBALIKAN KE ANTREAN</button>
                          </>
                        ))}
                        {(d.status === "cancelled" || d.status === "done") && (
                          <button disabled={!!busy} onClick={() => action(d, "reopen", "dibuka lagi")} className={`${btn} border-cyber-border text-zinc-300 hover:border-cyber-amber`}>BUKA LAGI</button>
                        )}
                      </div>
                    </div>
                  ))}
                  {!list.length && <p className="py-3 text-center text-[10px] text-zinc-600">kosong</p>}
                </div>
              </div>
            );
          })}
        </div>
      </Panel>

      <Panel title="AKTIVITAS JOBDESK TERBARU">
        <table className="w-full text-xs">
          <thead><tr><th className={th}>Waktu</th><th className={th}>Jobdesk</th><th className={th}>Oleh</th><th className={th}>Peristiwa</th><th className={th}>Detail</th></tr></thead>
          <tbody>
            {events.map((e, i) => (
              <tr key={i} className="border-t border-cyber-border/40">
                <td className={`${td} whitespace-nowrap text-zinc-500`}>{ago(e.at)}</td>
                <td className={td}>#{e.jobdesk_id}</td>
                <td className={td}>{e.actor}</td>
                <td className={`${td} font-bold text-zinc-200`}>{e.event}</td>
                <td className={`${td} text-zinc-400`}>{e.detail}</td>
              </tr>
            ))}
            {!events.length && <tr><td colSpan={5} className={`${td} text-center text-zinc-600`}>belum ada aktivitas</td></tr>}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}

// =============================================================================
// Tab: CI repo B (build + test terdistribusi)
// =============================================================================
export function CiTab({ onUnauthorized }: { onUnauthorized: () => void }) {
  const call = useAdminApi(onUnauthorized);
  const [runs, setRuns] = useState<CiRun[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [logs, setLogs] = useState<{ title: string; text: string } | null>(null);
  const [branch, setBranch] = useState("main");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const d = await call<{ runs: CiRun[]; project: Project }>("ci");
      setRuns(d.runs);
      setProject(d.project);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [call]);

  useEffect(() => {
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [load]);

  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await call<{ job_id: number; sha: string }>("ci", { branch });
      setNotice(`CI job #${r.job_id} dibuat untuk ${branch}@${r.sha.slice(0, 7)}.`);
      setTimeout(() => setNotice(null), 4000);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const showLogs = async (r: CiRun) => {
    try {
      const d = await call<{ logs: { file: string | null; stage: number; worker: string; status: string; log: string }[] }>(`ci/${r.job_id}/log`);
      setLogs({
        title: `Log CI job #${r.job_id} (${r.branch}@${r.sha.slice(0, 7)})`,
        text: d.logs.map((l) => `===== ${l.stage === 0 ? "BUILD" : l.file} @ ${l.worker} [${l.status}] =====\n${l.log}`).join("\n\n") || "(tidak ada log)",
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const repo = project?.repo_url;
  const done = runs.filter((r) => r.wall_s);
  return (
    <div className="space-y-6">
      <ProjectBanner p={project} />
      <Msg error={error} notice={notice} />

      <Panel
        title="CI TERDISTRIBUSI: BUILD -> TEST PER FILE -> LAPORAN"
        right={
          <form onSubmit={run} className="flex items-center gap-2">
            <input className={`${input} w-56`} value={branch} onChange={(e) => setBranch(e.target.value)} placeholder="nama branch" />
            <button disabled={busy || !project?.enabled} className={`${btn} border-cyber-amber bg-cyber-amber/20 py-1.5 text-cyber-amber-bright`}>JALANKAN CI</button>
          </form>
        }
      >
        <p className="mb-3 text-[11px] text-zinc-400">
          Setiap push ke repo B menjadi satu job: <b className="text-white">compute</b> (build + daftar file test, 1 tugas) &rarr;{" "}
          <b className="text-white">communicate</b> (koordinator membagi file test jadi tugas kecil) &rarr; <b className="text-white">compute</b> (tiap file
          test di node berbeda, paralel) &rarr; <b className="text-white">communicate</b> (laporan digabung). Tugas diambil FIFO, tiap tugas dikerjakan{" "}
          {project?.ci_replicas ?? 2} node dan hasilnya harus sama. Push baru di branch yang sama membatalkan CI lama yang belum selesai.
          {done.length > 0 && (
            <> Rata-rata percepatan (waktu 1 node / waktu nyata): <b className="text-cyber-amber-bright">
              {(done.reduce((s, r) => s + (r.speedup_est || 0), 0) / done.length).toFixed(2)}x</b>.</>
          )}
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr>
                <th className={th}>Job</th><th className={th}>Branch @ commit</th><th className={th}>Status</th><th className={th}>Tahap</th>
                <th className={th}>File test</th><th className={th}>Test</th><th className={th}>Node</th><th className={th}>Waktu</th>
                <th className={th}>Waktu 1 node</th><th className={th}>Percepatan</th><th className={th}></th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <React.Fragment key={r.job_id}>
                  <tr className="border-t border-cyber-border/40">
                    <td className={td}>
                      #{r.job_id}
                      <div className="text-[10px] text-zinc-600">{r.source} &bull; {ago(r.created_at)}</div>
                    </td>
                    <td className={`${td} break-all`}>
                      <span className="text-zinc-200">{r.branch}</span>{" "}
                      <a href={repo ? `${repo}/commit/${r.sha}` : "#"} target="_blank" rel="noreferrer" className="text-zinc-500 underline">@{r.sha.slice(0, 7)}</a>
                      {r.jobdesk_id && <div className="text-[10px] text-zinc-500">jobdesk #{r.jobdesk_id}</div>}
                    </td>
                    <td className={td}>
                      <CiBadge status={r.status} />
                      {r.build_error && <div className="mt-1 text-[10px] text-red-300">{r.build_error}</div>}
                      {!!r.shards_failed?.length && <div className="mt-1 text-[10px] text-red-300">gagal: {r.shards_failed.join(", ")}</div>}
                    </td>
                    <td className={td}>{r.step}</td>
                    <td className={`${td} tabular-nums`}>{r.shards ? `${r.shards_done}/${r.shards}` : "-"}</td>
                    <td className={`${td} tabular-nums`}>{r.tests_total != null ? `${r.tests_total - (r.tests_failed || 0)}/${r.tests_total}` : "-"}</td>
                    <td className={`${td} tabular-nums`}>{r.nodes}</td>
                    <td className={`${td} tabular-nums`}>{r.wall_s != null ? `${r.wall_s} s` : "-"}</td>
                    <td className={`${td} tabular-nums`}>{r.compute_s != null ? `${r.compute_s} s` : "-"}</td>
                    <td className={`${td} tabular-nums text-cyber-amber-bright`}>{r.speedup_est != null ? `${r.speedup_est}x` : "-"}</td>
                    <td className={`${td} whitespace-nowrap`}>
                      <button onClick={() => setOpen(open === r.job_id ? null : r.job_id)} className={`${btn} border-cyber-border text-zinc-300`}>{open === r.job_id ? "TUTUP" : "TUGAS"}</button>{" "}
                      <button onClick={() => showLogs(r)} className={`${btn} border-cyber-border text-zinc-300`}>LOG</button>
                    </td>
                  </tr>
                  {open === r.job_id && (
                    <tr>
                      <td colSpan={11} className="bg-black/30 px-3 py-2">
                        <table className="w-full text-[11px]">
                          <thead><tr><th className={th}>Tugas</th><th className={th}>Tahap</th><th className={th}>File</th><th className={th}>Status</th><th className={th}>Hasil</th><th className={th}>Node (replika)</th></tr></thead>
                          <tbody>
                            {(r.tasks || []).map((t) => (
                              <tr key={t.id} className="border-t border-cyber-border/30">
                                <td className={td}>#{t.id}</td>
                                <td className={td}>{t.stage === 0 ? "build" : "test"}</td>
                                <td className={td}>{t.file || "-"}</td>
                                <td className={td}>{t.status}</td>
                                <td className={td}>
                                  {t.stage === 0
                                    ? t.build_ok == null ? "-" : t.build_ok ? "build OK" : `build gagal ${t.error || ""}`
                                    : t.passed == null ? "-" : t.passed ? `lulus (${t.tests ?? "?"} test)` : `GAGAL (${t.failures ?? "?"} dari ${t.tests ?? "?"})`}
                                </td>
                                <td className={td}>
                                  {(t.workers || []).map((w, i) => (
                                    <span key={i} className={`mr-1 ${t.a_status?.[i] === "expired" ? "text-zinc-600 line-through" : t.a_status?.[i] === "running" ? "text-sky-300" : "text-zinc-300"}`}>{w}</span>
                                  ))}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        <p className="mt-1 text-[10px] text-zinc-600">Nama dicoret = node mati / lease habis, tugas dipindah ke node lain.</p>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
              {!runs.length && <tr><td colSpan={11} className={`${td} text-center text-zinc-600`}>belum ada CI. Push ke repo B atau klik JALANKAN CI.</td></tr>}
            </tbody>
          </table>
        </div>
      </Panel>

      {logs && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4" onClick={() => setLogs(null)}>
          <div className="cyber-box max-h-[85vh] w-full max-w-4xl overflow-hidden p-4" onClick={(e) => e.stopPropagation()}>
            <div className="mb-2 flex justify-between">
              <h3 className="text-xs font-bold text-cyber-amber-bright">{logs.title}</h3>
              <button onClick={() => setLogs(null)} className={`${btn} border-cyber-border text-zinc-300`}>TUTUP</button>
            </div>
            <pre className="max-h-[72vh] overflow-auto whitespace-pre-wrap rounded bg-black/60 p-3 text-[10px] text-zinc-300">{logs.text}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
