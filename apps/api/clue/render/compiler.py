"""Compile a SceneProject into FFmpeg runs (argument arrays only) and render an MP4.

Stages: 1) one segment per scene (visual + voice), 2) concat, 3) burn captions, watermark, loudness, final encode.
All work happens in a per-job temp directory that is removed afterwards.
"""
from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from clue.core.media import MediaError, probe, run_ffmpeg
from clue.core.storage import safe_path

from .captions import build_ass
from .scene import MODE_MAX_SECONDS, Scene, SceneProject

# Brand-flavoured gradient pairs for procedural backgrounds (hex without #)
PALETTES = [("6C4DFF", "0E0B1F"), ("0E0B1F", "C8FF3D"), ("FF5C7A", "6C4DFF"), ("0E0B1F", "6C4DFF"),
            ("3B2BB5", "FF5C7A"), ("101030", "00A896"), ("C8FF3D", "6C4DFF"), ("2A2548", "FF5C7A")]


class RenderCancelled(Exception):
    pass


def _resolve(p: str) -> Path:
    """Asset paths are relative to the storage root; reject anything that escapes it."""
    return safe_path(p)


def _visual_args(sc: Scene, w: int, h: int, fps: int) -> tuple[list[str], str]:
    """Return (input args, video filter) producing a w x h stream of length sc.duration."""
    d = f"{sc.duration:.3f}"
    v = sc.visual
    if v.kind == "image" and v.path:
        frames = max(1, int(sc.duration * fps))
        zoom = f"zoompan=z='min(1+0.18*on/{frames},1.18)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}"
        return (["-loop", "1", "-t", d, "-i", str(_resolve(v.path))],
                f"scale={int(w * 1.25)}:{int(h * 1.25)}:force_original_aspect_ratio=increase,crop={int(w * 1.25)}:{int(h * 1.25)},{zoom},format=yuv420p")
    if v.kind == "video" and v.path:
        return (["-stream_loop", "-1", "-t", d, "-i", str(_resolve(v.path))],
                f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},format=yuv420p")
    c0, c1 = PALETTES[v.seed % len(PALETTES)]
    return (["-f", "lavfi", "-i", f"gradients=s={w}x{h}:c0=0x{c0}:c1=0x{c1}:x0=0:y0=0:x1={w}:y1={h}:speed=0.015:rate={fps}:d={d}"],
            "format=yuv420p")


def render(project: SceneProject, out_path: Path, on_progress: Callable[[int, str], None] | None = None,
           cancelled: Callable[[], bool] | None = None) -> dict:
    """Render the project to out_path. Returns {'duration': s, 'size': bytes}."""
    cap = MODE_MAX_SECONDS[project.mode]
    total = project.total_duration()
    if total > cap + 0.5:
        raise MediaError(f"This video is {total:.0f}s but {project.mode} mode allows {cap}s. Shorten the script.")
    if not project.scenes:
        raise MediaError("Nothing to render: the project has no scenes.")
    prog = on_progress or (lambda p, s: None)
    check = cancelled or (lambda: False)
    w, h, fps = project.width, project.height, project.fps
    tmp = Path(tempfile.mkdtemp(prefix="clue-render-"))
    try:
        segs: list[str] = []
        n = len(project.scenes)
        for i, sc in enumerate(project.scenes):
            if check():
                raise RenderCancelled()
            prog(5 + int(55 * i / n), f"scene {i + 1}/{n}")
            vin, vf = _visual_args(sc, w, h, fps)
            args = list(vin)
            if sc.audio_path:
                args += ["-i", str(_resolve(sc.audio_path))]
                af = ["-af", f"apad=whole_dur={sc.duration:.3f}"]
            else:
                args += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono"]
                af = []
            seg = f"seg{i:03d}.mp4"
            args += ["-vf", vf, *af, "-t", f"{sc.duration:.3f}", "-r", str(fps), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                     "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "160k", seg]
            run_ffmpeg(args, cwd=tmp)
            segs.append(seg)
        if check():
            raise RenderCancelled()
        prog(62, "joining scenes")
        (tmp / "list.txt").write_text("".join(f"file '{s}'\n" for s in segs), encoding="utf-8")
        run_ffmpeg(["-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "joined.mp4"], cwd=tmp)
        prog(70, "captions and finishing")
        (tmp / "captions.ass").write_text(build_ass(project), encoding="utf-8")
        # Relative filenames + cwd avoid Windows drive-letter escaping problems in filter strings.
        final_args = ["-i", "joined.mp4"]
        vfilter = "ass=captions.ass"
        if project.music_path:
            final_args += ["-stream_loop", "-1", "-i", str(_resolve(project.music_path))]
            afilter = (f"[1:a]volume={project.music_volume}[m];[m][0:a]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=400[duck];"
                       f"[0:a][duck]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]")
            final_args += ["-filter_complex", f"[0:v]{vfilter}[v];{afilter}", "-map", "[v]", "-map", "[a]"]
        else:
            final_args += ["-vf", vfilter, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11"]
        final_args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-b:a", "160k",
                       "-t", f"{total:.3f}", "-movflags", "+faststart", "final.mp4"]
        run_ffmpeg(final_args, cwd=tmp)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp / "final.mp4"), out_path)
        prog(100, "done")
        info = probe(out_path)
        return {"duration": float(info["format"]["duration"]), "size": out_path.stat().st_size}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
