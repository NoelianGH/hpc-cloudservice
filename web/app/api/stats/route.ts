import { NextResponse } from "next/server";

const COORDINATOR_URL = process.env.COORDINATOR_URL || "http://localhost:8000";

export const dynamic = "force-dynamic";

/**
 * Statistik publik dari koordinator. Bila koordinator mati, kembalikan data KOSONG
 * dengan online=false (tidak ada lagi angka contoh/hardcoded yang bisa menyesatkan).
 */
export async function GET() {
  try {
    const res = await fetch(`${COORDINATOR_URL}/api/stats`, { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json({ online: true, coordinatorUrl: COORDINATOR_URL, ...data });
    }
  } catch {
    // koordinator tidak dapat dihubungi
  }
  return NextResponse.json({ online: false, coordinatorUrl: COORDINATOR_URL, tasks: {}, workers: [], jobs: [] });
}
