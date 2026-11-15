"use client";
import React, { useCallback, useEffect, useState } from "react";
import { CiTab, JobdeskTab } from "./ProjectTabs";
import AlertsTab from "./AlertsTab";
import { useRouter } from "next/navigation";

// =============================================================================
// Tipe data dari /api/admin/* (koordinator)
// =============================================================================
type Overview = {
  tasks: { pending: number; done: number; invalid: number; total: number };
  workers: { total: number; online: number; active: number; suspended: number; verified: number; credits: number };
  assignments: { running: number; expired: number; submitted: number; submitted_5m: number; expired_5m: number };
  jobs: number;
  registrations: { total: number; verified: number; last_24h: number };
  alerts?: { open: number; critical: number };
  backup?: { last_ok: string | null; recent_fail: boolean | null };
  throughput_per_min: { minute: string; n: number }[];
};
type Worker = {
  id: string; name: string; github_username: string | null; email: string | null; status: string;
  credits: number; last_seen: string; created_at: string; has_token: boolean; online: boolean;
  running: number; submitted: number; expired: number; rejected: number;
};
type Job = {
  id: number; kind: string; created_at: string; total: number; done: number; invalid: number;
  pending: number; seconds: number | null; pi: number | null;
  status: string; n_stages: number; current_stage: number; mean_temp: number | null; serial_match: boolean | null;
  code: { repo_url: string; sha: string; entry: string } | null;
  resources: { cpus: number; memory_mb: number; timeout_s: number };
  result_branch: string | null; result_commit: string | null; publish_status: string | null;
};
type Task = {
  id: number; job_id: number; kind: string; status: string; replicas: number; stage?: number;
  running: number; submitted: number; expired: number; last_result_at: string | null;
};
type TaskDetail = {
  task: { id: number; job_id: number; kind: string; status: string; replicas: number; payload: any; result: any };
  assignments: {
    id: number; worker_id: string; worker_name: string; github_username: string | null; status: string;
    result: any; started_at: string; finished_at: string | null; agrees: boolean | null;
  }[];
};
type Activity = {
  id: number; task_id: number; job_id: number; kind: string; status: string; worker_id: string;
  worker_name: string; started_at: string; finished_at: string | null; seconds: number | null;
};
type Registration = {
  session_id: string; worker_name: string; github_username: string; email: string; verified: boolean;
  attempts: number; expired: boolean; created_at: string;
};
type Tab = "overview" | "alerts" | "jobdesk" | "ci" | "workers" | "jobs" | "registrations";

class Unauthorized extends Error {}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/admin/${path}`, { cache: "no-store", ...init });
  if (res.status === 401) throw new Unauthorized();
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Error ${res.status}`);
  return data as T;
}

