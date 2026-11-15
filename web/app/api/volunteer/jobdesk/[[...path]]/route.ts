/**
 * Proxy jobdesk relawan: /api/volunteer/jobdesk[/...] -> COORDINATOR_URL/api/me/jobdesk[/...]
 * Token worker diambil dari cookie httpOnly; koordinator yang memeriksa kepemilikan jobdesk.
 *   GET  /api/volunteer/jobdesk               jobdesk saya + CI branch saya
 *   POST /api/volunteer/jobdesk/<id>/submit   ajukan review (CI harus lulus; sistem membuka PR)
 * Jobdesk tidak diambil/dilepas relawan: sistem yang meng-assign (FIFO) dan memindahkan.
 */
import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { coordinatorFetch, sameOrigin } from "@/lib/admin";
import { WORKER_COOKIE } from "@/lib/volunteer";

export const dynamic = "force-dynamic";

const ALLOWED_POST = [/^\d{1,9}\/submit$/];

async function proxy(req: Request, path: string[] | undefined, method: "GET" | "POST") {
  const sub = (path || []).join("/");
  if (method === "GET" && sub) return NextResponse.json({ detail: "Path tidak valid." }, { status: 400 });
  if (method === "POST") {
    if (!ALLOWED_POST.some((r) => r.test(sub))) return NextResponse.json({ detail: "Path tidak valid." }, { status: 400 });
    if (!sameOrigin(req)) return NextResponse.json({ detail: "Origin tidak diizinkan." }, { status: 403 });
  }
  const token = cookies().get(WORKER_COOKIE)?.value;
  if (!token) return NextResponse.json({ detail: "Belum login." }, { status: 401 });
  const { status, data } = await coordinatorFetch(`/api/me/jobdesk${sub ? `/${sub}` : ""}`, { method, token });
  return NextResponse.json(data, { status });
}

export async function GET(req: Request, { params }: { params: { path?: string[] } }) {
  return proxy(req, params.path, "GET");
}

export async function POST(req: Request, { params }: { params: { path?: string[] } }) {
  return proxy(req, params.path, "POST");
}
