import { NextResponse, type NextRequest } from "next/server";

const ADMIN_COOKIE = "hpc_admin_session";
const WORKER_COOKIE = "hpc_worker_session";

/**
 * - /admin hanya untuk admin yang sudah login.
 * - /dashboard hanya untuk relawan yang sudah login dengan token worker.
 * Middleware hanya mengecek keberadaan cookie; keabsahan sesi/token tetap dicek
 * koordinator pada setiap panggilan API.
 */
export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  if (pathname === "/admin/login") {
    return NextResponse.next();
  }
  if (pathname.startsWith("/dashboard")) {
    if (!req.cookies.get(WORKER_COOKIE)?.value) {
      const url = req.nextUrl.clone();
      url.pathname = "/login";
      url.search = "";
      return NextResponse.redirect(url);
    }
    return NextResponse.next();
  }
  if (!req.cookies.get(ADMIN_COOKIE)?.value) {
    const url = req.nextUrl.clone();
    url.pathname = "/admin/login";
    url.search = "";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/admin", "/admin/:path*", "/dashboard", "/dashboard/:path*"],
};
