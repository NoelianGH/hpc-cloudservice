import { NextResponse } from "next/server";
import { coordinatorFetch } from "@/lib/admin";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const { status, data } = await coordinatorFetch("/api/appreciation");

    if (status === 200 && data && Array.isArray(data.contributors)) {
      return NextResponse.json(data, { status: 200 });
    }

    // Jika koordinator mengembalikan 404 (kontainer belum di-rebuild via ./hpc.sh head-up),
    // kembalikan array kosong dengan status 200 agar UI tidak menampilkan banner merah
    if (status === 404) {
      return NextResponse.json({
        contributors: [],
        total: 0,
        notice: "Endpoint apresiasi belum aktif di kontainer koordinator. Jalankan './hpc.sh head-up' untuk memuat update.",
      }, { status: 200 });
    }

    // Jika koordinator offline / 502
    if (status >= 500) {
      return NextResponse.json({
        contributors: [],
        total: 0,
        error: data?.detail || "Koordinator backend offline.",
      }, { status: 200 });
    }

    return NextResponse.json(data || { contributors: [], total: 0 }, { status: 200 });
  } catch (err: any) {
    return NextResponse.json({
      contributors: [],
      total: 0,
      error: err.message,
    }, { status: 200 });
  }
}
