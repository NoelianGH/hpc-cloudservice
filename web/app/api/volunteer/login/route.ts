import { NextResponse } from "next/server";
import { coordinatorFetch, isHttps, sameOrigin } from "@/lib/admin";
import { WORKER_COOKIE, WORKER_COOKIE_MAX_AGE } from "@/lib/volunteer";

export const dynamic = "force-dynamic";

/** Login relawan dengan WORKER_TOKEN: token DICEK ke koordinator sebelum sesi dibuat. */
export async function POST(req: Request) {
  if (!sameOrigin(req)) {
    return NextResponse.json({ detail: "Origin tidak diizinkan." }, { status: 403 });
  }
  let token = "";
  try {
    token = String((await req.json()).token || "").trim();
  } catch {
    /* body kosong */
  }
  if (!/^hpc_w_[A-Za-z0-9]{16,64}$/.test(token)) {
    return NextResponse.json(
      { detail: "Format token tidak valid. Token relawan diawali 'hpc_w_' (didapat dari Register atau ./hpc.sh worker-login)." },
      { status: 400 }
    );
  }
  const { status, data } = await coordinatorFetch("/api/auth/me", { token });
  if (status !== 200 || data?.type !== "individual") {
    const detail =
      status === 403
        ? data?.detail || "Worker ditangguhkan admin."
        : status === 502
          ? data?.detail
          : "Token tidak dikenal koordinator atau sudah dicabut. Daftar ulang / jalankan ./hpc.sh worker-login.";
    return NextResponse.json({ detail }, { status: status === 502 ? 502 : 401 });
  }
  const res = NextResponse.json({ ok: true, worker: data });
  res.cookies.set(WORKER_COOKIE, token, {
    httpOnly: true,
    sameSite: "strict",
    secure: isHttps(req),
    path: "/",
    maxAge: WORKER_COOKIE_MAX_AGE,
  });
  return res;
}
