import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { ADMIN_COOKIE, coordinatorFetch, sameOrigin } from "@/lib/admin";

export async function POST(req: Request) {
  if (!sameOrigin(req)) {
    return NextResponse.json({ detail: "Origin tidak diizinkan." }, { status: 403 });
  }
  const token = (await cookies()).get(ADMIN_COOKIE)?.value;
  if (token) {
    await coordinatorFetch("/api/admin/logout", { method: "POST", token });
  }
  const res = NextResponse.json({ ok: true });
  res.cookies.set(ADMIN_COOKIE, "", { httpOnly: true, sameSite: "strict", path: "/", maxAge: 0 });
  return res;
}
