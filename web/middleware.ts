import { NextResponse, type NextRequest } from "next/server";

const ADMIN_COOKIE = "hpc_admin_session";
const WORKER_COOKIE = "hpc_worker_session";
const COORDINATOR_URL = process.env.COORDINATOR_URL || "http://localhost:8000";

/** 200 = sesi admin sah, 401 = tidak sah, 0 = koordinator tidak bisa dihubungi. */
async function adminSessionStatus(token: string): Promise<number> {
  try {
    const res = await fetch(`${COORDINATOR_URL}/api/admin/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    return res.status === 200 ? 200 : res.status >= 500 ? 0 : 401;
  } catch {
    return 0;
  }
}

function toAdminLogin(req: NextRequest, clearCookie: boolean) {
  const res = go(req, "/admin/login");
  if (clearCookie) res.cookies.set(ADMIN_COOKIE, "", { httpOnly: true, sameSite: "strict", path: "/", maxAge: 0 });
  return res;
}

function go(req: NextRequest, pathname: string) {
  const url = req.nextUrl.clone();
  url.pathname = pathname;
  url.search = "";
  return NextResponse.redirect(url);
}

/**
 * - /admin hanya untuk admin yang sudah login.
 * - /dashboard hanya untuk relawan yang sudah login (sesi web email + password).
 * - /login dan /register langsung ke /dashboard bila relawan masih punya sesi, jadi tidak
 *   perlu login ulang setiap kali kembali ke portal.
 * - /admin: sesi admin DIVERIFIKASI ke koordinator (GET /api/admin/me) di setiap akses, bukan
 *   sekadar ada cookie. Tanpa sesi sah (tidak ada, habis, dicabut, atau email admin diganti lewat
 *   './hpc.sh admin-setup') langsung ke /admin/login dan cookie palsu/basi dihapus. Bila koordinator
 *   tidak bisa dihubungi, akses juga ditolak (fail closed). /admin/login langsung ke /admin bila
 *   sesi admin masih sah.
 * Untuk relawan, middleware hanya mengecek keberadaan cookie; keabsahan sesi tetap dicek koordinator pada
 * setiap panggilan API. Sesi yang ternyata habis membuat cookie dihapus lalu diarahkan ke
 * /login?expired=1 (tanpa redirect balik, jadi tidak ada loop).
 */
export async function middleware(req: NextRequest) {
  const { pathname, searchParams } = req.nextUrl;
  const hasWorker = Boolean(req.cookies.get(WORKER_COOKIE)?.value);

  if (pathname === "/login" || pathname === "/register") {
    return hasWorker && !searchParams.has("expired") ? go(req, "/dashboard") : NextResponse.next();
  }
  if (pathname.startsWith("/dashboard")) {
    return hasWorker ? NextResponse.next() : go(req, "/login");
  }

  // ---- /admin dan /admin/login ----
  const adminToken = req.cookies.get(ADMIN_COOKIE)?.value;
  if (pathname === "/admin/login") {
    if (adminToken) {
      const st = await adminSessionStatus(adminToken);
      if (st === 200) return go(req, "/admin");
      if (st === 401) {
        const res = NextResponse.next();
        res.cookies.set(ADMIN_COOKIE, "", { httpOnly: true, sameSite: "strict", path: "/", maxAge: 0 });
        return res;
      }
    }
    return NextResponse.next();
  }
  if (!adminToken) return toAdminLogin(req, false);
  const st = await adminSessionStatus(adminToken);
  if (st === 200) return NextResponse.next();
  return toAdminLogin(req, st === 401);
}

export const config = {
  matcher: ["/admin", "/admin/:path*", "/dashboard", "/dashboard/:path*", "/login", "/register"],
};
