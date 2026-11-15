import { NextResponse } from "next/server";
import { coordinatorFetch } from "@/lib/admin";

export const dynamic = "force-dynamic";

export async function GET() {
  const { status, data } = await coordinatorFetch("/api/leaderboard?limit=100");
  return NextResponse.json(data, { status });
}
