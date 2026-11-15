"use client";
/**
 * Tab "PERINGATAN" di dashboard admin: hasil watch (pemantauan kejadian) dan status backup.
 * Koordinator mendeteksi error dan aktivitas mencurigakan (termasuk cek per branch repo B),
 * mencatatnya di tabel alerts, dan mengirim ringkasannya ke email admin.
 */
import React, { useCallback, useEffect, useState } from "react";

type Alert = {
  id: number; key: string; level: "info" | "warning" | "critical"; category: string; title: string;
  detail: string | null; ref: Record<string, string | number | null | string[]>; count: number;
  created_at: string; last_at: string; acked_at: string | null; acked_by: string | null; emailed_at: string | null;
};
type AlertData = {
  summary: { open: number; critical: number; warning: number; info: number };
  alerts: Alert[];
  email: { to: boolean; min_level: string; cooldown_min: number };
};
type Backup = { id: number; at: string; ok: boolean; file: string | null; bytes: number | null; sha256: string | null; copied: boolean; error: string | null };
type BackupData = { backups: Backup[]; last_ok: { at: string; age_min: number } | null; max_age_min: number };

const btn = "rounded border px-2 py-1 text-[10px] font-bold transition-colors disabled:opacity-40";
const LEVEL_STYLE: Record<string, string> = {
  critical: "border-red-700 bg-red-950 text-red-300",
  warning: "border-amber-700 bg-amber-950 text-amber-300",
  info: "border-sky-800 bg-sky-950 text-sky-300",
};
const CATEGORY_LABEL: Record<string, string> = {
  error: "ERROR SISTEM", suspicious: "MENCURIGAKAN", branch: "CEK BRANCH", backup: "BACKUP", node: "COMPUTE NODE",
};

function ago(iso: string | null | undefined): string {
  if (!iso) return "-";
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s} dtk lalu`;
  if (s < 3600) return `${Math.floor(s / 60)} mnt lalu`;
  if (s < 86400) return `${Math.floor(s / 3600)} jam lalu`;
  return `${Math.floor(s / 86400)} hari lalu`;
}
function size(b: number | null) {
  if (!b) return "-";
  return b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`;
}

