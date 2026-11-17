import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { coordinatorFetch, sameOrigin } from "@/lib/admin";
import { WORKER_COOKIE, clearWorkerCookie } from "@/lib/volunteer";

export const dynamic = "force-dynamic";

/** Logout: sesi dihapus di koordinator (tidak bisa dipakai lagi) dan cookie dibersihkan. */
export async function POST(req: Request) {
  if (!sameOrigin(req)) {
    return NextResponse.json({ detail: "Origin tidak diizinkan." }, { status: 403 });
  }
  const session = (await cookies()).get(WORKER_COOKIE)?.value;
  if (session) await coordinatorFetch("/api/auth/logout", { method: "POST", token: session });
  const res = NextResponse.json({ ok: true });
  clearWorkerCookie(res);
  return res;
}
