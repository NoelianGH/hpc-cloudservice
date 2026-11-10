import { NextResponse } from "next/server";
import { verifyOtpRequest } from "@/lib/coordinator";

export async function POST(req: Request) {
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

    return NextResponse.json(result);
  } catch (err: any) {
    return NextResponse.json(
      { detail: err.message || "Internal server error" },
      { status: 500 }
    );
  }
}

