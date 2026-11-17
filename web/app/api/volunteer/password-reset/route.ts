import { NextResponse } from "next/server";
import { coordinatorFetch, sameOrigin } from "@/lib/admin";

export const dynamic = "force-dynamic";

/**
 * Atur / atur ulang password website lewat kode OTP email (akun lama tanpa password, atau lupa).
 *   { action: "request", email }                 -> koordinator mengirim kode ke email
 *   { action: "reset", email, otp, password }    -> password baru, semua sesi lama keluar
 * Kode OTP tidak pernah dikirim balik ke browser.
 */
export async function POST(req: Request) {
  if (!sameOrigin(req)) {
    return NextResponse.json({ detail: "Origin tidak diizinkan." }, { status: 403 });
  }
  const body = await req.json().catch(() => ({} as any));
  const email = String(body.email || "").trim();
  if (!email) return NextResponse.json({ detail: "Email wajib diisi." }, { status: 400 });

  if (body.action === "request") {
    const { status, data } = await coordinatorFetch("/api/auth/password/request", { method: "POST", body: { email } });
    return NextResponse.json({ ok: data?.ok, message: data?.message, detail: data?.detail }, { status });
  }
  if (body.action === "reset") {
    const otp = String(body.otp || "").trim();
    const password = String(body.password || "");
    if (!/^\d{6}$/.test(otp)) return NextResponse.json({ detail: "Kode OTP 6 angka." }, { status: 400 });
    const { status, data } = await coordinatorFetch("/api/auth/password/reset", {
      method: "POST",
      body: { email, otp, password },
    });
    return NextResponse.json(data, { status });
  }
  return NextResponse.json({ detail: "action harus 'request' atau 'reset'." }, { status: 400 });
}
