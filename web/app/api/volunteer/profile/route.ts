import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { coordinatorFetch, sameOrigin } from "@/lib/admin";
import { WORKER_COOKIE } from "@/lib/volunteer";

export const dynamic = "force-dynamic";

/** Update profil relawan (nama, email, github username). */
export async function POST(req: Request) {
  if (!sameOrigin(req)) return NextResponse.json({ detail: "Origin tidak diizinkan." }, { status: 403 });
  const session = (await cookies()).get(WORKER_COOKIE)?.value;
  if (!session) return NextResponse.json({ detail: "Belum login." }, { status: 401 });
  const body = await req.json().catch(() => ({}));
  const { status, data } = await coordinatorFetch("/api/me/profile", {
    method: "POST",
    token: session,
    body,
  });
  return NextResponse.json(data, { status });
}
