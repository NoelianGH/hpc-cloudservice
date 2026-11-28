import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { COORDINATOR_URL, proxyHeaders } from "@/lib/admin";
import { WORKER_COOKIE, clearWorkerCookie } from "@/lib/volunteer";

export const dynamic = "force-dynamic";

/** Alamat publik situs ini (dipakai untuk tautan verifikasi yang dicetak di sertifikat). */
function siteOrigin(req: Request): string {
  const url = new URL(req.url);
  const host = req.headers.get("x-forwarded-host") || req.headers.get("host") || url.host;
  const proto = (req.headers.get("x-forwarded-proto") || url.protocol.replace(":", "")).split(",")[0].trim();
  return `${proto}://${host.split(",")[0].trim()}`;
}

const esc = (s: string) =>
  s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string);

/** Halaman HTML sederhana untuk tab baru bila sertifikat belum bisa dibuka. */
function infoPage(title: string, lines: string[], status: number) {
  const items = lines.map((l) => `<li>${esc(l)}</li>`).join("");
  const html = `<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>${esc(title)}</title>
<style>
  body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0b0d12;color:#e4e4e7;font-family:ui-monospace,Menlo,Consolas,monospace;padding:16px}
  .box{max-width:520px;width:100%;border:1px solid #f59e0b66;border-radius:12px;background:#111827;padding:24px}
  h1{font-size:16px;color:#fbbf24;margin:0 0 12px;letter-spacing:.05em;text-transform:uppercase}
  ul{font-size:13px;line-height:1.7;padding-left:18px;color:#a1a1aa}
  a{display:inline-block;margin-top:12px;border:1px solid #f59e0b;background:#f59e0b;color:#0b0d12;font-weight:700;font-size:12px;padding:8px 14px;border-radius:8px;text-decoration:none}
</style></head><body><div class="box"><h1>${esc(title)}</h1><ul>${items}</ul>
<a href="/dashboard">&larr; KEMBALI KE DASHBOARD</a></div></body></html>`;
  return new NextResponse(html, { status, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
}

/**
 * GET /api/volunteer/certificate/pdf[?download=1]
 * Sertifikat kontributor relawan sebagai PDF (dibuat koordinator dari template PNG + nama lengkap
 * registrasi). Dibuka dari tombol dashboard di tab baru; ?download=1 langsung mengunduh file.
 */
export async function GET(req: Request) {
  const token = (await cookies()).get(WORKER_COOKIE)?.value;
  if (!token) return NextResponse.redirect(new URL("/login", siteOrigin(req)));

  const download = new URL(req.url).searchParams.get("download") === "1";
  const qs = new URLSearchParams({ base: siteOrigin(req) });
  if (download) qs.set("download", "true");

  let r: Response;
  try {
    r = await fetch(`${COORDINATOR_URL}/api/me/certificate.pdf?${qs}`, {
      headers: { Authorization: `Bearer ${token}`, ...(await proxyHeaders()) },
      cache: "no-store",
    });
  } catch {
    return infoPage("Koordinator tidak dapat dihubungi", [`Coba lagi sebentar. (${COORDINATOR_URL})`], 502);
  }

  if (r.ok) {
    return new NextResponse(await r.arrayBuffer(), {
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": r.headers.get("content-disposition") || "inline; filename=\"Sertifikat.pdf\"",
        "Cache-Control": "private, no-store",
      },
    });
  }

  if (r.status === 401) {
    const res = NextResponse.redirect(new URL("/login?expired=1", siteOrigin(req)));
    clearWorkerCookie(res);
    return res;
  }
  const data: any = await r.json().catch(() => ({}));
  const det = data?.detail;
  if (r.status === 403 && det && typeof det === "object") {
    return infoPage(det.message || "Sertifikat belum tersedia", [
      `Poin Anda saat ini: ${det.credits ?? 0} dari ${det.min_credits ?? 50} poin.`,
      ...((det.missing as string[]) || []).map((m) => `Belum terpenuhi: ${m}`),
    ], 403);
  }
  return infoPage("Sertifikat belum bisa dibuka", [typeof det === "string" ? det : `Koordinator error (${r.status}).`], r.status);
}
