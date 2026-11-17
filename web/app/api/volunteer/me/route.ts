import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { coordinatorFetch } from "@/lib/admin";
import { WORKER_COOKIE, clearWorkerCookie } from "@/lib/volunteer";

export const dynamic = "force-dynamic";

/** Profil relawan yang sedang login: kredit, peringkat, lencana, progres sertifikat, riwayat tugas. */
export async function GET() {
  const session = cookies().get(WORKER_COOKIE)?.value;
  if (!session) return NextResponse.json({ detail: "Belum login." }, { status: 401 });

  const { status, data } = await coordinatorFetch("/api/me", { token: session });
  const res = NextResponse.json(
    status === 404 ? { detail: "Koordinator masih versi lama. Jalankan './hpc.sh head-up' untuk memuat update." } : data,
    { status }
  );
  if (status === 401 || status === 403) clearWorkerCookie(res);
  return res;
}
