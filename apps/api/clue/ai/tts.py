"""TTS providers. Default: Kokoro (Apache-2.0, CPU, no key). Others (Piper, Azure, ElevenLabs) are plugins."""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from pathlib import Path

from clue.core.models_dl import ensure_kokoro

LANG_BY_PREFIX = {"a": "en-us", "b": "en-gb", "e": "es", "f": "fr-fr", "h": "hi", "i": "it", "j": "ja", "p": "pt-br", "z": "cmn"}
LANG_NAME = {"en-us": "English (US)", "en-gb": "English (UK)", "es": "Spanish", "fr-fr": "French", "hi": "Hindi", "it": "Italian",
             "ja": "Japanese", "pt-br": "Portuguese (BR)", "cmn": "Mandarin"}


class TTSError(Exception):
    pass


class TTSProvider(ABC):
    name: str

    @abstractmethod
    def voices(self) -> list[dict]: ...

    @abstractmethod
    def synthesize(self, text: str, voice: str, speed: float, out_path: Path) -> None: ...


class KokoroProvider(TTSProvider):
    name = "kokoro"
    _lock = threading.Lock()
    _engine = None

    @classmethod
    def _load(cls):
        with cls._lock:
            if cls._engine is None:
                try:
                    from kokoro_onnx import Kokoro
                except ImportError as e:
                    raise TTSError("Voice engine is not installed. Run `npm run setup`.") from e
                try:
                    model, voices = ensure_kokoro()
                except Exception as e:  # noqa: BLE001
                    raise TTSError(f"Could not download the voice model ({e.__class__.__name__}). Check your connection and retry; the download resumes.") from e
                cls._engine = Kokoro(str(model), str(voices))
            return cls._engine

    def voices(self) -> list[dict]:
        out = []
        for v in sorted(self._load().get_voices()):
            lang = LANG_BY_PREFIX.get(v[0], "en-us")
            out.append({"id": v, "name": v.split("_", 1)[1].title(), "gender": "female" if v[1] == "f" else "male",
                        "lang": lang, "language": LANG_NAME.get(lang, lang), "provider": self.name})
        return out

    def synthesize(self, text: str, voice: str, speed: float, out_path: Path) -> None:
        import wave

        import numpy as np

        eng = self._load()
        if voice not in eng.get_voices():
            raise TTSError(f"Unknown voice '{voice}'.")
        if not text.strip():
            raise TTSError("Nothing to say: the text is empty.")
        lang = LANG_BY_PREFIX.get(voice[0], "en-us")
        samples, sr = eng.create(text, voice=voice, speed=max(0.5, min(2.0, speed)), lang=lang)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pcm = (np.clip(np.asarray(samples, dtype=np.float32), -1, 1) * 32767).astype(np.int16)
        with wave.open(str(out_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(int(sr))
            w.writeframes(pcm.tobytes())


def get_tts() -> TTSProvider:
    return KokoroProvider()
