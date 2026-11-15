"use client";
/**
 * Peran relawan sebagai DEVELOPER: jobdesk yang di-assign SISTEM (FIFO, otomatis saat compute
 * node relawan online), perintah git untuk branch-nya, status CI terdistribusi setiap push,
 * dan tombol ajukan review (sistem membuka Pull Request).
 */
import React, { useCallback, useEffect, useState } from "react";
import { CiBadge } from "../admin/ProjectTabs";

type Jobdesk = {
  id: number; title: string; description: string; kind: string; credit: number; status: string; branch: string | null;
  note: string | null; last_sha: string | null; last_ci_job: number | null; last_ci_status: string | null;
  assigned_at: string | null; done_at: string | null; pr_number: number | null; pr_url: string | null;
  merged_sha: string | null; git?: string[];
};
type CiRun = {
  job_id: number; branch: string; sha: string; status: string; step: string; shards: number; shards_done: number;
  nodes: number; wall_s: number | null; tests_total: number | null; tests_failed: number | null;
  shards_failed: string[] | null; build_error: string | null; created_at: string;
};
type Data = {
  project: { enabled: boolean; repo_url: string | null; app_name: string; require_ci_pass: boolean; max_active: number };
  active: Jobdesk[]; history: Jobdesk[]; queue_open: number; online: boolean; ci: CiRun[];
};

const STATUS_LABEL: Record<string, string> = {
  in_progress: "SEDANG DIKERJAKAN", review: "MENUNGGU REVIEW ADMIN", done: "SELESAI", open: "DIKEMBALIKAN", cancelled: "DIBATALKAN",
};
const btn = "rounded border px-3 py-1.5 text-[11px] font-bold transition-colors disabled:opacity-40";

export default function JobdeskCard() {
  const [d, setD] = useState<Data | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

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

  if (!d) return null;
  const repo = d.project.repo_url;

  return (
    <section className="cyber-box p-4 sm:p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-cyber-border pb-2">
        <h2 className="text-xs font-bold text-cyber-amber-bright">// JOBDESK SAYA (PERAN DEVELOPER)</h2>
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

          {j.status === "in_progress" && j.git && (
            <div className="mt-3">
              <p className="mb-1 text-[10px] uppercase text-zinc-500">
                Kerjakan di branch <span className="text-white">{j.branch}</span> (VS Code / terminal):
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
              <span className="text-[10px] text-zinc-500">Sistem membuka Pull Request ke main; admin menyetujui = PR di-merge.</span>
            </div>
          )}
          {j.pr_url && (
            <a href={j.pr_url} target="_blank" rel="noreferrer" className="mt-2 block text-[11px] text-sky-300 underline">
              Pull Request #{j.pr_number}
            </a>
          )}
        </div>
      ))}

      {d.project.enabled && (
        <div className="space-y-1 text-[11px] text-zinc-400">
          {!d.online && (
            <p className="rounded border border-cyber-amber-deep bg-cyber-amber-darkest/40 p-2 text-cyber-amber-bright">
              Compute node Anda OFFLINE. Jalankan <code>./hpc.sh worker-up</code>.{" "}
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
