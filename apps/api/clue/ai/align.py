"""Word-level timing for captions.

Preferred: run faster-whisper on the TTS audio and map its word timings onto the script words.
Fallback (model unavailable): spread script words across the voiced span proportionally to length.
"""
from __future__ import annotations

import logging
import os
import re
import threading
from pathlib import Path

from clue.core.media import load_audio_16k
from clue.render.scene import Word

log = logging.getLogger("clue.align")
_lock = threading.Lock()
_model = None
_failed = False


def _whisper(size: str):
    global _model, _failed
    with _lock:
        if _model is None and not _failed:
            try:
                from faster_whisper import WhisperModel

                from clue.core.config import get_settings

                _model = WhisperModel(size, device="cpu", compute_type="int8", download_root=str(get_settings().storage_dir / "models" / "whisper"))
            except Exception as e:  # noqa: BLE001
                log.warning("whisper unavailable, using proportional timing: %s", e)
                _failed = True
        return _model


def script_words(text: str) -> list[str]:
    return [w for w in re.split(r"\s+", text.strip()) if w]


def proportional(words: list[str], start: float, end: float) -> list[Word]:
    """Distribute words over [start, end] by character length; punctuation adds a small pause weight."""
    if not words:
        return []
    weights = [len(re.sub(r"\W", "", w)) + 1 + (2 if re.search(r"[,.;:!?]$", w) else 0) for w in words]
    total = sum(weights)
    t, out = start, []
    for w, wt in zip(words, weights):
        d = (end - start) * wt / total
        out.append(Word(w=w, start=round(t, 3), end=round(t + d, 3)))
        t += d
    return out


def align(text: str, wav: Path, duration: float) -> list[Word]:
    words = script_words(text)
    if not words:
        return []
    model = _whisper(os.environ.get("ALIGN_MODEL", "tiny"))
    span = (0.05, max(0.2, duration - 0.15))
    if model is not None:
        try:
            segs, _ = model.transcribe(load_audio_16k(wav), word_timestamps=True, vad_filter=False, beam_size=1)
            heard = [w for s in segs for w in (s.words or [])]
            if heard:
                if len(heard) == len(words):
                    return [Word(w=sw, start=round(h.start, 3), end=round(h.end, 3)) for sw, h in zip(words, heard)]
                span = (heard[0].start, heard[-1].end)
        except Exception as e:  # noqa: BLE001
            log.warning("alignment failed, using proportional timing: %s", e)
    return proportional(words, span[0], span[1])
