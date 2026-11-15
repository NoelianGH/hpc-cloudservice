import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { coordinatorFetch, sameOrigin } from "@/lib/admin";
import { WORKER_COOKIE } from "@/lib/volunteer";

export const dynamic = "force-dynamic";

/** Terbitkan sertifikat kontributor (koordinator yang memeriksa syaratnya). */
export async function POST(req: Request) {
  if (!sameOrigin(req)) {
    return NextResponse.json({ detail: "Origin tidak diizinkan." }, { status: 403 });
  }
  const token = cookies().get(WORKER_COOKIE)?.value;
  if (!token) return NextResponse.json({ detail: "Belum login." }, { status: 401 });
  const { status, data } = await coordinatorFetch("/api/me/certificate", { method: "POST", token });
  return NextResponse.json(data, { status });
}
