"""ASS subtitle generation with word-by-word highlighting. User text is sanitised for ASS."""
from __future__ import annotations

from .scene import CaptionStyle, SceneProject


def _clean(w: str) -> str:
    """Remove characters that ASS treats as markup, and control characters."""
    w = w.replace("\\", "").replace("{", "(").replace("}", ")")
    return "".join(ch for ch in w if ch.isprintable()).strip()


def _bgr(rrggbb: str) -> str:
    rrggbb = (rrggbb + "000000")[:6]
    return f"{rrggbb[4:6]}{rrggbb[2:4]}{rrggbb[0:2]}"


def _ts(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def build_ass(project: SceneProject) -> str:
    st: CaptionStyle = project.captions
    margin_v = 560 if st.position == "lower" else 0
    align = 2 if st.position == "lower" else 5
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {project.width}", f"PlayResY: {project.height}", "WrapStyle: 2", "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        f"Style: Main,{_clean(st.font) or 'Arial'},{st.size},&H00{_bgr(st.color)},&H00{_bgr(st.highlight)},&H00{_bgr(st.outline)},&H80000000,-1,0,0,0,100,100,0,0,1,7,2,{align},80,80,{margin_v},1",
        "Style: Mark,Arial,34,&H99FFFFFF,&H00FFFFFF,&H99000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,9,0,30,40,1",
        "",
        "[Events]", "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    hi = f"{{\\c&H{_bgr(st.highlight)}&}}"
    base = f"{{\\c&H{_bgr(st.color)}&}}"
    offset = 0.0
    for sc in project.scenes:
        words = [(_clean(w.w), offset + w.start, offset + w.end) for w in sc.words if _clean(w.w)]
        for i in range(0, len(words), st.words_per_chunk):
            chunk = words[i : i + st.words_per_chunk]
            for j, (_, ws, _we) in enumerate(chunk):
                end = chunk[j + 1][1] if j + 1 < len(chunk) else chunk[-1][2]
                end = max(end, ws + 0.05)
                text = " ".join((hi if k == j else base) + cw[0] for k, cw in enumerate(chunk))
                lines.append(f"Dialogue: 0,{_ts(ws)},{_ts(end)},Main,,0,0,0,,{text}")
        offset += sc.duration
    if project.watermark:
        lines.append(f"Dialogue: 1,{_ts(0)},{_ts(project.total_duration())},Mark,,0,0,0,,{_clean(project.watermark)}")
    return "\n".join(lines) + "\n"
