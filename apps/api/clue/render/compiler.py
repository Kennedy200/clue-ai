"""Compile a SceneProject into FFmpeg runs (argument arrays only) and render an MP4.

Stages: 1) one segment per scene (visual(s) + voice, via filter_complex), 2) concat, 3) burn captions,
watermark, music ducking, loudness, final encode. All work happens in a per-job temp dir removed afterwards.
"""
from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from clue.core.media import MediaError, probe, run_ffmpeg
from clue.core.storage import safe_path

from .captions import build_ass
from .scene import MODE_MAX_SECONDS, Scene, SceneProject, Visual

# Brand-flavoured gradient pairs for procedural backgrounds (hex without #)
PALETTES = [("6C4DFF", "0E0B1F"), ("0E0B1F", "C8FF3D"), ("FF5C7A", "6C4DFF"), ("0E0B1F", "6C4DFF"),
            ("3B2BB5", "FF5C7A"), ("101030", "00A896"), ("C8FF3D", "6C4DFF"), ("2A2548", "FF5C7A")]


class RenderCancelled(Exception):
    pass


def _resolve(p: str) -> Path:
    """Asset paths are relative to the storage root; reject anything that escapes it."""
    return safe_path(p)


def _visual(v: Visual, idx: int, label: str, w: int, h: int, fps: int, dur: float) -> tuple[list[str], str]:
    """Return (input args, filtergraph piece) that turns input #idx into a w x h stream called [label]."""
    d = f"{dur:.3f}"
    if v.kind == "image" and v.path:
        frames = max(1, int(dur * fps))
        bw, bh = int(w * 1.25), int(h * 1.25)
        zoom = f"zoompan=z='min(1+0.18*on/{frames},1.18)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}"
        return (["-loop", "1", "-t", d, "-i", str(_resolve(v.path))],
                f"[{idx}:v]scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},{zoom},setsar=1,format=yuv420p[{label}]")
    if v.kind == "video" and v.path:
        pre = ["-ss", f"{v.start:.3f}"] if v.start else []
        return ([*pre, "-stream_loop", "-1", "-t", d, "-i", str(_resolve(v.path))],
                f"[{idx}:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},setsar=1,format=yuv420p[{label}]")
    c0, c1 = PALETTES[v.seed % len(PALETTES)]
    return (["-f", "lavfi", "-i", f"gradients=s={w}x{h}:c0=0x{c0}:c1=0x{c1}:x0=0:y0=0:x1={w}:y1={h}:speed=0.015:rate={fps}:d={d}"],
            f"[{idx}:v]setsar=1,format=yuv420p[{label}]")


def _segment_args(sc: Scene, project: SceneProject, seg: str) -> list[str]:
    w, h, fps = project.width, project.height, project.fps
    split = project.layout == "split"
    part_h = h // 2 if split else h
    args: list[str] = []
    graph: list[str] = []
    a_in, g = _visual(sc.visual, 0, "top" if split else "v", w, part_h, fps, sc.duration)
    args += a_in
    graph.append(g)
    n = 1
    if split:
        v2 = sc.visual2 or Visual(kind="procedural", seed=sc.visual.seed + 3)
        a2, g2 = _visual(v2, n, "bot", w, part_h, fps, sc.duration)
        args += a2
        graph += [g2, "[top][bot]vstack=inputs=2[v]"]
        n += 1
    dur = f"{sc.duration:.3f}"
    if sc.audio_path:
        args += ["-i", str(_resolve(sc.audio_path))]
        graph.append(f"[{n}:a]aresample=44100,apad=whole_dur={dur}[va]")
    else:
        args += ["-f", "lavfi", "-t", dur, "-i", "anullsrc=r=44100:cl=mono"]
        graph.append(f"[{n}:a]aresample=44100[va]")
    v = sc.visual
    if v.kind == "video" and v.path and v.has_audio and v.audio_volume:
        # keep the source clip's own sound, quieter, underneath the voice
        graph.append(f"[0:a]aresample=44100,volume={v.audio_volume},apad=whole_dur={dur}[sa]")
        graph.append("[va][sa]amix=inputs=2:duration=first:normalize=0[a]")
    else:
        graph.append("[va]anull[a]")
    vlabel, alabel = "[v]", "[a]"
    if sc.transition == "fade":  # dip through black at both ends of the scene
        f = min(0.3, sc.duration / 3)
        graph.append(f"[v]fade=t=in:st=0:d={f:.2f},fade=t=out:st={sc.duration - f:.3f}:d={f:.2f}[vf]")
        graph.append(f"[a]afade=t=in:st=0:d=0.12,afade=t=out:st={max(0.0, sc.duration - 0.15):.3f}:d=0.15[af]")
        vlabel, alabel = "[vf]", "[af]"
    return [*args, "-filter_complex", ";".join(graph), "-map", vlabel, "-map", alabel, "-t", dur, "-r", str(fps),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "160k", seg]


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
    tmp = Path(tempfile.mkdtemp(prefix="clue-render-"))
    try:
        segs: list[str] = []
        n = len(project.scenes)
        for i, sc in enumerate(project.scenes):
            if check():
                raise RenderCancelled()
            prog(5 + int(55 * i / n), f"scene {i + 1}/{n}")
            seg = f"seg{i:03d}.mp4"
            run_ffmpeg(_segment_args(sc, project, seg), cwd=tmp)
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
        grade = ""
        if project.mode == "cinematic":  # colour grade, soft vignette and fine film grain under the captions
            grade = "eq=contrast=1.08:saturation=1.12:gamma=0.97,vignette=PI/5,noise=alls=7:allf=t,"
        vfilter = f"{grade}ass=captions.ass"
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
