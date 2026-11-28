"""
Pembuat template sertifikat (template.png) untuk sertifikat kontributor relawan.

Template ini adalah gambar PNG A4 lanskap (2480 x 1754 px, ±212 dpi) berisi semua teks tetap.
Bagian yang dikosongkan (nama, tanggal terbit, nomor sertifikat) diisi koordinator saat relawan
membuka sertifikatnya, lalu dijadikan PDF (lihat ../certificate_pdf.py). Posisi isian ada di
layout.json.

Template boleh diganti dengan desain sendiri (mis. dari Canva): ekspor PNG berukuran sama,
kosongkan area nama / tanggal / nomor, simpan sebagai template.png, lalu sesuaikan layout.json
bila posisinya berubah. Skrip ini hanya perlu dijalankan lagi bila ingin membuat ulang desain bawaan:

    pip install pillow
    python buat_template.py            # menimpa template.png di folder ini
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
FONTS = HERE / "fonts"

W, H = 2480, 1754
CX = W // 2

CREAM = (250, 246, 236)
NAVY = (19, 34, 63)
GOLD = (176, 132, 52)
GOLD_LIGHT = (214, 178, 106)
INK = (64, 70, 84)
MUTED = (120, 118, 110)


def font(name: str, size: int, weight: int | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONTS / name), size, layout_engine=ImageFont.Layout.BASIC)
    if weight is not None:
        f.set_variation_by_axes([weight])
    return f


def spaced(draw: ImageDraw.ImageDraw, xy, text: str, f, fill, spacing: int, anchor_x="center"):
    """Teks dengan jarak antarhuruf (letter-spacing), rata tengah pada x."""
    widths = [draw.textlength(ch, font=f) for ch in text]
    total = sum(widths) + spacing * (len(text) - 1)
    x = xy[0] - total / 2 if anchor_x == "center" else xy[0]
    for ch, w in zip(text, widths):
        draw.text((x, xy[1]), ch, font=f, fill=fill, anchor="ls")
        x += w + spacing
    return total


def diamond(draw, cx, cy, r, fill):
    draw.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=fill)


def background(img: Image.Image) -> None:
    """Latar krem dengan pola heksagon samar (kesan jaringan / komputasi)."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    r = 46
    dx, dy = r * math.sqrt(3), r * 1.5
    row = 0
    y = 0.0
    while y < H + r:
        x = (dx / 2 if row % 2 else 0.0)
        while x < W + r:
            pts = [(x + r * math.cos(math.radians(a)), y + r * math.sin(math.radians(a)))
                   for a in range(30, 390, 60)]
            d.line(pts, fill=GOLD + (18,), width=2)
            x += dx
        y += dy
        row += 1
    # pudarkan pola di tengah supaya teks tetap bersih
    mask = Image.new("L", img.size, 255)
    md = ImageDraw.Draw(mask)
    md.ellipse([CX - 1050, H // 2 - 620, CX + 1050, H // 2 + 620], fill=0)
    mask = mask.filter(ImageFilter.GaussianBlur(160))
    layer.putalpha(Image.composite(layer.getchannel("A"), Image.new("L", img.size, 0), mask))
    img.alpha_composite(layer)


def frame(d: ImageDraw.ImageDraw) -> None:
    # pita navy di tepi, garis emas tebal + tipis di dalamnya
    d.rectangle([0, 0, W - 1, H - 1], outline=NAVY, width=56)
    d.rectangle([80, 80, W - 81, H - 81], outline=GOLD, width=6)
    d.rectangle([98, 98, W - 99, H - 99], outline=GOLD_LIGHT, width=2)

    # ornamen sudut bermotif jalur sirkuit
    for sx, sy in [(1, 1), (-1, 1), (1, -1), (-1, -1)]:
        ox = 98 if sx > 0 else W - 99
        oy = 98 if sy > 0 else H - 99
        p = lambda x, y: (ox + sx * x, oy + sy * y)  # noqa: E731
        for off, length, node in [(36, 280, 10), (66, 200, 8), (96, 130, 7)]:
            d.line([p(off, length), p(off, off), p(length, off)], fill=GOLD, width=4, joint="curve")
            for cx, cy in (p(length, off), p(off, length)):
                d.ellipse([cx - node, cy - node, cx + node, cy + node], outline=GOLD, width=4, fill=CREAM)
        diamond(d, *p(36, 36), 13, GOLD)


def logo(d: ImageDraw.ImageDraw, cx: int, cy: int, r: int) -> None:
    """Heksagon dengan tiga simpul terhubung: lambang node komputasi."""
    pts = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in range(-90, 270, 60)]
    d.polygon(pts, outline=NAVY, width=6, fill=CREAM)
    nodes = [(cx, cy - r * 0.42), (cx - r * 0.40, cy + r * 0.28), (cx + r * 0.40, cy + r * 0.28)]
    for a in nodes:
        for b in nodes:
            d.line([a, b], fill=GOLD, width=5)
    for x, y in nodes:
        d.ellipse([x - 11, y - 11, x + 11, y + 11], fill=NAVY)


def seal(img: Image.Image, cx: int, cy: int) -> None:
    """Segel emas dengan pita di bawahnya."""
    d = ImageDraw.Draw(img)
    # pita
    for side in (-1, 1):
        x0 = cx + side * 40
        d.polygon([(x0 - 38, cy + 60), (x0 + 38, cy + 60), (x0 + 38 + side * 30, cy + 215),
                   (x0 + side * 22, cy + 180), (x0 - 38 + side * 30, cy + 215)], fill=NAVY)
    # gerigi luar
    teeth = 36
    outer, inner = 150, 136
    pts = []
    for i in range(teeth * 2):
        rr = outer if i % 2 == 0 else inner
        a = math.pi * i / teeth
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=GOLD)
    d.ellipse([cx - 122, cy - 122, cx + 122, cy + 122], fill=GOLD_LIGHT, outline=CREAM, width=4)
    d.ellipse([cx - 104, cy - 104, cx + 104, cy + 104], outline=GOLD, width=3)
    f1 = font("Cinzel-Variable.ttf", 30, 700)
    f2 = font("Cinzel-Variable.ttf", 21, 700)
    spaced(d, (cx, cy - 22), "VERIFIED", f1, NAVY, 4)
    diamond(d, cx, cy + 2, 9, NAVY)
    d.line([(cx - 70, cy + 2), (cx - 18, cy + 2)], fill=NAVY, width=3)
    d.line([(cx + 18, cy + 2), (cx + 70, cy + 2)], fill=NAVY, width=3)
    spaced(d, (cx, cy + 46), "CONTRIBUTOR", f2, NAVY, 2)


