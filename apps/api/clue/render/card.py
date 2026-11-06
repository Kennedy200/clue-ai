"""Clue Card: a 1080x1350 shareable PNG of a Clue Score (Pillow, no network)."""
from __future__ import annotations

import io

from PIL import Image, ImageDraw

from clue.render.thumbnail import _font, _wrap

W, H = 1080, 1350
LABELS = {"hook": "Hook", "pacing": "Pacing", "clarity": "Clarity", "specificity": "Specifics", "cta": "Call to action"}


def make_card(result: dict, title: str = "", invite: str = "") -> bytes:
    img = Image.new("RGB", (W, H), (14, 11, 31))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((40, 40, W - 40, H - 40), 48, outline=(108, 77, 255), width=6)
    d.text((90, 90), "CLUE SCORE", font=_font(44), fill=(200, 255, 61))
    score = int(result.get("score", 0))
    colour = (200, 255, 61) if score >= 70 else (255, 190, 80) if score >= 45 else (255, 92, 122)
    d.ellipse((290, 190, 790, 690), outline=(40, 34, 80), width=36)
    d.arc((290, 190, 790, 690), -90, -90 + int(360 * score / 100), fill=colour, width=36)
    f = _font(190)
    tw = d.textlength(str(score), font=f)
    d.text(((W - tw) / 2, 330), str(score), font=f, fill=(255, 255, 255))
    g = f"Grade {result.get('grade', '-')}"
    gw = d.textlength(g, font=_font(46))
    d.text(((W - gw) / 2, 560), g, font=_font(46), fill=colour)
    y = 740
    if title:
        for line in _wrap(d, title[:90], _font(44), W - 220)[:2]:
            d.text((90, y), line, font=_font(44), fill=(255, 255, 255))
            y += 56
        y += 20
    mx = result.get("max", {})
    for k, v in result.get("parts", {}).items():
        d.text((90, y), LABELS.get(k, k), font=_font(34), fill=(200, 196, 230))
        d.rounded_rectangle((420, y + 8, 960, y + 36), 14, fill=(40, 34, 80))
        pct = v / mx.get(k, 1) if mx.get(k) else 0
        if pct > 0:
            d.rounded_rectangle((420, y + 8, 420 + int(540 * pct), y + 36), 14, fill=colour)
        y += 62
    d.text((90, H - 170), "Scored free with Clue AI", font=_font(38), fill=(255, 255, 255))
    if invite:
        d.text((90, H - 115), invite, font=_font(30), fill=(200, 255, 61))
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()
