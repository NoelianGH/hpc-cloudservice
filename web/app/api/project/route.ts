import { NextResponse } from "next/server";
import { coordinatorFetch } from "@/lib/admin";

export const dynamic = "force-dynamic";

/** Info publik proyek: repo worker (repo B) dan alamat koordinator untuk worker relawan. */
export async function GET() {
  const { status, data } = await coordinatorFetch("/api/project");
  return NextResponse.json(status === 200 ? data : { project: null, detail: data?.detail }, { status: 200 });
}