def build() -> Image.Image:
    img = Image.new("RGBA", (W, H), CREAM + (255,))
    background(img)
    d = ImageDraw.Draw(img)
    frame(d)

    # kepala: lambang + nama platform
    logo(d, CX, 232, 62)
    spaced(d, (CX, 368), "IDLESCALE  ·  CLOUD SERVICE HPC", font("Cinzel-Variable.ttf", 34, 600), GOLD, 9)

    # judul
    spaced(d, (CX, 545), "SERTIFIKAT", font("Cinzel-Variable.ttf", 150, 800), NAVY, 22)
    sub = font("Cinzel-Variable.ttf", 46, 600)
    tw = spaced(d, (CX, 635), "KONTRIBUTOR RELAWAN", sub, GOLD, 12)
    for side in (-1, 1):
        x_in = CX + side * (tw / 2 + 40)
        x_out = CX + side * (tw / 2 + 240)
        d.line([(x_in, 620), (x_out, 620)], fill=GOLD, width=3)
        diamond(d, x_in, 620, 8, GOLD)

    d.text((CX, 745), "Diberikan dengan hormat kepada", font=font("Lora-Italic-Variable.ttf", 46, 400),
           fill=INK, anchor="ms")

    # area nama (diisi koordinator): garis bawah emas
    d.line([(CX - 760, 975), (CX + 760, 975)], fill=GOLD, width=4)
    diamond(d, CX, 975, 13, GOLD)
    diamond(d, CX - 760, 975, 7, GOLD)
    diamond(d, CX + 760, 975, 7, GOLD)

    body = font("Lora-Variable.ttf", 38, 400)
    lines = [
        "atas dedikasi dan kontribusinya sebagai relawan pengembang serta penyedia daya komputasi",
        "pada platform volunteer computing IdleScale, dan telah memenuhi batas poin kontribusi",
        "yang dipersyaratkan untuk memperoleh sertifikat ini.",
    ]
    for i, line in enumerate(lines):
        d.text((CX, 1080 + i * 58), line, font=body, fill=INK, anchor="ms")

    # tanda tangan & tanggal
    label = font("Lora-Variable.ttf", 32, 600)
    small = font("Lora-Italic-Variable.ttf", 28, 400)
    for x, title, note in [(620, "Tanggal Terbit", None),
                           (1860, "Koordinator Platform", "IdleScale  ·  Cloud Service HPC")]:
        d.line([(x - 270, 1445), (x + 270, 1445)], fill=NAVY, width=3)
        d.text((x, 1495), title, font=label, fill=NAVY, anchor="ms")
        if note:
            d.text((x, 1538), note, font=small, fill=MUTED, anchor="ms")

    seal(img, CX, 1360)
    return img.convert("RGB")


if __name__ == "__main__":
    out = HERE / "template.png"
    build().save(out, optimize=True)
    print(f"Template disimpan: {out}")
