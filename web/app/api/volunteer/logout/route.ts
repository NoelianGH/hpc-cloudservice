import { NextResponse } from "next/server";
import { WORKER_COOKIE } from "@/lib/volunteer";

export async function POST() {
  const res = NextResponse.json({ ok: true });
  res.cookies.set(WORKER_COOKIE, "", { httpOnly: true, sameSite: "strict", path: "/", maxAge: 0 });
  return res;
}
