"""Local transcription with faster-whisper (CPU, int8). No key, no per-minute fee."""
from __future__ import annotations

import logging
import os
import re
import threading
from pathlib import Path

from clue.core.config import get_settings
from clue.core.media import MediaError, load_audio_16k

log = logging.getLogger("clue.transcribe")
_lock = threading.Lock()
_models: dict[str, object] = {}


def whisper_size() -> str:
    from clue.core.config import get_settings

    return os.environ.get("WHISPER_MODEL") or get_settings().whisper_model  # env var wins, then .env, then the default


def _model(size: str):
    with _lock:
        if size not in _models:
            try:
                from faster_whisper import WhisperModel
            except ImportError as e:
                raise MediaError("Transcription is not installed. Run `npm run setup`.") from e
            try:
                _models[size] = WhisperModel(size, device="cpu", compute_type="int8", download_root=str(get_settings().storage_dir / "models" / "whisper"))
            except Exception as e:  # noqa: BLE001
                raise MediaError(f"Could not load the '{size}' transcription model ({e.__class__.__name__}). The first run needs internet to download it.") from e
        return _models[size]


def transcribe(path: Path | str, language: str | None = None, size: str | None = None, on_progress=None) -> dict:
    """Return {'language', 'words': [{w,start,end}], 'segments': [{text,start,end}]}."""
    audio = load_audio_16k(path)
    if audio.size < 1600:
        raise MediaError("There is no audio to transcribe in this file.")
    total = audio.size / 16000
    segs, info = _model(size or whisper_size()).transcribe(audio, language=language, word_timestamps=True, vad_filter=True, beam_size=1)
    words, segments = [], []
    for s in segs:
        segments.append({"text": s.text.strip(), "start": round(s.start, 2), "end": round(s.end, 2)})
        for w in s.words or []:
            t = w.word.strip()
            if t:
                words.append({"w": t, "start": round(w.start, 2), "end": round(w.end, 2)})
        if on_progress:
            on_progress(min(95, int(100 * s.end / total)))
    return {"language": info.language, "words": words, "segments": segments}


# ---- subtitle files -------------------------------------------------------------------------

def cues(words: list[dict], max_words: int = 7, max_secs: float = 3.5) -> list[tuple[float, float, str]]:
    """Group words into readable subtitle cues (break on sentence ends, long gaps, or size)."""
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        end_sentence = bool(re.search(r"[.!?…]$", w["w"]))
        gap = nxt is not None and nxt["start"] - w["end"] > 0.7
        too_long = len(cur) >= max_words or w["end"] - cur[0]["start"] >= max_secs
        if nxt is None or end_sentence or gap or too_long:
            out.append((cur[0]["start"], w["end"], " ".join(x["w"] for x in cur)))
            cur = []
    return out


def _stamp(t: float, comma: bool) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{',' if comma else '.'}{ms:03d}"


def to_srt(words: list[dict]) -> str:
    return "".join(f"{i}\n{_stamp(a, True)} --> {_stamp(b, True)}\n{t}\n\n" for i, (a, b, t) in enumerate(cues(words), 1))


def to_vtt(words: list[dict]) -> str:
    return "WEBVTT\n\n" + "".join(f"{_stamp(a, False)} --> {_stamp(b, False)}\n{t}\n\n" for a, b, t in cues(words))
