import { NextResponse } from "next/server";
import { coordinatorFetch } from "@/lib/admin";

export const dynamic = "force-dynamic";

export async function GET() {
  const { status, data } = await coordinatorFetch("/api/jobs?limit=20");
  return NextResponse.json(data, { status });
}
