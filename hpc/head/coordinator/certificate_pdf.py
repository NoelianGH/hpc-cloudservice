"""
Render sertifikat kontributor ke PDF dari template PNG.

Alur: sertifikat/template.png (desain, semua teks tetap) -> isi nama lengkap relawan, tanggal
terbit, dan nomor sertifikat sesuai sertifikat/layout.json -> simpan sebagai PDF satu halaman
A4 lanskap. Template dan layout bisa diganti tanpa mengubah kode (lihat sertifikat/buat_template.py).
Lokasi folder bisa diubah lewat env CERT_TEMPLATE_DIR.
"""
import io
import json
import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TEMPLATE_DIR = Path(os.environ.get("CERT_TEMPLATE_DIR") or Path(__file__).resolve().parent / "sertifikat")

BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
         "September", "Oktober", "November", "Desember"]


@lru_cache(maxsize=1)
def _layout() -> dict:
    return json.loads((TEMPLATE_DIR / "layout.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _template() -> Image.Image:
    with Image.open(TEMPLATE_DIR / _layout().get("template", "template.png")) as im:
        return im.convert("RGB")


@lru_cache(maxsize=64)
def _font(path: str, size: int, weight: int | None) -> ImageFont.FreeTypeFont:
    # Layout BASIC: hasil sama di mana pun (tidak bergantung libraqm/fribidi di image Docker)
    f = ImageFont.truetype(str(TEMPLATE_DIR / path), size, layout_engine=ImageFont.Layout.BASIC)
    if weight is not None:
        f.set_variation_by_axes([weight])
    return f


def tanggal_id(d: datetime) -> str:
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


def rapikan_nama(name: str) -> str:
    """Spasi dirapikan; nama yang seluruhnya huruf besar/kecil dijadikan Huruf Kapital Tiap Kata
    (huruf latin bersambung tidak cocok untuk HURUF BESAR SEMUA)."""
    name = " ".join((name or "").split())
    if name and (name.isupper() or name.islower()):
        name = " ".join(w[:1].upper() + w[1:].lower() for w in name.split(" "))
    return name


def _fit(draw: ImageDraw.ImageDraw, spec: dict, lines: list[str], size: int, min_size: int):
    """Ukuran font terbesar (<= size, >= min_size) agar semua baris muat di max_width."""
    weight = spec.get("weight")
    while True:
        f = _font(spec["font"], size, weight)
        if size <= min_size or all(draw.textlength(t, font=f) <= spec["max_width"] for t in lines):
            return f, size
        size -= 2


def _two_lines(text: str) -> list[str]:
    """Pecah di spasi yang paling dekat ke tengah (untuk nama yang sangat panjang)."""
    words = text.split(" ")
    if len(words) < 2:
        return [text]
    best = min(range(1, len(words)),
               key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))))
    return [" ".join(words[:best]), " ".join(words[best:])]


def _draw_field(draw: ImageDraw.ImageDraw, spec: dict, text: str) -> None:
    if not text:
        return
    size = int(spec["size"])
    min_size = int(spec.get("min_size", size))
    fill = spec.get("color", "#000000")
    x, y = spec["center_x"], spec["baseline_y"]
    f, size = _fit(draw, spec, [text], size, min_size)
    lines = [text]
    if draw.textlength(text, font=f) > spec["max_width"] and spec.get("wrap"):
        # Nama tidak dipotong: jadikan dua baris (baris bawah tetap di garis nama)
        lines = _two_lines(text)
        f, size = _fit(draw, spec, lines, int(spec.get("wrap_size", min_size)),
                       int(spec.get("wrap_min_size", min_size // 2)))
    if draw.textlength(lines[-1], font=f) > spec["max_width"] or (
            len(lines) > 1 and draw.textlength(lines[0], font=f) > spec["max_width"]):
        # teks tanpa spasi yang tetap kepanjangan: potong dengan elipsis
        lines = [ln if draw.textlength(ln, font=f) <= spec["max_width"] else _ellipsis(draw, ln, f, spec["max_width"])
                 for ln in lines]
    gap = size * 1.05
    for i, ln in enumerate(lines):
        draw.text((x, y - gap * (len(lines) - 1 - i)), ln, font=f, fill=fill, anchor="ms")


def _ellipsis(draw: ImageDraw.ImageDraw, text: str, f, max_width: float) -> str:
    while len(text) > 4 and draw.textlength(text + "…", font=f) > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def render_certificate(name: str, code: str, issued_at: datetime, verify_url: str | None = None,
                       fmt: str = "PDF") -> bytes:
    """Sertifikat berisi nama lengkap relawan. fmt "PDF" (bawaan) atau "PNG"."""
    lay = _layout()
    img = _template().copy()
    draw = ImageDraw.Draw(img)
    _draw_field(draw, lay["name"], rapikan_nama(name))
    _draw_field(draw, lay["date"], tanggal_id(issued_at))
    footer = f"No. Sertifikat {code}"
    if verify_url:
        footer += f"   ·   Verifikasi keaslian: {verify_url}"
    _draw_field(draw, lay["footer"], footer)

    buf = io.BytesIO()
    if fmt.upper() == "PNG":
        img.save(buf, "PNG", optimize=True)
    else:
        dpi = float(lay.get("dpi", 212.1))
        img.save(buf, "PDF", resolution=dpi, quality=92, title=f"Sertifikat Kontributor {code}",
                 author="IdleScale - Cloud Service HPC", subject=rapikan_nama(name),
                 creator="Koordinator Cloud Service HPC")
    return buf.getvalue()
