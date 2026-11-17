import { NextResponse } from "next/server";
import { requestRegistration } from "@/lib/coordinator";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { workerName, githubUsername, email, password, username } = body;

    if (!workerName || !githubUsername || !email) {
      return NextResponse.json(
        { detail: "workerName, githubUsername, dan email wajib diisi." },
        { status: 400 }
      );
    }
    // Password dipakai untuk login website; token worker tetap untuk CLI.
    if (typeof password !== "string" || password.length < 8) {
      return NextResponse.json({ detail: "Password minimal 8 karakter." }, { status: 400 });
    }

    const result = await requestRegistration({
      worker_name: workerName,
      github_username: githubUsername,
      email,
      password,
      username: typeof username === "string" ? username.trim() : undefined,
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

