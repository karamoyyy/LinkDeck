#!/usr/bin/env python3
"""Gambar ikon LinkDeck (layar lilac + HP biru langit di atas kaca senja) -> png, ico, icns."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).parent / "icons"
S = 1024


def draw() -> Image.Image:
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # latar: persegi membulat dengan gradasi senja
    bg = Image.new("RGBA", (S, S))
    px = bg.load()
    for y in range(S):
        for x in range(S):
            t = (x * 0.35 + y * 0.65) / S
            r = int(242 * (1 - t) + 44 * t); g = int(176 * (1 - t) + 30 * t); b = int(102 * (1 - t) + 48 * t)
            px[x, y] = (r, g, b, 255)
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((520, -120, 1180, 520), fill=(200, 140, 220, 200))
    ImageDraw.Draw(glow).ellipse((-200, 640, 520, 1260), fill=(238, 106, 47, 170))
    bg = Image.alpha_composite(bg, glow.filter(ImageFilter.GaussianBlur(120)))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((40, 40, S - 40, S - 40), radius=220, fill=255)
    im.paste(bg, (0, 0), mask)
    d = ImageDraw.Draw(im)
    # layar (flat lilac) dan HP (biru langit, garis tinta)
    d.rounded_rectangle((150, 250, 690, 640), radius=70, fill=(236, 198, 245, 255))
    d.rounded_rectangle((300, 700, 540, 728), radius=14, fill=(236, 198, 245, 210))
    d.rounded_rectangle((560, 400, 860, 860), radius=64, fill=(191, 230, 248, 255), outline=(29, 32, 48, 255), width=34)
    d.rounded_rectangle((665, 452, 755, 474), radius=11, fill=(29, 32, 48, 255))
    return im


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    im = draw()
    im.save(OUT / "linkdeck.png")
    im.resize((256, 256), Image.LANCZOS).save(OUT / "linkdeck-256.png")
    im.save(OUT / "linkdeck.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    im.save(OUT / "linkdeck.icns")
    print("ikon dibuat di", OUT)


if __name__ == "__main__":
    main()
