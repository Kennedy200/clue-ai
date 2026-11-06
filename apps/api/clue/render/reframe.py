"""Vertical reframing for Auto Clipping: smoothed face tracking, blurred-letterbox, or centre crop; then captions + loudness."""
from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from clue.core.media import MediaError, probe, run_ffmpeg

from .captions import build_ass
from .scene import CaptionStyle, Scene, SceneProject, Word

log = logging.getLogger("clue.reframe")
W, H = 1080, 1920


def sample_faces(src: Path, start: float, end: float, every: float = 0.75) -> list[tuple[float, float | None]]:
    """Face centre x (0..1 of frame width) every `every` seconds, or None when no face. Haar cascade, CPU only."""
    try:
        import cv2
    except ImportError:
        return []
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(str(src))
    out: list[tuple[float, float | None]] = []
    try:
        t = start
        while t < end:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            if not ok:
                break
            scale = 1280 / max(frame.shape[1], 1)
            small = cv2.resize(frame, None, fx=scale, fy=scale) if scale < 1 else frame
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(max(30, small.shape[1] // 40),) * 2)
            if len(faces):
                x, _, w, _ = max(faces, key=lambda f: f[2] * f[3])
                out.append((t - start, (x + w / 2) / small.shape[1]))
            else:
                out.append((t - start, None))
            t += every
    finally:
        cap.release()
    return out


def smooth_path(samples: list[tuple[float, float | None]], alpha: float = 0.35) -> list[tuple[float, float]] | None:
    """Fill gaps, exponentially smooth, and return [(t, centre_x)] or None if faces were rarely seen."""
    seen = [c for _, c in samples if c is not None]
    if not samples or len(seen) < max(2, 0.25 * len(samples)):
        return None
    cur = seen[0]
    out = []
    for t, c in samples:
        if c is not None:
            cur = cur + alpha * (c - cur)
        out.append((t, cur))
    return out


def crop_x_expr(path: list[tuple[float, float]], src_w: int, crop_w: int) -> str:
    """Piecewise-linear ffmpeg expression for the crop's left edge (clamped to the frame)."""
    xs = [min(max(c * src_w - crop_w / 2, 0), src_w - crop_w) for _, c in path]
    if len(path) < 2:
        return f"{xs[0]:.1f}"
    terms = []
    for (t0, _), (t1, _), x0, x1 in zip(path, path[1:], xs, xs[1:]):
        if abs(x1 - x0) >= 0.5 and t1 > t0:
            terms.append(f"({x1 - x0:.1f})*clip((t-{t0:.2f})/{t1 - t0:.2f},0,1)")
    return f"{xs[0]:.1f}" + ("+" + "+".join(terms) if terms else "")


def reframe_filter(mode: str, src_w: int, src_h: int, path: list[tuple[float, float]] | None) -> tuple[str, str]:
    """Return (filtergraph piece producing [r], mode actually used)."""
    if src_w / src_h <= 9 / 16 + 0.02:  # already vertical
        return f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[r]", "native"
    if mode == "blur":
        return (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=25:3[bg];"
                f"[b]scale={W}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[r]"), "blur"
    crop_w = int(src_h * 9 / 16) // 2 * 2
    if mode == "face" and path:
        return f"[0:v]crop={crop_w}:{src_h}:x='{crop_x_expr(path, src_w, crop_w)}':y=0,scale={W}:{H},setsar=1[r]", "face"
    return f"[0:v]crop={crop_w}:{src_h}:x='(iw-{crop_w})/2':y=0,scale={W}:{H},setsar=1[r]", "center"


def export_clip(src: Path, start: float, end: float, out: Path, words: list[dict], *, mode: str = "face", captions: bool = True,
                style: CaptionStyle | None = None, watermark: str | None = None) -> dict:
    """Cut [start,end] from src, reframe to 1080x1920, burn captions, normalise loudness. Returns {'mode', 'duration'}."""
    src = Path(src).resolve()  # ffmpeg runs in a temp dir, so the input path must be absolute
    info = probe(src)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    if v is None:
        raise MediaError("This file has no video to clip.")
    sw, sh = int(v["width"]), int(v["height"])
    length = end - start
    if length <= 0.5:
        raise MediaError("This clip is too short.")
    path = smooth_path(sample_faces(src, start, end)) if mode == "face" else None
    graph, used = reframe_filter(mode, sw, sh, path)
    if mode == "face" and used == "center":
        log.info("no steady face found; using a centre crop")
    tmp = Path(tempfile.mkdtemp(prefix="clue-clip-"))
    try:
        vf = graph
        if captions or watermark:
            rel = [Word(w=w["w"], start=max(0.0, w["start"] - start), end=min(length, w["end"] - start)) for w in words if w["start"] >= start - 0.05 and w["end"] <= end + 0.05]
            proj = SceneProject(scenes=[Scene(id="c", text="", duration=length, words=rel if captions else [])], captions=style or CaptionStyle(), watermark=watermark)
            (tmp / "captions.ass").write_text(build_ass(proj), encoding="utf-8")
            vf = f"{graph};[r]ass=captions.ass[v]"
        else:
            vf = graph.replace("[r]", "[v]")
        args = ["-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", str(src), "-filter_complex", vf, "-map", "[v]"]
        if any(s["codec_type"] == "audio" for s in info["streams"]):
            args += ["-map", "0:a:0", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-ar", "48000", "-b:a", "160k"]
        args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "out.mp4"]
        run_ffmpeg(args, cwd=tmp, timeout=1800)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp / "out.mp4"), out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"mode": used, "duration": length}


def thumbnail(src: Path, at: float, out: Path, width: int = 360) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(["-ss", f"{at:.2f}", "-i", str(src), "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "4", str(out)])
