import { NextResponse } from "next/server";
import { coordinatorFetch } from "@/lib/admin";

export const dynamic = "force-dynamic";

export async function GET(_req: Request, { params }: { params: { code: string } }) {
  if (!/^HPC-[A-Fa-f0-9]{10}$/.test(params.code)) {
    return NextResponse.json({ detail: "Sertifikat tidak ditemukan." }, { status: 404 });
  }
  const { status, data } = await coordinatorFetch(`/api/certificates/${params.code.toUpperCase()}`);
  return NextResponse.json(data, { status });
}
