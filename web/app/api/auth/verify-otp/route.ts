import { NextResponse } from "next/server";
import { verifyOtpRequest } from "@/lib/coordinator";
import { sameOrigin } from "@/lib/admin";

export async function POST(req: Request) {
  if (!sameOrigin(req)) return NextResponse.json({ detail: "Origin tidak diizinkan." }, { status: 403 });
  try {
    const body = await req.json();
    const { session_id, otp } = body;

    if (!session_id || !otp) {
      return NextResponse.json(
        { detail: "session_id dan otp wajib diisi." },
        { status: 400 }
      );
    }

    const result = await verifyOtpRequest({ session_id, otp });

    if (result.status === "error") {
      return NextResponse.json(result, { status: 400 });
    }

    // Token worker (hpc_w_) tidak pernah dikirim ke browser: website hanya memakai email + password.
    const { worker_token: _hidden, ...safe } = result as any;
    return NextResponse.json(safe);
  } catch (err: any) {
    return NextResponse.json(
      { detail: err.message || "Internal server error" },
      { status: 500 }
    );
  }
}

