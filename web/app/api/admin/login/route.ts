import { NextResponse } from "next/server";
import { ADMIN_COOKIE, coordinatorFetch, isHttps, sameOrigin } from "@/lib/admin";

export async function POST(req: Request) {
  if (!sameOrigin(req)) {
    return NextResponse.json({ detail: "Origin tidak diizinkan." }, { status: 403 });
  }
  let body: any;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ detail: "Body JSON tidak valid." }, { status: 400 });
  }
  const email = String(body?.email || "").trim();
  const password = String(body?.password || "");
  if (!email || !password) {
    return NextResponse.json({ detail: "Email dan password wajib diisi." }, { status: 400 });
  }

  const { status, data } = await coordinatorFetch("/api/admin/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  if (status !== 200 || !data?.token) {
    return NextResponse.json({ detail: data?.detail || "Login gagal." }, { status: status === 200 ? 502 : status });
  }

  const res = NextResponse.json({ ok: true, email: data.email, expires_at: data.expires_at });
  res.cookies.set(ADMIN_COOKIE, data.token, {
    httpOnly: true,
    sameSite: "strict",
    secure: isHttps(req),
    path: "/",
    expires: new Date(data.expires_at),
  });
  return res;
}