function post<T>(path: string, body?: unknown) {
  return api<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

function ago(iso: string | null | undefined): string {
  if (!iso) return "-";
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s} dtk lalu`;
  if (s < 3600) return `${Math.floor(s / 60)} mnt lalu`;
  if (s < 86400) return `${Math.floor(s / 3600)} jam lalu`;
  return `${Math.floor(s / 86400)} hari lalu`;
}

const STATUS_STYLE: Record<string, string> = {
  active: "border-emerald-800 bg-emerald-950 text-emerald-400",
  done: "border-emerald-800 bg-emerald-950 text-emerald-400",
  submitted: "border-emerald-800 bg-emerald-950 text-emerald-400",
  verified: "border-emerald-800 bg-emerald-950 text-emerald-400",
  pending: "border-cyber-amber-deep bg-cyber-amber-darkest/60 text-cyber-amber-bright",
  running: "border-sky-800 bg-sky-950 text-sky-300",
  suspended: "border-red-800 bg-red-950 text-red-300",
  invalid: "border-red-800 bg-red-950 text-red-300",
  expired: "border-zinc-700 bg-zinc-900 text-zinc-400",
};

function Badge({ status, label }: { status: string; label?: string }) {
  return (
    <span
      className={`inline-block rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase ${
        STATUS_STYLE[status] || "border-zinc-700 bg-zinc-900 text-zinc-300"
      }`}
    >
      {label || status}
    </span>
  );
}

function Stat({ label, value, sub, tone = "text-white" }: { label: string; value: React.ReactNode; sub?: React.ReactNode; tone?: string }) {
  return (
    <div className="cyber-box p-4 border-l-2 border-l-cyber-amber">
      <span className="text-[10px] uppercase text-zinc-400">{label}</span>
      <div className={`mt-1 text-2xl font-bold tabular-nums ${tone}`}>{value}</div>
      {sub && <p className="mt-1 text-[10px] text-zinc-500">{sub}</p>}
    </div>
  );
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

const th = "px-2 py-2 text-left text-[10px] font-semibold uppercase text-zinc-500";
const td = "px-2 py-2 align-top";
const btn =
  "rounded border px-2 py-1 text-[10px] font-bold transition-colors disabled:opacity-40";

// =============================================================================
// Halaman
// =============================================================================
export default function AdminDashboardPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("overview");
  const [me, setMe] = useState<{ email: string; expires_at: string } | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [activity, setActivity] = useState<Activity[]>([]);
  const [regs, setRegs] = useState<Registration[]>([]);
  const [jobFilter, setJobFilter] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  const onError = useCallback(
    (e: unknown) => {
      if (e instanceof Unauthorized) {
        router.replace("/admin/login");
        return;
      }
      setError(e instanceof Error ? e.message : String(e));
    },
    [router]
  );

  const load = useCallback(async () => {
    try {
      const jobs: Promise<void>[] = [api<Overview>("overview").then(setOverview)];
      if (tab === "overview") jobs.push(api<{ activity: Activity[] }>("activity?limit=15").then((d) => setActivity(d.activity)));
      if (tab === "workers") jobs.push(api<{ workers: Worker[] }>("workers").then((d) => setWorkers(d.workers)));
      if (tab === "jobs") {
        const q = new URLSearchParams({ limit: "200" });
        if (jobFilter !== null) q.set("job_id", String(jobFilter));
        if (statusFilter) q.set("status", statusFilter);
        jobs.push(api<{ jobs: Job[] }>("jobs").then((d) => setJobs(d.jobs)));
        jobs.push(api<{ tasks: Task[] }>(`tasks?${q}`).then((d) => setTasks(d.tasks)));
      }
      if (tab === "registrations") jobs.push(api<{ registrations: Registration[] }>("registrations").then((d) => setRegs(d.registrations)));
      await Promise.all(jobs);
      setError(null);
      setUpdatedAt(new Date());
    } catch (e) {
      onError(e);
    }
  }, [tab, jobFilter, statusFilter, onError]);

  useEffect(() => {
    api<{ email: string; expires_at: string }>("me").then(setMe).catch(onError);
  }, [onError]);

  useEffect(() => {
    load();
    if (!autoRefresh) return;
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load, autoRefresh]);

  const toLogin = useCallback(() => router.replace("/admin/login"), [router]);

  const logout = async () => {
    await fetch("/api/admin/logout", { method: "POST" }).catch(() => undefined);
    router.replace("/admin/login");
  };

  const act = async (key: string, fn: () => Promise<any>, msg: string) => {
    setBusy(key);
    try {
      await fn();
      setNotice(msg);
      setTimeout(() => setNotice(null), 4000);
      await load();
    } catch (e) {
      onError(e);
    } finally {
      setBusy(null);
    }
  };

  const openTask = async (id: number) => {
    try {
      setDetail(await api<TaskDetail>(`tasks/${id}`));
    } catch (e) {
      onError(e);
    }
  };

  const tabs: { key: Tab; label: string }[] = [
    { key: "overview", label: "RINGKASAN" },
    { key: "alerts", label: `PERINGATAN${overview?.alerts?.open ? ` (${overview.alerts.open})` : ""}` },
    { key: "jobdesk", label: "JOBDESK (REPO B)" },
    { key: "ci", label: "CI TERDISTRIBUSI" },
    { key: "workers", label: `WORKER${overview ? ` (${overview.workers.total})` : ""}` },
    { key: "jobs", label: "JOB KOMPUTASI" },
    { key: "registrations", label: "PENDAFTARAN" },
  ];

  return (
    <div className="min-h-screen py-8 px-4 sm:px-6 lg:px-8 font-mono">
      <div className="mx-auto max-w-7xl">
        {/* Header */}
        <div className="flex flex-col gap-4 border-b border-cyber-border pb-4 md:flex-row md:items-end md:justify-between">
          <div>
            <span className="text-xs font-bold uppercase tracking-widest text-cyber-amber-bright">
              // ADMIN CONSOLE &bull; HEAD NODE
            </span>
            <h1 className="mt-1 text-2xl font-extrabold text-white sm:text-3xl">DASHBOARD ADMIN</h1>
            <p className="mt-1 text-[11px] text-zinc-500">
              Data langsung dari koordinator &bull; diperbarui {updatedAt ? ago(updatedAt.toISOString()) : "..."}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            <span className="rounded border border-cyber-border bg-cyber-surface px-3 py-1.5 text-zinc-300">
              ADMIN: <span className="text-cyber-amber-bright">{me?.email || "..."}</span>
            </span>
            <label className="flex cursor-pointer items-center gap-1.5 rounded border border-cyber-border bg-cyber-surface px-3 py-1.5 text-zinc-300">
              <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} className="accent-amber-500" />
              AUTO-REFRESH 5s
            </label>
            <button onClick={load} className={`${btn} border-cyber-border bg-cyber-surface py-1.5 text-zinc-200 hover:border-cyber-amber`}>
              MUAT ULANG
            </button>
            <button onClick={logout} className={`${btn} border-red-800 bg-red-950/60 py-1.5 text-red-300 hover:bg-red-900/60`}>
              LOGOUT
            </button>
          </div>
        </div>

        {error && (
          <div role="alert" className="mt-4 rounded border border-red-500/50 bg-red-950/40 p-3 text-xs text-red-300">
            [ERROR]: {error}
          </div>
        )}
        {notice && (
          <div className="mt-4 rounded border border-emerald-700/60 bg-emerald-950/40 p-3 text-xs text-emerald-300">
            {notice}
          </div>
        )}

        {/* Tabs */}
        <div className="mt-6 flex overflow-x-auto border-b border-cyber-border text-xs">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`whitespace-nowrap border-b-2 px-4 py-2.5 font-bold transition-all ${
                t.key === "alerts" && overview?.alerts?.critical ? "!text-red-400 " : ""
              }${
                tab === t.key
                  ? "border-cyber-amber bg-cyber-surface/50 text-cyber-amber-bright"
                  : "border-transparent text-zinc-400 hover:text-white"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="mt-6 space-y-6">
          {tab === "overview" && overview?.alerts?.critical ? (
            <button onClick={() => setTab("alerts")} className="block w-full rounded border border-red-500/60 bg-red-950/50 p-3 text-left text-xs font-bold text-red-300 hover:bg-red-900/50">
              ! {overview.alerts.critical} PERINGATAN CRITICAL belum ditangani. Buka tab PERINGATAN.
            </button>
          ) : null}
          {tab === "overview" && <OverviewTab o={overview} activity={activity} />}
          {tab === "alerts" && <AlertsTab onUnauthorized={toLogin} />}
          {tab === "jobdesk" && <JobdeskTab onUnauthorized={toLogin} />}
          {tab === "ci" && <CiTab onUnauthorized={toLogin} />}
          {tab === "workers" && (
            <WorkersTab
              workers={workers}
              busy={busy}
              onStatus={(w, status) =>
                act(`st-${w.id}`, () => post(`workers/${w.id}/status`, { status, reason: "via dashboard admin" }),
                  `Worker ${w.name} ${status === "active" ? "diaktifkan" : "ditangguhkan"}.`)
              }
              onRevoke={(w) => {
                if (!window.confirm(`Cabut token worker "${w.name}"? Worker harus login ulang (./hpc.sh worker-login).`)) return;
                act(`rv-${w.id}`, () => post(`workers/${w.id}/revoke-token`), `Token worker ${w.name} dicabut.`);
              }}
            />
          )}
          {tab === "jobs" && (
            <JobsTab
              jobs={jobs}
              tasks={tasks}
              jobFilter={jobFilter}
              statusFilter={statusFilter}
              setJobFilter={setJobFilter}
              setStatusFilter={setStatusFilter}
              busy={busy}
              onCreate={(body) => act("create-job", () => post("jobs", body), `Job ${body.kind} dibuat.`)}
              onOpenTask={openTask}
            />
          )}
          {tab === "registrations" && <RegistrationsTab regs={regs} />}
        </div>
      </div>

      {detail && <TaskDetailModal d={detail} onClose={() => setDetail(null)} />}
    </div>
  );
}

