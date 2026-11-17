import { NextResponse } from "next/server";
import { coordinatorFetch } from "@/lib/admin";

export const dynamic = "force-dynamic";

export async function GET(_req: Request, { params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  if (!/^HPC-[A-Fa-f0-9]{10}$/.test(code)) {
    return NextResponse.json({ detail: "Sertifikat tidak ditemukan." }, { status: 404 });
  }
  const { status, data } = await coordinatorFetch(`/api/certificates/${code.toUpperCase()}`);
  return NextResponse.json(data, { status });
}
