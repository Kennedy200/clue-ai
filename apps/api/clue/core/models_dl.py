"""Resumable download of local model files (Kokoro TTS). Shows progress; safe to re-run."""
from __future__ import annotations

from pathlib import Path

import httpx

from .config import get_settings

KOKORO_BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
KOKORO_FILES = {"kokoro-v1.0.int8.onnx": 92_361_271, "voices-v1.0.bin": 28_214_398}


def models_dir() -> Path:
    p = get_settings().storage_dir / "models" / "kokoro"
    p.mkdir(parents=True, exist_ok=True)
    return p


def download(url: str, dest: Path, expected: int | None = None, on_progress=None) -> Path:
    """Download with HTTP Range resume. Verifies size when known."""
    if expected and dest.exists() and dest.stat().st_size == expected:
        return dest
    part = dest.with_suffix(dest.suffix + ".part")
    have = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={have}-"} if have else {}
    with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=60) as r:
        if r.status_code == 416:  # already complete
            part.replace(dest)
            return dest
        r.raise_for_status()
        mode = "ab" if r.status_code == 206 else "wb"
        got = have if mode == "ab" else 0
        with open(part, mode) as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
                got += len(chunk)
                if on_progress:
                    on_progress(got, expected or 0)
    if expected and part.stat().st_size != expected:
        raise IOError(f"download incomplete: {part.stat().st_size}/{expected} bytes; run again to resume")
    part.replace(dest)
    return dest


def ensure_kokoro(on_progress=None) -> tuple[Path, Path]:
    d = models_dir()
    for name, size in KOKORO_FILES.items():
        download(f"{KOKORO_BASE}/{name}", d / name, size, on_progress)
    return d / "kokoro-v1.0.int8.onnx", d / "voices-v1.0.bin"


if __name__ == "__main__":
    last = [0]

    def p(got, total):
        if got - last[0] > 8_000_000 or got == total:
            last[0] = got
            print(f"  {got / 1e6:.0f} / {total / 1e6:.0f} MB", flush=True)

    print("Downloading Kokoro voice model (about 120 MB, resumable)...")
    ensure_kokoro(p)
    print("Done.")