// =============================================================================
// Tab: Ringkasan
// =============================================================================
function OverviewTab({ o, activity }: { o: Overview | null; activity: Activity[] }) {
  if (!o) return <p className="text-xs text-zinc-500">Memuat data koordinator...</p>;
  const max = Math.max(1, ...o.throughput_per_min.map((p) => p.n));
  const pct = (n: number) => (o.tasks.total ? (n / o.tasks.total) * 100 : 0);
  return (
    <>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Worker online" value={`${o.workers.online}/${o.workers.total}`} tone="text-emerald-400"
          sub={`${o.workers.verified} terverifikasi GitHub • ${o.workers.suspended} ditangguhkan`} />
        <Stat label="Tugas selesai (valid)" value={o.tasks.done}
          sub={`${o.tasks.pending} antre • ${o.tasks.invalid} invalid • ${o.jobs} job`} />
        <Stat label="Hasil masuk / menit" value={(o.assignments.submitted_5m / 5).toFixed(1)} tone="text-cyber-amber-bright"
          sub={`${o.assignments.running} sedang dikerjakan`} />
        <Stat label="Lease habis (5 mnt)" value={o.assignments.expired_5m}
          tone={o.assignments.expired_5m ? "text-red-300" : "text-white"}
          sub={`Total ${o.assignments.expired} tugas dikembalikan ke antrean`} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Panel title="THROUGHPUT: TUGAS TERVALIDASI / MENIT (10 MNT)">
          <div className="flex h-32 items-end gap-1" role="img" aria-label="Grafik tugas tervalidasi per menit">
            {o.throughput_per_min.map((p) => (
              <div key={p.minute} className="group relative flex h-full flex-1 flex-col justify-end">
                <div className="rounded-t-sm bg-cyber-amber/80 group-hover:bg-cyber-amber-bright" style={{ height: `${(p.n / max) * 100}%`, minHeight: p.n ? 2 : 0 }} />
                <span className="pointer-events-none absolute -top-5 left-1/2 hidden -translate-x-1/2 rounded bg-cyber-black px-1 text-[10px] text-white group-hover:block">
                  {p.n}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-1 flex justify-between text-[10px] text-zinc-500">
            <span>-10 mnt</span>
            <span>sekarang</span>
          </div>
        </Panel>

        <Panel title="STATUS ANTREAN TUGAS">
          <div className="flex h-3 w-full overflow-hidden rounded bg-cyber-black">
            <div className="bg-emerald-500" style={{ width: `${pct(o.tasks.done)}%` }} />
            <div className="bg-cyber-amber" style={{ width: `${pct(o.tasks.pending)}%` }} />
            <div className="bg-red-500" style={{ width: `${pct(o.tasks.invalid)}%` }} />
          </div>
          <ul className="mt-3 space-y-1 text-xs">
            <li className="flex justify-between"><span className="text-emerald-400">■ Selesai</span><span className="tabular-nums">{o.tasks.done}</span></li>
            <li className="flex justify-between"><span className="text-cyber-amber-bright">■ Antre / proses</span><span className="tabular-nums">{o.tasks.pending}</span></li>
            <li className="flex justify-between"><span className="text-red-400">■ Invalid</span><span className="tabular-nums">{o.tasks.invalid}</span></li>
          </ul>
        </Panel>

        <Panel title="RELAWAN & KREDIT">
          <ul className="space-y-2 text-xs">
            <li className="flex justify-between"><span className="text-zinc-400">Total kredit dibagikan</span><span className="font-bold text-cyber-amber-bright tabular-nums">{o.workers.credits}</span></li>
            <li className="flex justify-between"><span className="text-zinc-400">Pendaftaran (24 jam)</span><span className="tabular-nums">{o.registrations.last_24h}</span></li>
            <li className="flex justify-between"><span className="text-zinc-400">Pendaftaran terverifikasi OTP</span><span className="tabular-nums">{o.registrations.verified}/{o.registrations.total}</span></li>
            <li className="flex justify-between"><span className="text-zinc-400">Worker aktif</span><span className="tabular-nums">{o.workers.active}</span></li>
          </ul>
        </Panel>
      </div>

      <Panel title="AKTIVITAS TERBARU">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr><th className={th}>Waktu</th><th className={th}>Worker</th><th className={th}>Tugas</th><th className={th}>Status</th><th className={th}>Durasi</th></tr></thead>
            <tbody>
              {activity.map((a) => (
                <tr key={a.id} className="border-t border-cyber-border/50">
                  <td className={`${td} text-zinc-400`}>{ago(a.finished_at || a.started_at)}</td>
                  <td className={td}>{a.worker_name}</td>
                  <td className={td}>#{a.task_id} <span className="text-zinc-500">({a.kind}, job {a.job_id})</span></td>
                  <td className={td}><Badge status={a.status} /></td>
                  <td className={`${td} tabular-nums`}>{a.seconds != null ? `${Number(a.seconds).toFixed(1)} s` : "-"}</td>
                </tr>
              ))}
              {!activity.length && <tr><td colSpan={5} className={`${td} text-zinc-500`}>Belum ada aktivitas.</td></tr>}
            </tbody>
          </table>
        </div>
      </Panel>
    </>
  );
}

// =============================================================================
// Tab: Worker
// =============================================================================
function WorkersTab({ workers, busy, onStatus, onRevoke }: {
  workers: Worker[]; busy: string | null;
  onStatus: (w: Worker, status: "active" | "suspended") => void;
  onRevoke: (w: Worker) => void;
}) {
  return (
    <Panel title="MANAJEMEN WORKER" right={<span className="text-[10px] text-zinc-500">Online = heartbeat &lt; 60 dtk</span>}>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr>
              <th className={th}>Worker</th><th className={th}>GitHub / Email</th><th className={th}>Status</th>
              <th className={th}>Jalan</th><th className={th}>Hasil</th><th className={th}>Beda hasil</th>
              <th className={th}>Lease habis</th><th className={th}>Kredit</th><th className={th}>Terakhir aktif</th><th className={th}>Aksi</th>
            </tr>
          </thead>
          <tbody>
            {workers.map((w) => (
              <tr key={w.id} className="border-t border-cyber-border/50">
                <td className={td}>
                  <div className="flex items-center gap-1.5">
                    <span className={`h-2 w-2 rounded-full ${w.online ? "bg-emerald-400" : "bg-zinc-600"}`} title={w.online ? "online" : "offline"} />
                    <span className="font-bold text-white">{w.name}</span>
                  </div>
                  <div className="text-[10px] text-zinc-500">{w.id}</div>
                </td>
                <td className={td}>
                  {w.github_username ? (
                    <a href={`https://github.com/${encodeURIComponent(w.github_username)}`} target="_blank" rel="noreferrer" className="text-cyber-amber-bright hover:underline">
                      @{w.github_username}
                    </a>
                  ) : <span className="text-zinc-500">anonim (token global)</span>}
                  <div className="text-[10px] text-zinc-400">{w.email || "-"}</div>
                </td>
                <td className={td}>
                  <Badge status={w.status} />
                  {!w.has_token && w.github_username && <div className="mt-1 text-[10px] text-zinc-500">token dicabut</div>}
                </td>
                <td className={`${td} tabular-nums`}>{w.running}</td>
                <td className={`${td} tabular-nums`}>{w.submitted}</td>
                <td className={`${td} tabular-nums ${w.rejected ? "font-bold text-red-300" : ""}`}>{w.rejected}</td>
                <td className={`${td} tabular-nums`}>{w.expired}</td>
                <td className={`${td} tabular-nums font-bold text-cyber-amber-bright`}>{w.credits}</td>
                <td className={`${td} text-zinc-400`}>{ago(w.last_seen)}</td>
                <td className={td}>
                  <div className="flex flex-wrap gap-1">
                    {w.status === "active" ? (
                      <button disabled={busy === `st-${w.id}`} onClick={() => onStatus(w, "suspended")} className={`${btn} border-red-800 text-red-300 hover:bg-red-950`}>
                        TANGGUHKAN
                      </button>
                    ) : (
                      <button disabled={busy === `st-${w.id}`} onClick={() => onStatus(w, "active")} className={`${btn} border-emerald-800 text-emerald-300 hover:bg-emerald-950`}>
                        AKTIFKAN
                      </button>
                    )}
                    {w.has_token && (
                      <button disabled={busy === `rv-${w.id}`} onClick={() => onRevoke(w)} className={`${btn} border-cyber-border text-zinc-300 hover:border-cyber-amber`}>
                        CABUT TOKEN
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {!workers.length && <tr><td colSpan={10} className={`${td} text-zinc-500`}>Belum ada worker terdaftar.</td></tr>}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-[10px] text-zinc-500">
        &quot;Beda hasil&quot; = jumlah hasil worker yang tidak sama dengan hasil final quorum (indikasi worker curang/rusak).
      </p>
    </Panel>
  );
}

// =============================================================================
// Tab: Job & Tugas
// =============================================================================
function JobsTab({ jobs, tasks, jobFilter, statusFilter, setJobFilter, setStatusFilter, busy, onCreate, onOpenTask }: {
  jobs: Job[]; tasks: Task[]; jobFilter: number | null; statusFilter: string;
  setJobFilter: (v: number | null) => void; setStatusFilter: (v: string) => void; busy: string | null;
  onCreate: (b: Record<string, any>) => void;
  onOpenTask: (id: number) => void;
}) {
  const [kind, setKind] = useState("montecarlo_pi");
  const [nTasks, setNTasks] = useState(20);
  const [replicas, setReplicas] = useState(2);
  const [size, setSize] = useState("");
  // heat2d (multi-tahap)
  const [grid, setGrid] = useState(160);
  const [stages, setStages] = useState(10);
  const [steps, setSteps] = useState(20);
  // kode dari repo job (wajib untuk jenis "repo", opsional untuk jenis lain)
  const [repoUrl, setRepoUrl] = useState("");
  const [sha, setSha] = useState("");
  const [entry, setEntry] = useState("python3 run.py");
  const [taskKind, setTaskKind] = useState("prime_count");
  // resource per tugas
  const [cpus, setCpus] = useState(1);
  const [mem, setMem] = useState(256);
  const [timeout, setTimeoutS] = useState(120);
  const input = "mt-1 w-full rounded border border-cyber-border bg-cyber-black px-2 py-1.5 text-xs text-white focus:border-cyber-amber focus:outline-none";
  const lbl = "text-[10px] text-zinc-400";

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const body: Record<string, any> = {
      kind, n_tasks: nTasks, replicas,
      resources: { cpus, memory_mb: mem, timeout_s: timeout },
    };
    if (size && (kind === "montecarlo_pi" || kind === "mandelbrot")) body.size = Number(size);
    if (kind === "heat2d") body.params = { n: grid, stages, steps };
    if (kind === "repo") body.task_kind = taskKind;
    if (sha.trim() || kind === "repo") body.code = { repo_url: repoUrl.trim() || undefined, sha: sha.trim(), entry };
    onCreate(body);
  };

  return (
    <>
      <Panel title="BUAT JOB BARU (MASUK ANTREAN FIFO)">
        <form className="space-y-3" onSubmit={submit}>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <label className={lbl}>JENIS
              <select value={kind} onChange={(e) => setKind(e.target.value)} className={input}>
                <option value="montecarlo_pi">Monte Carlo π (1 tahap)</option>
                <option value="mandelbrot">Mandelbrot (1 tahap)</option>
                <option value="heat2d">Simulasi panas 2D (multi-tahap)</option>
                <option value="repo">Program dari repo job</option>
              </select>
            </label>
            <label className={lbl}>{kind === "heat2d" ? "JUMLAH BLOK (TUGAS / TAHAP)" : "JUMLAH TUGAS"}
              <input type="number" min={1} max={1000} value={nTasks} onChange={(e) => setNTasks(Number(e.target.value))} className={input} />
            </label>
            <label className={lbl}>REPLIKA
              <input type="number" min={1} max={4} value={replicas} onChange={(e) => setReplicas(Number(e.target.value))} className={input} />
            </label>
            {(kind === "montecarlo_pi" || kind === "mandelbrot") && (
              <label className={lbl}>UKURAN (OPSIONAL)
                <input type="number" min={1} value={size} onChange={(e) => setSize(e.target.value)}
                  placeholder={kind === "montecarlo_pi" ? "30000000 sampel" : "2000 px"} className={input} />
              </label>
            )}
            {kind === "repo" && (
              <label className={lbl}>TASK_KIND (DITERUSKAN KE PROGRAM)
                <input value={taskKind} onChange={(e) => setTaskKind(e.target.value)} className={input} />
              </label>
            )}
          </div>
          {kind === "heat2d" && (
            <div className="grid grid-cols-3 gap-3">
              <label className={lbl}>UKURAN GRID N (N x N)
                <input type="number" min={8} max={1024} value={grid} onChange={(e) => setGrid(Number(e.target.value))} className={input} />
              </label>
              <label className={lbl}>JUMLAH TAHAP
                <input type="number" min={1} max={200} value={stages} onChange={(e) => setStages(Number(e.target.value))} className={input} />
              </label>
              <label className={lbl}>LANGKAH WAKTU / TAHAP (= TEBAL HALO)
                <input type="number" min={1} max={500} value={steps} onChange={(e) => setSteps(Number(e.target.value))} className={input} />
              </label>
            </div>
          )}
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <label className={lbl}>REPO JOB {kind === "repo" ? "" : "(OPSIONAL)"} — KOSONG = JOB_REPO_URL
              <input value={repoUrl} onChange={(e) => setRepoUrl(e.target.value)} placeholder="https://github.com/org/hpc-jobs" className={input} />
            </label>
            <label className={lbl}>COMMIT SHA (40 HEX){kind === "repo" ? "" : " — KOSONG = KODE BAWAAN WORKER"}
              <input value={sha} onChange={(e) => setSha(e.target.value)} placeholder="git rev-parse HEAD" className={input} />
            </label>
            <label className={lbl}>PERINTAH (ENTRY)
              <input value={entry} onChange={(e) => setEntry(e.target.value)} className={input} />
            </label>
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 md:items-end">
            <label className={lbl}>CPU / TUGAS
              <input type="number" min={0.1} max={4} step={0.1} value={cpus} onChange={(e) => setCpus(Number(e.target.value))} className={input} />
            </label>
            <label className={lbl}>MEMORI (MB)
              <input type="number" min={16} max={4096} value={mem} onChange={(e) => setMem(Number(e.target.value))} className={input} />
            </label>
            <label className={lbl}>BATAS WAKTU (DETIK)
              <input type="number" min={1} max={3600} value={timeout} onChange={(e) => setTimeoutS(Number(e.target.value))} className={input} />
            </label>
            <button type="submit" disabled={busy === "create-job"}
              className="rounded border border-cyber-amber bg-cyber-amber py-2 text-xs font-bold text-cyber-void hover:bg-cyber-amber-bright disabled:opacity-50">
              {busy === "create-job" ? "MEMBUAT..." : "BUAT JOB"}
            </button>
          </div>
        </form>
      </Panel>

      <Panel title="JOB (50 TERBARU)">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr><th className={th}>ID</th><th className={th}>Jenis</th><th className={th}>Tahap</th><th className={th}>Progres</th><th className={th}>Invalid</th><th className={th}>Durasi</th><th className={th}>Hasil</th><th className={th}>Kode & branch hasil</th><th className={th}>Dibuat</th><th className={th}></th></tr></thead>
            <tbody>
              {jobs.map((j) => {
                const p = j.total ? (j.done / j.total) * 100 : 0;
                return (
                  <tr key={j.id} className={`border-t border-cyber-border/50 ${jobFilter === j.id ? "bg-cyber-surface/60" : ""}`}>
                    <td className={`${td} font-bold`}>#{j.id}</td>
                    <td className={td}>{j.kind}<div className="text-[10px] text-zinc-500">{j.status} • {j.resources?.cpus} CPU/{j.resources?.memory_mb} MB/{j.resources?.timeout_s}s</div></td>
                    <td className={`${td} tabular-nums`}>{Math.min(j.current_stage + 1, j.n_stages)}/{j.n_stages}</td>
                    <td className={`${td} min-w-[140px]`}>
                      <div className="h-1.5 w-full rounded bg-cyber-black"><div className="h-1.5 rounded bg-emerald-500" style={{ width: `${p}%` }} /></div>
                      <span className="text-[10px] text-zinc-400 tabular-nums">{j.done}/{j.total} selesai</span>
                    </td>
                    <td className={`${td} tabular-nums ${j.invalid ? "text-red-300" : ""}`}>{j.invalid}</td>
                    <td className={`${td} tabular-nums`}>{j.seconds != null ? `${Math.round(Number(j.seconds))} s` : "-"}</td>
                    <td className={td}>
                      {j.pi != null ? `π ≈ ${Number(j.pi).toFixed(6)}` : j.mean_temp != null ? (
                        <a href={`/api/jobs/${j.id}/heatmap`} target="_blank" className="text-cyber-amber-bright hover:underline">
                          T̄ = {Number(j.mean_temp).toFixed(3)} (heatmap)
                        </a>
                      ) : "-"}
                      {j.serial_match != null && <div className={`text-[10px] ${j.serial_match ? "text-emerald-400" : "text-red-300"}`}>{j.serial_match ? "identik dengan serial" : "BEDA dengan serial"}</div>}
                    </td>
                    <td className={`${td} text-[10px] text-zinc-400`}>
                      {j.code ? <div>{j.code.repo_url.replace("https://github.com/", "")} @ {j.code.sha.slice(0, 10)}</div> : <div>bawaan worker</div>}
                      {j.result_branch ? <div className="text-emerald-400">{j.result_branch} ({(j.result_commit || "").slice(0, 7)})</div>
                        : j.publish_status ? <div title={j.publish_status}>{j.publish_status.slice(0, 40)}</div> : null}
                    </td>
                    <td className={`${td} text-zinc-400`}>{ago(j.created_at)}</td>
                    <td className={td}>
                      <button onClick={() => setJobFilter(jobFilter === j.id ? null : j.id)} className={`${btn} border-cyber-border text-zinc-300 hover:border-cyber-amber`}>
                        {jobFilter === j.id ? "SEMUA TUGAS" : "LIHAT TUGAS"}
                      </button>
                    </td>
                  </tr>
                );
              })}
              {!jobs.length && <tr><td colSpan={10} className={`${td} text-zinc-500`}>Belum ada job.</td></tr>}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel
        title={`TUGAS & VALIDASI${jobFilter !== null ? ` • JOB #${jobFilter}` : ""}`}
        right={
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded border border-cyber-border bg-cyber-black px-2 py-1 text-[11px] text-white">
            <option value="">Semua status</option>
            <option value="pending">pending</option>
            <option value="done">done</option>
            <option value="invalid">invalid</option>
            <option value="cancelled">cancelled</option>
          </select>
        }
      >
        <div className="max-h-[420px] overflow-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-cyber-dark"><tr><th className={th}>Tugas</th><th className={th}>Job</th><th className={th}>Status</th><th className={th}>Replika</th><th className={th}>Jalan</th><th className={th}>Hasil masuk</th><th className={th}>Lease habis</th><th className={th}>Hasil terakhir</th><th className={th}></th></tr></thead>
            <tbody>
              {tasks.map((t) => (
                <tr key={t.id} className="border-t border-cyber-border/50">
                  <td className={`${td} font-bold`}>#{t.id}</td>
                  <td className={td}>#{t.job_id} <span className="text-zinc-500">{t.kind}{t.stage ? ` • tahap ${t.stage + 1}` : ""}</span></td>
                  <td className={td}><Badge status={t.status} /></td>
                  <td className={`${td} tabular-nums`}>{t.replicas}</td>
                  <td className={`${td} tabular-nums`}>{t.running}</td>
                  <td className={`${td} tabular-nums`}>{t.submitted}/{t.replicas}</td>
                  <td className={`${td} tabular-nums`}>{t.expired}</td>
                  <td className={`${td} text-zinc-400`}>{ago(t.last_result_at)}</td>
                  <td className={td}>
                    <button onClick={() => onOpenTask(t.id)} className={`${btn} border-cyber-border text-zinc-300 hover:border-cyber-amber`}>DETAIL</button>
                  </td>
                </tr>
              ))}
              {!tasks.length && <tr><td colSpan={9} className={`${td} text-zinc-500`}>Tidak ada tugas.</td></tr>}
            </tbody>
          </table>
        </div>
      </Panel>
    </>
  );
}

function TaskDetailModal({ d, onClose }: { d: TaskDetail; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 p-4 font-mono" onClick={onClose}>
      <div role="dialog" aria-modal="true" className="cyber-box max-h-[85vh] w-full max-w-3xl overflow-auto bg-cyber-dark p-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between border-b border-cyber-border pb-2">
          <div>
            <h3 className="text-sm font-bold text-white">TUGAS #{d.task.id} <span className="text-zinc-500">• job #{d.task.job_id} • {d.task.kind}</span></h3>
            <div className="mt-1 flex items-center gap-2 text-[11px] text-zinc-400"><Badge status={d.task.status} /> replika target {d.task.replicas}</div>
          </div>
          <button onClick={onClose} className={`${btn} border-cyber-border text-zinc-300 hover:border-cyber-amber`}>TUTUP</button>
        </div>
        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
          <div>
            <p className="text-[10px] text-zinc-500">PAYLOAD</p>
            <pre className="mt-1 overflow-auto rounded bg-cyber-black p-2 text-[11px] text-zinc-300">{JSON.stringify(d.task.payload, null, 2)}</pre>
          </div>
          <div>
            <p className="text-[10px] text-zinc-500">HASIL FINAL (QUORUM)</p>
            <pre className="mt-1 max-h-40 overflow-auto rounded bg-cyber-black p-2 text-[11px] text-emerald-300">{d.task.result ? JSON.stringify(d.task.result, null, 2) : "belum ada"}</pre>
          </div>
        </div>
        <p className="mt-4 text-[10px] text-zinc-500">REPLIKA / ASSIGNMENT</p>
        <div className="overflow-x-auto">
          <table className="mt-1 w-full text-xs">
            <thead><tr><th className={th}>#</th><th className={th}>Worker</th><th className={th}>Status</th><th className={th}>Sepakat?</th><th className={th}>Hasil</th><th className={th}>Selesai</th></tr></thead>
            <tbody>
              {d.assignments.map((a) => (
                <tr key={a.id} className="border-t border-cyber-border/50">
                  <td className={td}>{a.id}</td>
                  <td className={td}>{a.worker_name}{a.github_username && <div className="text-[10px] text-zinc-500">@{a.github_username}</div>}</td>
                  <td className={td}><Badge status={a.status} /></td>
                  <td className={td}>
                    {a.agrees === true && <span className="text-emerald-400">✓ ya</span>}
                    {a.agrees === false && <span className="font-bold text-red-300">✗ beda</span>}
                    {a.agrees === null && <span className="text-zinc-500">-</span>}
                  </td>
                  <td className={td}><code className="block max-w-[260px] truncate text-[10px] text-zinc-300" title={JSON.stringify(a.result)}>{a.result ? JSON.stringify(a.result) : "-"}</code></td>
                  <td className={`${td} text-zinc-400`}>{ago(a.finished_at)}</td>
                </tr>
              ))}
              {!d.assignments.length && <tr><td colSpan={6} className={`${td} text-zinc-500`}>Belum pernah diambil worker.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Tab: Pendaftaran
// =============================================================================
function RegistrationsTab({ regs }: { regs: Registration[] }) {
  return (
    <Panel title="RIWAYAT PENDAFTARAN RELAWAN (GITHUB + OTP)">
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead><tr><th className={th}>Waktu</th><th className={th}>Worker</th><th className={th}>GitHub</th><th className={th}>Email</th><th className={th}>Status</th><th className={th}>Salah OTP</th></tr></thead>
          <tbody>
            {regs.map((r) => (
              <tr key={r.session_id + r.created_at} className="border-t border-cyber-border/50">
                <td className={`${td} text-zinc-400`}>{ago(r.created_at)}</td>
                <td className={td}>{r.worker_name}</td>
                <td className={td}>@{r.github_username}</td>
                <td className={td}>{r.email}</td>
                <td className={td}>
                  {r.verified ? <Badge status="verified" label="terverifikasi" />
                    : r.expired ? <Badge status="expired" label="OTP kedaluwarsa" />
                    : <Badge status="pending" label="menunggu OTP" />}
                </td>
                <td className={`${td} tabular-nums ${r.attempts >= 3 ? "text-red-300" : ""}`}>{r.attempts}</td>
              </tr>
            ))}
            {!regs.length && <tr><td colSpan={6} className={`${td} text-zinc-500`}>Belum ada pendaftaran.</td></tr>}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
