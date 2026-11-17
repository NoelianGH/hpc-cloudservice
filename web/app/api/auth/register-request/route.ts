import { NextResponse } from "next/server";
import { requestRegistration } from "@/lib/coordinator";
import { sameOrigin } from "@/lib/admin";

export async function POST(req: Request) {
  if (!sameOrigin(req)) return NextResponse.json({ detail: "Origin tidak diizinkan." }, { status: 403 });
  try {
    const body = await req.json();
    const { workerName, githubUsername, email, password, username, firstName, lastName } = body;

    const fullDisplayName = `${firstName || ""} ${lastName || ""}`.trim();
    const effectiveWorkerName = (workerName || fullDisplayName || `worker-${githubUsername}`).trim();

    if (!githubUsername || !email) {
      return NextResponse.json(
        { detail: "githubUsername dan email wajib diisi." },
        { status: 400 }
      );
    }
    // Password = satu-satunya cara login website.
    if (typeof password !== "string" || password.length < 8) {
      return NextResponse.json({ detail: "Password minimal 8 karakter." }, { status: 400 });
    }

    const result = await requestRegistration({
      worker_name: effectiveWorkerName,
      github_username: githubUsername,
      email,
      password,
      username: typeof username === "string" ? username.trim() : undefined,
      first_name: typeof firstName === "string" ? firstName.trim() : undefined,
      last_name: typeof lastName === "string" ? lastName.trim() : undefined,
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

