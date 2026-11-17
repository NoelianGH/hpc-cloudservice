import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { coordinatorFetch } from "@/lib/admin";
import { WORKER_COOKIE, clearWorkerCookie } from "@/lib/volunteer";

export const dynamic = "force-dynamic";

/** Status login untuk navbar: { logged_in, username, github_username }. */
export async function GET() {
  const session = (await cookies()).get(WORKER_COOKIE)?.value;
  if (!session) return NextResponse.json({ logged_in: false });
  const { status, data } = await coordinatorFetch("/api/auth/session", { token: session });
  if (status === 200) {
    return NextResponse.json({
      logged_in: true,
      username: data.username || data.github_username || data.worker_name,
      github_username: data.github_username,
    });
  }
  const res = NextResponse.json({ logged_in: false });
  // Sesi habis / dicabut: bersihkan cookie. Koordinator mati: biarkan, sesi mungkin masih sah.
  if (status === 401 || status === 403) clearWorkerCookie(res);
  return res;
}
