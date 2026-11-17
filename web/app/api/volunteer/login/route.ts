import { NextResponse } from "next/server";
import { coordinatorFetch, sameOrigin } from "@/lib/admin";
import { setWorkerCookie } from "@/lib/volunteer";

export const dynamic = "force-dynamic";

/**
 * Login website relawan.
 *   { email, password }  cara utama
 *   { token }            sekali saja, untuk akun lama dari './hpc.sh worker-login' yang belum punya password
 * Koordinator mengembalikan token SESI web (bukan token worker); hanya sesi itu yang masuk cookie.
 */
export async function POST(req: Request) {
  if (!sameOrigin(req)) {
    return NextResponse.json({ detail: "Origin tidak diizinkan." }, { status: 403 });
  }
  let body: any = {};
  try {
    body = await req.json();
  } catch {
    /* body kosong */
  }
  const email = String(body.email || "").trim();
  const password = String(body.password || "");
  const token = String(body.token || "").trim();

  let payload: Record<string, string>;
  if (token) {
    if (!/^hpc_w_[A-Za-z0-9]{16,64}$/.test(token)) {
      return NextResponse.json({ detail: "Format token tidak valid. Token worker diawali 'hpc_w_'." }, { status: 400 });
    }
    payload = { token };
  } else {
    if (!email || !password) {
      return NextResponse.json({ detail: "Email dan password wajib diisi." }, { status: 400 });
    }
    payload = { email, password };
  }

  const { status, data } = await coordinatorFetch("/api/auth/login", { method: "POST", body: payload });
  if (status === 404) {
    // Koordinator yang berjalan belum memuat modul login web (image Docker lama)
    return NextResponse.json(
      { detail: "Koordinator masih versi lama (belum ada login web). Jalankan './hpc.sh head-up' lalu coba lagi." },
      { status: 503 }
    );
  }
  if (status !== 200 || !data?.session) {
    return NextResponse.json({ detail: data?.detail || "Login ditolak koordinator." }, { status: status === 200 ? 502 : status });
  }
  const res = NextResponse.json({
    ok: true,
    worker_name: data.worker_name,
    github_username: data.github_username,
    has_password: data.has_password,
  });
  setWorkerCookie(res, req, data.session);
  return res;
}
