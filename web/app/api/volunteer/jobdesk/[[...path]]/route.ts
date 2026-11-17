/**
 * Proxy jobdesk relawan: /api/volunteer/jobdesk[/...] -> COORDINATOR_URL/api/me/jobdesk[/...]
 * Sesi web diambil dari cookie httpOnly; koordinator yang memeriksa kepemilikan jobdesk.
 *   GET  /api/volunteer/jobdesk               jobdesk saya + CI branch saya
 *   POST /api/volunteer/jobdesk/take          ambil jobdesk berikutnya di antrean (FIFO, tidak memilih)
 *   POST /api/volunteer/jobdesk/<id>/submit   ajukan review (CI harus lulus; sistem membuka PR)
 *   POST /api/volunteer/jobdesk/<id>/node-code  ganti token node (password ssh + git) compute node
 */
import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { coordinatorFetch, sameOrigin } from "@/lib/admin";
import { WORKER_COOKIE } from "@/lib/volunteer";

export const dynamic = "force-dynamic";

const ALLOWED_POST = [/^take$/, /^\d{1,9}\/submit$/, /^\d{1,9}\/node-code$/];

async function proxy(req: Request, path: string[] | undefined, method: "GET" | "POST") {
  const sub = (path || []).join("/");
  if (method === "GET" && sub) return NextResponse.json({ detail: "Path tidak valid." }, { status: 400 });
  if (method === "POST") {
    if (!ALLOWED_POST.some((r) => r.test(sub))) return NextResponse.json({ detail: "Path tidak valid." }, { status: 400 });
    if (!sameOrigin(req)) return NextResponse.json({ detail: "Origin tidak diizinkan." }, { status: 403 });
  }
  const token = (await cookies()).get(WORKER_COOKIE)?.value;
  if (!token) return NextResponse.json({ detail: "Belum login." }, { status: 401 });
  const { status, data } = await coordinatorFetch(`/api/me/jobdesk${sub ? `/${sub}` : ""}`, { method, token });
  return NextResponse.json(data, { status });
}

export async function GET(req: Request, { params }: { params: Promise<{ path?: string[] }> }) {
  return proxy(req, (await params).path, "GET");
}

export async function POST(req: Request, { params }: { params: Promise<{ path?: string[] }> }) {
  return proxy(req, (await params).path, "POST");
}
