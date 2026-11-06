"""FFmpeg / ffprobe helpers. Commands are ALWAYS argument lists, never shell strings."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


class MediaError(Exception):
    pass


def _find(name: str) -> str:
    env = os.environ.get(f"{name.upper()}_PATH")
    if env and Path(env).exists():
        return env
    hit = shutil.which(name)
    if hit:
        return hit
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if base.exists():
        for p in base.glob(f"**/bin/{name}.exe"):
            return str(p)
    raise MediaError(f"{name} not found. Install FFmpeg (Windows: winget install Gyan.FFmpeg) and reopen your terminal.")


def ffmpeg_bin() -> str:
    return _find("ffmpeg")


def ffprobe_bin() -> str:
    return _find("ffprobe")


def run_ffmpeg(args: list[str], cwd: Path | None = None, timeout: int = 900) -> None:
    """Run ffmpeg with the given args. Raises MediaError with the tail of stderr on failure."""
    cmd = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", *args]
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise MediaError("ffmpeg timed out") from e
    if r.returncode != 0:
        raise MediaError(f"ffmpeg failed: {(r.stderr or '').strip()[-600:]}")


def probe(path: Path | str) -> dict:
    r = subprocess.run(
        [ffprobe_bin(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        raise MediaError(f"not a valid media file: {(r.stderr or '').strip()[-200:]}")
    return json.loads(r.stdout)


def duration(path: Path | str) -> float:
    return float(probe(path)["format"]["duration"])


def video_size(path: Path | str) -> tuple[int, int]:
    for s in probe(path)["streams"]:
        if s["codec_type"] == "video":
            return int(s["width"]), int(s["height"])
    raise MediaError("no video stream")


def load_audio_16k(path: Path | str):
    """Decode any audio/video file to a mono 16 kHz float32 numpy array (what Whisper expects)."""
    import numpy as np

    r = subprocess.run(
        [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
        capture_output=True, timeout=600,
    )
    if r.returncode != 0:
        raise MediaError("could not read audio from this file")
    return np.frombuffer(r.stdout, dtype=np.float32)
