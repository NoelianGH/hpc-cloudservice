"use client";
import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";

type Cert = {
  valid: boolean; project: string; badge: string | null; code: string; worker_name: string;
  github_username: string | null; credits: number; tasks_validated: number; issued_at: string; updated_at: string;
};

/** Sertifikat kontributor yang bisa dicetak (Ctrl+P) dan diverifikasi publik lewat kodenya. */
export default function CertificatePage() {
  const params = useParams<{ code: string }>();
  const [cert, setCert] = useState<Cert | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/certificates/${encodeURIComponent(params.code)}`, { cache: "no-store" })
      .then(async (r) => {
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || "Sertifikat tidak ditemukan.");
        setCert(d);
      })
      .catch((e) => setError(e.message));
  }, [params.code]);

  if (error) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 font-mono text-xs">
        <div className="rounded border border-red-500/50 bg-red-950/40 p-4 text-red-300">
          [TIDAK VALID]: {error} Kode: {params.code}
        </div>
      </div>
    );
  }
  if (!cert) return <div className="px-4 py-16 font-mono text-xs text-zinc-400">Memeriksa sertifikat...</div>;

  const date = (s: string) => new Date(s).toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" });
  const url = typeof window !== "undefined" ? window.location.href : "";

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <div className="rounded-lg border-4 border-double border-amber-700 bg-white p-10 text-center text-zinc-900 shadow-2xl print:shadow-none">
        <div className="text-xs font-semibold uppercase tracking-[0.3em] text-amber-800">Sertifikat Kontributor</div>
        <div className="mt-1 text-sm text-zinc-600">{cert.project}</div>
        <div className="mt-8 text-sm text-zinc-600">Diberikan kepada</div>
        <div className="mt-2 text-3xl font-bold">{cert.worker_name}</div>
        {cert.github_username && <div className="mt-1 text-sm text-zinc-600">github.com/{cert.github_username}</div>}
        <p className="mx-auto mt-6 max-w-xl text-sm leading-relaxed text-zinc-700">
          atas kontribusi sumber daya komputasi sebagai relawan, dengan <b>{cert.credits} kredit</b> dari{" "}
          <b>{cert.tasks_validated} tugas</b> yang hasilnya tervalidasi melalui replikasi dan quorum
          {cert.badge ? <> (lencana <b>{cert.badge}</b>)</> : null}.
        </p>
        <div className="mt-8 text-xs text-zinc-500">
          Diterbitkan {date(cert.issued_at)}
          {cert.updated_at !== cert.issued_at && <> • diperbarui {date(cert.updated_at)}</>}
        </div>
        <div className="mt-4 font-mono text-sm font-bold tracking-wider">{cert.code}</div>
        <div className="mt-1 break-all text-[10px] text-zinc-400">Verifikasi: {url}</div>
        {!cert.valid && <div className="mt-4 text-sm font-bold text-red-600">Status: DICABUT (worker ditangguhkan)</div>}
      </div>
      <div className="mt-4 text-center font-mono text-xs print:hidden">
        <button onClick={() => window.print()} className="rounded border border-cyber-amber bg-cyber-amber px-4 py-2 font-bold text-cyber-void hover:bg-cyber-amber-bright">
          CETAK / SIMPAN PDF
        </button>
      </div>
    </div>
  );
}
