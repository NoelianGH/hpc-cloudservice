import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { coordinatorFetch, sameOrigin } from "@/lib/admin";
import { WORKER_COOKIE } from "@/lib/volunteer";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  if (!sameOrigin(req)) return NextResponse.json({ detail: "Origin tidak diizinkan." }, { status: 403 });
  const token = (await cookies()).get(WORKER_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ detail: "Sesi relawan tidak ditemukan atau sudah berakhir." }, { status: 401 });
  }

  try {
    const body = await req.json();
    const consent = Boolean(body.consent);

    const { status, data } = await coordinatorFetch("/api/volunteer/appreciation-consent", {
      method: "POST",
      token,
      body: { consent },
    });

    return NextResponse.json(data, { status });
  } catch (err: any) {
    return NextResponse.json({ detail: err.message || "Gagal menyimpan persetujuan apresiasi." }, { status: 500 });
  }
}
