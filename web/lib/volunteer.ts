/**
 * Sesi relawan (worker) di web portal.
 *
 * Website  : relawan login dengan EMAIL + PASSWORD. Koordinator membuat sesi web (hpc_ws_...)
 *            yang disimpan di cookie httpOnly ini (tidak bisa dibaca JavaScript), lalu diteruskan
 *            ke koordinator sebagai Authorization: Bearer pada setiap request dashboard.
 * Token lain tidak dipakai di website: token node (hpc_ng_..., ssh + git per jobdesk) hanya
 *            ditampilkan di kartu jobdesk; token worker CPU (hpc_w_...) diatur admin lewat ./hpc.sh.
 */
import type { NextResponse } from "next/server";
import { isHttps } from "@/lib/admin";

export const WORKER_COOKIE = "hpc_worker_session";
// Samakan dengan WORKER_SESSION_DAYS koordinator (bawaan 7 hari)
export const WORKER_COOKIE_MAX_AGE = 60 * 60 * 24 * Number(process.env.WORKER_SESSION_DAYS || 7);

export function setWorkerCookie(res: NextResponse, req: Request, session: string) {
  res.cookies.set(WORKER_COOKIE, session, {
    httpOnly: true,
    // Lax: sesi tetap terbaca saat relawan membuka portal dari tautan (email OTP, GitHub, dll).
    // POST lintas situs tetap ditolak oleh pemeriksaan sameOrigin() di setiap route.
    sameSite: "lax",
    secure: isHttps(req),
    path: "/",
    maxAge: WORKER_COOKIE_MAX_AGE,
  });
}

export function clearWorkerCookie(res: NextResponse) {
  res.cookies.set(WORKER_COOKIE, "", { httpOnly: true, sameSite: "lax", path: "/", maxAge: 0 });
}
