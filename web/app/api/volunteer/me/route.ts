import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { coordinatorFetch } from "@/lib/admin";
import { WORKER_COOKIE } from "@/lib/volunteer";

export const dynamic = "force-dynamic";

/** Profil relawan yang sedang login: kredit, peringkat, lencana, progres sertifikat, riwayat tugas. */
export async function GET() {
  const token = cookies().get(WORKER_COOKIE)?.value;
  if (!token) return NextResponse.json({ detail: "Belum login." }, { status: 401 });

  // 1. Coba endpoint utama /api/me
  const { status, data } = await coordinatorFetch("/api/me", { token });

  if (status === 200 && data?.worker) {
    return NextResponse.json(data, { status: 200 });
  }

  // 2. Jika 404 (kontainer koordinator masih menggunakan image lama yang belum memuat volunteer.py),
  // fallback ke endpoint /api/auth/me yang selalu tersedia di koordinator
  if (status === 404) {
    const authRes = await coordinatorFetch("/api/auth/me", { token });
    if (authRes.status === 200 && authRes.data?.verified) {
      const w = authRes.data;
      const fallbackData = {
        worker: {
          id: w.worker_id || "worker",
          name: w.worker_name || "Volunteer Node",
          github_username: w.github_username || null,
          email: w.email || null,
          status: w.status || "active",
          online: false,
          last_seen: new Date().toISOString(),
          show_in_appreciation: false,
        },
        stats: {
          credits: 0,
          rank: null,
          of: 1,
          badge: "Perintis",
          next_badge: { name: "Perunggu", credits: 25 },
          tasks_validated: 0,
          tasks_rejected: 0,
          tasks_expired: 0,
          reject_pct: 0,
          jobs_joined: 0,
          compute_seconds: 0,
        },
        certificate: {
          eligible: false,
          missing: ["Kredit minimal 50"],
          min_credits: 50,
          max_reject_pct: 10,
          progress_pct: 0,
          issued: null,
        },
        recent: [],
      };
      return NextResponse.json(fallbackData, { status: 200 });
    }
  }

  const res = NextResponse.json(data, { status });
  if (status === 401 || status === 403) {
    res.cookies.set(WORKER_COOKIE, "", { httpOnly: true, sameSite: "strict", path: "/", maxAge: 0 });
  }
  return res;
}
