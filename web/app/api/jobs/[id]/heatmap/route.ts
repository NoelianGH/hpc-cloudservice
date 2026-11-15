import { COORDINATOR_URL } from "@/lib/admin";

export const dynamic = "force-dynamic";

/** Gambar heatmap hasil akhir job heat2d (PNG dibuat koordinator). */
export async function GET(_req: Request, { params }: { params: { id: string } }) {
  if (!/^\d{1,9}$/.test(params.id)) return new Response("Not found", { status: 404 });
  try {
    const r = await fetch(`${COORDINATOR_URL}/api/jobs/${params.id}/heatmap.png`, { cache: "no-store" });
    if (!r.ok) return new Response("Heatmap belum tersedia", { status: r.status });
    return new Response(await r.arrayBuffer(), {
      headers: { "Content-Type": "image/png", "Cache-Control": "public, max-age=300" },
    });
  } catch {
    return new Response("Koordinator tidak dapat dihubungi", { status: 502 });
  }
}
