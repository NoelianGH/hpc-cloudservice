/**
 * Proxy aman ke API admin koordinator: /api/admin/<path> -> COORDINATOR_URL/api/admin/<path>.
 * Token sesi diambil dari cookie httpOnly; koordinator yang memvalidasi sesi di setiap request.
 */
import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { ADMIN_COOKIE, coordinatorFetch, sameOrigin } from "@/lib/admin";

export const dynamic = "force-dynamic";

const SEGMENT = /^[A-Za-z0-9_-]+$/;

async function proxy(req: Request, path: string[], method: "GET" | "POST") {
  if (!path.every((p) => SEGMENT.test(p))) {
    return NextResponse.json({ detail: "Path tidak valid." }, { status: 400 });
  }
  if (method === "POST" && !sameOrigin(req)) {
    return NextResponse.json({ detail: "Origin tidak diizinkan." }, { status: 403 });
  }
  const token = (await cookies()).get(ADMIN_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ detail: "Belum login sebagai admin." }, { status: 401 });
  }
  const search = new URL(req.url).search;
  const body = method === "POST" ? await req.text() : undefined;
  const { status, data } = await coordinatorFetch(`/api/admin/${path.join("/")}${search}`, {
    method,
    body: body || undefined,
    token,
  });
  const res = NextResponse.json(data, { status });
  if (status === 401) {
    // Sesi habis / dicabut: hapus cookie agar diarahkan ke halaman login
    res.cookies.set(ADMIN_COOKIE, "", { httpOnly: true, sameSite: "strict", path: "/", maxAge: 0 });
  }
  return res;
}

export async function GET(req: Request, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, (await params).path, "GET");
}

export async function POST(req: Request, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(req, (await params).path, "POST");
}