export default function AlertsTab({ onUnauthorized }: { onUnauthorized: () => void }) {
  const [state, setState] = useState<"open" | "all">("open");
  const [cat, setCat] = useState<string>("");
  const [data, setData] = useState<AlertData | null>(null);
  const [backups, setBackups] = useState<BackupData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const call = useCallback(async <T,>(path: string, method = "GET"): Promise<T> => {
    const r = await fetch(`/api/admin/${path}`, { method, cache: "no-store" });
    if (r.status === 401) {
      onUnauthorized();
      throw new Error("Sesi admin habis.");
    }
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof body.detail === "string" ? body.detail : `Error ${r.status}`);
    return body as T;
  }, [onUnauthorized]);

  const load = useCallback(async () => {
    try {
      const [a, b] = await Promise.all([call<AlertData>(`alerts?state=${state}&limit=200`), call<BackupData>("backups?limit=8")]);
      setData(a);
      setBackups(b);
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [call, state]);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  const ack = async (path: string, key: string) => {
    setBusy(key);
    try {
      await call(path, "POST");
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const s = data?.summary;
  const list = (data?.alerts || []).filter((a) => !cat || a.category === cat);
  const lastOk = backups?.last_ok;
  const stale = !lastOk || (backups && backups.max_age_min > 0 && lastOk.age_min > backups.max_age_min);

  return (
    <div className="space-y-6">
      {err && <div className="rounded border border-red-500/50 bg-red-950/40 p-2 text-xs text-red-300">[ERROR]: {err}</div>}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="cyber-box p-3">
          <div className="text-[10px] uppercase text-zinc-500">Belum ditangani</div>
          <div className="text-2xl font-extrabold text-white">{s?.open ?? "..."}</div>
          <div className="text-[10px] text-zinc-500">
            <span className="text-red-300">{s?.critical ?? 0} critical</span> &bull; <span className="text-amber-300">{s?.warning ?? 0} warning</span> &bull;{" "}
            <span className="text-sky-300">{s?.info ?? 0} info</span>
          </div>
        </div>
        <div className="cyber-box p-3">
          <div className="text-[10px] uppercase text-zinc-500">Email ke admin</div>
          <div className={`text-sm font-bold ${data?.email.to ? "text-emerald-300" : "text-zinc-400"}`}>{data?.email.to ? "AKTIF" : "MATI (penerima kosong)"}</div>
          <div className="text-[10px] text-zinc-500">
            level &ge; {data?.email.min_level ?? "-"}, digabung tiap {data?.email.cooldown_min ?? "-"} mnt (critical: 2 mnt)
          </div>
        </div>
        <div className={`cyber-box p-3 sm:col-span-2 ${stale ? "border-red-600/60" : ""}`}>
          <div className="text-[10px] uppercase text-zinc-500">Backup database (otomatis tiap jam)</div>
          <div className={`text-sm font-bold ${stale ? "text-red-300" : "text-emerald-300"}`}>
            {lastOk ? `Terakhir berhasil ${ago(lastOk.at)}` : "Belum ada backup berhasil"}
          </div>
          <div className="mt-1 flex flex-wrap gap-1">
            {(backups?.backups || []).map((b) => (
              <span
                key={b.id}
                title={`${b.file || ""}\n${b.error || ""}${b.sha256 ? `\nsha256 ${b.sha256}` : ""}`}
                className={`rounded border px-1 py-0.5 text-[9px] ${b.ok ? (b.error ? "border-amber-800 text-amber-300" : "border-emerald-800 text-emerald-300") : "border-red-800 text-red-300"}`}
              >
                {new Date(b.at).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })} {b.ok ? size(b.bytes) : "GAGAL"}
                {b.copied ? " +luar" : ""}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1 text-[10px]">
          {(["open", "all"] as const).map((v) => (
            <button key={v} onClick={() => setState(v)} className={`${btn} ${state === v ? "border-cyber-amber text-cyber-amber-bright" : "border-cyber-border text-zinc-400"}`}>
              {v === "open" ? "BELUM DITANGANI" : "SEMUA"}
            </button>
          ))}
          <span className="mx-1 text-zinc-700">|</span>
          {["", "error", "suspicious", "branch", "backup", "node"].map((c) => (
            <button key={c || "x"} onClick={() => setCat(c)} className={`${btn} ${cat === c ? "border-cyber-amber text-cyber-amber-bright" : "border-cyber-border text-zinc-400"}`}>
              {c ? CATEGORY_LABEL[c] : "SEMUA JENIS"}
            </button>
          ))}
        </div>
        {!!s?.open && (
          <button disabled={busy === "all"} onClick={() => ack("alerts/ack-all", "all")} className={`${btn} border-emerald-700 bg-emerald-950/60 text-emerald-300 hover:bg-emerald-900/60`}>
            TANDAI SEMUA DITANGANI
          </button>
        )}
      </div>

      <div className="space-y-2">
        {list.length === 0 && (
          <p className="rounded border border-cyber-border p-4 text-center text-xs text-zinc-500">
            {state === "open" ? "Tidak ada peringatan yang belum ditangani." : "Belum ada peringatan."}
          </p>
        )}
        {list.map((a) => (
          <div key={a.id} className={`rounded border bg-black/30 p-3 ${a.acked_at ? "border-cyber-border opacity-60" : a.level === "critical" ? "border-red-700/70" : "border-cyber-border"}`}>
            <div className="flex flex-wrap items-start justify-between gap-2 sm:flex-nowrap">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className={`rounded border px-1.5 py-0.5 text-[10px] font-bold ${LEVEL_STYLE[a.level]}`}>{a.level.toUpperCase()}</span>
                  <span className="text-[10px] font-bold text-zinc-400">{CATEGORY_LABEL[a.category] || a.category}</span>
                  {a.count > 1 && <span className="text-[10px] text-zinc-400">x{a.count}</span>}
                  {a.emailed_at && <span className="text-[10px] text-zinc-500">&bull; email terkirim</span>}
                </div>
                <h3 className="mt-1 text-sm font-bold text-white">{a.title}</h3>
                {a.detail && <p className="mt-1 whitespace-pre-line break-words text-[11px] text-zinc-400">{a.detail}</p>}
                <p className="mt-1 text-[10px] text-zinc-600">
                  #{a.id} &bull; pertama {ago(a.created_at)}
                  {a.count > 1 ? ` • terakhir ${ago(a.last_at)}` : ""}
                  {Object.entries(a.ref || {})
                    .filter(([, v]) => v !== null && v !== "")
                    .map(([k, v]) => ` • ${k} ${Array.isArray(v) ? v.length : k === "sha" ? String(v).slice(0, 7) : v}`)
                    .join("")}
                  {a.acked_at ? ` • ditangani ${a.acked_by || ""} ${ago(a.acked_at)}` : ""}
                </p>
              </div>
              {!a.acked_at && (
                <button disabled={busy === String(a.id)} onClick={() => ack(`alerts/${a.id}/ack`, String(a.id))} className={`${btn} shrink-0 border-cyber-border text-zinc-200 hover:border-emerald-600 hover:text-emerald-300`}>
                  SUDAH DITANGANI
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      <details className="rounded border border-cyber-border p-3 text-[11px] text-zinc-400">
        <summary className="cursor-pointer font-bold text-zinc-300">Apa saja yang dipantau?</summary>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li><b>Error sistem:</b> CI berstatus error, CI branch main gagal, tugas invalid karena program terus gagal, publikasi hasil gagal, langkah validator gagal.</li>
          <li><b>Mencurigakan:</b> hasil worker beda dari mayoritas (quorum), worker sering beda dalam 24 jam, login admin dikunci, webhook dengan tanda tangan salah atau dari repo lain.</li>
          <li><b>Cek per branch repo B</b> (setiap push): commit di <code>task/&lt;id&gt;</code> harus oleh relawan pemilik jobdesk, push ke main harus hasil merge sistem, force push, branch dihapus, branch di luar aturan.</li>
          <li><b>Backup:</b> backup gagal, terlambat, atau salinan ke folder luar gagal.</li>
          <li><b>Compute node:</b> node mati di tengah tugas (info; tugasnya otomatis pindah ke node lain, jobdesk relawan tetap).</li>
        </ul>
      </details>
    </div>
  );
}
