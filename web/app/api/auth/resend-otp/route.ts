import { NextResponse } from "next/server";
import { resendOtpRequest } from "@/lib/coordinator";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { session_id } = body;

    if (!session_id) {
      return NextResponse.json(
        { detail: "session_id wajib diisi." },
        { status: 400 }
      );
    }

    const result = await resendOtpRequest({ session_id });
    return NextResponse.json(result);
  } catch (err: any) {
    return NextResponse.json(
      { detail: err.message || "Internal server error" },
      { status: 500 }
    );
  }
}

