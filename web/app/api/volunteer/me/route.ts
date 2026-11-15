import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { coordinatorFetch } from "@/lib/admin";
import { WORKER_COOKIE } from "@/lib/volunteer";

export const dynamic = "force-dynamic";

/** Profil relawan yang sedang login: kredit, peringkat, lencana, progres sertifikat, riwayat tugas. */
export async function GET() {
  const token = cookies().get(WORKER_COOKIE)?.value;
  if (!token) return NextResponse.json({ detail: "Belum login." }, { status: 401 });
  const { status, data } = await coordinatorFetch("/api/me", { token });
  const res = NextResponse.json(data, { status });
  if (status === 401 || status === 403) {
    res.cookies.set(WORKER_COOKIE, "", { httpOnly: true, sameSite: "strict", path: "/", maxAge: 0 });
  }
  return res;
}
