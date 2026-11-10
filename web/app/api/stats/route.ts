import { NextResponse } from "next/server";

const COORDINATOR_URL = process.env.COORDINATOR_URL || "http://localhost:8000";

export async function GET() {
  try {
    const res = await fetch(`${COORDINATOR_URL}/api/stats`, {
      cache: "no-store",
    });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json({
        online: true,
        coordinatorUrl: COORDINATOR_URL,
        ...data,
      });
    }
  } catch (err) {
    // coordinator offline fallback telemetry
  }

  return NextResponse.json({
    online: false,
    coordinatorUrl: COORDINATOR_URL,
    tasks: { pending: 14, done: 46, invalid: 0 },
    workers: [
      { id: "w-alpha9", name: "node-titan-x", github_username: "cyber-contributor", credits: 128, online: true, running: 2, status: "active" },
      { id: "w-beta4", name: "ryzen-worker-01", github_username: "hpc-fanatic", credits: 84, online: true, running: 1, status: "active" },
    ],
    jobs: [
      { id: 104, kind: "montecarlo_pi", total: 20, done: 20, seconds: 14.2, pi: 3.141592 },
      { id: 105, kind: "mandelbrot", total: 20, done: 12, seconds: 9.8 },
    ],
  });
}

