/**
 * Helper server-side untuk dashboard admin.
 * Token sesi admin disimpan di cookie httpOnly (tidak bisa dibaca JavaScript di browser),
 * lalu diteruskan ke koordinator sebagai header Authorization oleh route /api/admin/*.
 */
export const COORDINATOR_URL = process.env.COORDINATOR_URL || "http://localhost:8000";
export const ADMIN_COOKIE = "hpc_admin_session";

export function isHttps(req: Request): boolean {
  return (
    new URL(req.url).protocol === "https:" ||
    req.headers.get("x-forwarded-proto") === "https"
  );
}

/** Tolak POST lintas situs (lapisan tambahan selain cookie SameSite=Strict). */
export function sameOrigin(req: Request): boolean {
  const origin = req.headers.get("origin");
  if (!origin) return true; // permintaan non-browser / same-origin lama
  const host = req.headers.get("x-forwarded-host") || req.headers.get("host");
  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

export async function coordinatorFetch(
  path: string,
  init: { method?: string; body?: string | Record<string, unknown>; token?: string } = {}
): Promise<{ status: number; data: any }> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (init.token) headers["Authorization"] = `Bearer ${init.token}`;
  const rawBody = init.body == null ? undefined
    : typeof init.body === "string" ? init.body
    : JSON.stringify(init.body);
  try {
    const res = await fetch(`${COORDINATOR_URL}${path}`, {
      method: init.method || "GET",
      headers,
      body: rawBody,
      cache: "no-store",
    });
    const text = await res.text();
    let data: any;
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { detail: text || `Koordinator error (${res.status})` };
    }
    return { status: res.status, data };
  } catch {
    return {
      status: 502,
      data: {
        detail: `Koordinator (${COORDINATOR_URL}) tidak dapat dihubungi. Jalankan './hpc.sh head-up'.`,
      },
    };
  }
}
