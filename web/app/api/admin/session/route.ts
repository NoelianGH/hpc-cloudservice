import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { ADMIN_COOKIE, coordinatorFetch } from "@/lib/admin";

export const dynamic = "force-dynamic";

/** Status login admin untuk navbar: { logged_in }. Selalu 200 agar tidak ada error 401 di konsol. */
export async function GET() {
  const token = cookies().get(ADMIN_COOKIE)?.value;
  if (!token) return NextResponse.json({ logged_in: false });
  const { status } = await coordinatorFetch("/api/admin/me", { token });
  const res = NextResponse.json({ logged_in: status === 200 });
  if (status === 401) {
    res.cookies.set(ADMIN_COOKIE, "", { httpOnly: true, sameSite: "strict", path: "/", maxAge: 0 });
  }
  return res;
}
