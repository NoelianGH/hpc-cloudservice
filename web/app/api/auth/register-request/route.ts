import { NextResponse } from "next/server";
import { requestRegistration } from "@/lib/coordinator";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { workerName, githubUsername, email } = body;

    if (!workerName || !githubUsername || !email) {
      return NextResponse.json(
        { detail: "workerName, githubUsername, dan email wajib diisi." },
        { status: 400 }
      );
    }

    const result = await requestRegistration({
      worker_name: workerName,
      github_username: githubUsername,
      email,
    });

    if (result.status === "error") {
      return NextResponse.json(result, { status: 400 });
    }

    return NextResponse.json(result);
  } catch (err: any) {
    return NextResponse.json(
      { detail: err.message || "Internal server error" },
      { status: 500 }
    );
  }
}

