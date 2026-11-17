import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { coordinatorFetch, sameOrigin } from "@/lib/admin";
import { WORKER_COOKIE } from "@/lib/volunteer";

export const dynamic = "force-dynamic";

/**
 * Token worker untuk CLI (.env repo worker), hanya untuk pemilik sesi web.
 *   GET   tampilkan token
 *   POST  buat token baru (token lama langsung tidak berlaku)
 */
export async function GET() {
  const session = cookies().get(WORKER_COOKIE)?.value;
  if (!session) return NextResponse.json({ detail: "Belum login." }, { status: 401 });
  const { status, data } = await coordinatorFetch("/api/me/cli-token", { token: session });
  return NextResponse.json(data, { status, headers: { "Cache-Control": "no-store" } });
}

export async function POST(req: Request) {
  if (!sameOrigin(req)) return NextResponse.json({ detail: "Origin tidak diizinkan." }, { status: 403 });
  const session = cookies().get(WORKER_COOKIE)?.value;
  if (!session) return NextResponse.json({ detail: "Belum login." }, { status: 401 });
  const { status, data } = await coordinatorFetch("/api/me/cli-token/rotate", { method: "POST", token: session });
  return NextResponse.json(data, { status, headers: { "Cache-Control": "no-store" } });
}
