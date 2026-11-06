"""Thumbnail maker (Pillow): 1280x720 PNG with a readable title over a photo or gradient. Four layout variants."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1280, 720
PALETTES = [((108, 77, 255), (14, 11, 31)), ((255, 92, 122), (108, 77, 255)), ((14, 11, 31), (200, 255, 61)), ((59, 43, 181), (255, 92, 122))]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _gradient(c0, c1) -> Image.Image:
    base = Image.new("RGB", (W, H), c0)
    top = Image.new("RGB", (W, H), c1)
    mask = Image.linear_gradient("L").resize((W, H)).rotate(35, expand=False, resample=Image.BICUBIC)
    return Image.composite(top, base, mask)


def _cover(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    s = max(W / img.width, H / img.height)
    img = img.resize((int(img.width * s) + 1, int(img.height * s) + 1))
    x, y = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        t = f"{cur} {word}".strip()
        if draw.textlength(t, font=font) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = word
    return lines + ([cur] if cur else [])


def _fit(draw, text: str, max_w: int, max_h: int, start: int = 150):
    size = start
    while size > 40:
        f = _font(size)
        lines = _wrap(draw, text, f, max_w)
        if len(lines) * size * 1.08 <= max_h and all(draw.textlength(ln, font=f) <= max_w for ln in lines):
            return f, lines, size
        size -= 6
    f = _font(40)
    return f, _wrap(draw, text, f, max_w), 40


def make(title: str, variant: int = 0, background: Path | None = None) -> bytes:
    """Render one thumbnail variant (0-3) and return PNG bytes."""
    title = " ".join(title.split())[:90] or "Your title"
    bg = _cover(Image.open(background)) if background else _gradient(*PALETTES[variant % 4])
    if background:
        bg = bg.filter(ImageFilter.GaussianBlur(2 if variant % 2 else 0))
    img = bg.copy()
    dr = ImageDraw.Draw(img, "RGBA")
    pad = 70
    if variant == 0:  # bottom scrim, left aligned
        dr.rectangle((0, H * 0.45, W, H), fill=(14, 11, 31, 170))
        f, lines, size = _fit(dr, title, W - 2 * pad, int(H * 0.45) - 40)
        y = H - pad - len(lines) * size * 1.08
        accent = (200, 255, 61, 255)
        align = "left"
    elif variant == 1:  # centred on a dark card
        f, lines, size = _fit(dr, title, W - 2 * pad - 80, int(H * 0.6))
        bh = len(lines) * size * 1.08 + 70
        dr.rounded_rectangle((pad, (H - bh) / 2, W - pad, (H + bh) / 2), 36, fill=(14, 11, 31, 205))
        y = (H - bh) / 2 + 35
        accent = (200, 255, 61, 255)
        align = "center"
    elif variant == 2:  # big top-left with accent bar
        dr.rectangle((0, 0, W, H), fill=(14, 11, 31, 110))
        dr.rectangle((pad, pad, pad + 18, H - pad), fill=(200, 255, 61, 255))
        f, lines, size = _fit(dr, title, W - 2 * pad - 60, H - 2 * pad)
        y = pad
        accent = (255, 255, 255, 255)
        align = "left"
        pad += 50
    else:  # lime banner
        f, lines, size = _fit(dr, title, W - 2 * pad - 40, int(H * 0.5))
        bh = len(lines) * size * 1.08 + 50
        y0 = H - bh - 60
        dr.rectangle((0, y0, W, y0 + bh), fill=(200, 255, 61, 255))
        y = y0 + 25
        accent = (14, 11, 31, 255)
        align = "left"
    for ln in lines:
        w = dr.textlength(ln, font=f)
        x = (W - w) / 2 if align == "center" else pad
        if accent[:3] != (14, 11, 31):  # outline for readability on photos
            for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2)):
                dr.text((x + dx, y + dy), ln, font=f, fill=(0, 0, 0, 255))
        dr.text((x, y), ln, font=f, fill=(255, 255, 255, 255) if variant in (0, 1, 2) else accent)
        y += size * 1.08
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG", optimize=True)
    return buf.getvalue()
