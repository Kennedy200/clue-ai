"""TTS providers. Default: Kokoro (Apache-2.0, CPU, no key). Optional plugin: edge-tts (online voices incl. Nigerian English).

Voice ids: Kokoro voices are plain ("af_heart"); plugin voices are prefixed ("edge:en-NG-AbeoNeural").
"""
from __future__ import annotations

import asyncio
import threading
import time
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


EDGE_LOCALES = ("en-NG", "en-ZA", "en-KE", "en-GH", "en-GB", "en-US", "fr-FR", "es-ES", "pt-BR", "pt-PT", "ar-EG", "ar-SA", "sw-KE", "sw-TZ", "ha-NG", "yo-NG")


class EdgeProvider(TTSProvider):
    """Microsoft Edge online voices through the unofficial `edge-tts` client. Needs internet.

    LICENSING: not an official, licensed API. Fine for personal and evaluation use; for commercial products use the
    Azure Speech plugin (same voice names, proper licence). Disabled unless an admin turns it on.
    """
    name = "edge"
    _cache: tuple[float, list[dict]] | None = None

    def voices(self) -> list[dict]:
        if EdgeProvider._cache and time.time() - EdgeProvider._cache[0] < 86400:
            return EdgeProvider._cache[1]
        try:
            import edge_tts
        except ImportError as e:
            raise TTSError("The edge-tts plugin is not installed. Run `npm run setup`.") from e
        try:
            raw = asyncio.run(edge_tts.list_voices())
        except Exception as e:  # noqa: BLE001
            raise TTSError("Could not reach the online voice service. Check your internet connection.") from e
        out = [{"id": f"edge:{v['ShortName']}", "name": v["ShortName"].split("-", 2)[2].replace("Neural", ""), "gender": v["Gender"].lower(),
                "lang": v["Locale"], "language": f"{v['Locale']} (online)", "provider": "edge"} for v in raw if v["Locale"] in EDGE_LOCALES]
        EdgeProvider._cache = (time.time(), out)
        return out

    def synthesize(self, text: str, voice: str, speed: float, out_path: Path) -> None:
        import edge_tts

        from clue.core.media import MediaError, run_ffmpeg

        short = voice.removeprefix("edge:")
        if not text.strip():
            raise TTSError("Nothing to say: the text is empty.")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        mp3 = out_path.with_suffix(".edge.mp3")
        rate = f"{int(round((max(0.5, min(2.0, speed)) - 1) * 100)):+d}%"
        try:
            asyncio.run(edge_tts.Communicate(text, short, rate=rate).save(str(mp3)))
            run_ffmpeg(["-i", str(mp3), "-ac", "1", "-ar", "24000", str(out_path)])
        except MediaError as e:
            raise TTSError(str(e)) from e
        except Exception as e:  # noqa: BLE001
            raise TTSError(f"The online voice failed ({e.__class__.__name__}). Check your connection or pick a local voice.") from e
        finally:
            mp3.unlink(missing_ok=True)


_flags: dict[str, tuple[float, bool]] = {}


def plugin_enabled(key: str) -> bool:
    """Admin switch stored in the settings table, re-read at most every 5 seconds."""
    now = time.time()
    c = _flags.get(key)
    if c and now - c[0] < 5:
        return c[1]
    from clue.core.db import SessionLocal
    from clue.core.settings_store import get_setting

    with SessionLocal() as db:
        on = get_setting(db, key) == "1"
    _flags[key] = (now, on)
    return on


def edge_enabled() -> bool:
    return plugin_enabled("tts_edge_enabled")


def piper_enabled() -> bool:
    return plugin_enabled("tts_piper_enabled")


def reset_edge_cache() -> None:
    _flags.clear()


# Curated Piper voices (all verified to exist on huggingface.co/rhasspy/piper-voices). Each voice has its own licence
# in its MODEL_CARD: check it before commercial use. Models download on first use (about 60 MB each).
PIPER_CATALOG: dict[str, tuple[str, str, str, str]] = {
    # id: (path, language label, gender, display name)
    "en_GB-alba-medium": ("en/en_GB/alba/medium", "English (UK)", "female", "Alba"),
    "en_GB-jenny_dioco-medium": ("en/en_GB/jenny_dioco/medium", "English (UK)", "female", "Jenny"),
    "en_GB-northern_english_male-medium": ("en/en_GB/northern_english_male/medium", "English (UK)", "male", "Northern"),
    "en_US-amy-medium": ("en/en_US/amy/medium", "English (US)", "female", "Amy"),
    "en_US-lessac-medium": ("en/en_US/lessac/medium", "English (US)", "female", "Lessac"),
    "en_US-ryan-medium": ("en/en_US/ryan/medium", "English (US)", "male", "Ryan"),
    "fr_FR-siwis-medium": ("fr/fr_FR/siwis/medium", "French", "female", "Siwis"),
    "es_ES-davefx-medium": ("es/es_ES/davefx/medium", "Spanish", "male", "Davefx"),
    "pt_BR-faber-medium": ("pt/pt_BR/faber/medium", "Portuguese (BR)", "male", "Faber"),
    "ar_JO-kareem-medium": ("ar/ar_JO/kareem/medium", "Arabic", "male", "Kareem"),
    "sw_CD-lanfrica-medium": ("sw/sw_CD/lanfrica/medium", "Swahili", "female", "Lanfrica"),
}
PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"


class PiperProvider(TTSProvider):
    """Piper (MIT) neural voices that run locally on CPU. No account, no per-use cost."""
    name = "piper"
    _voices: dict[str, object] = {}
    _lock = threading.Lock()

    def voices(self) -> list[dict]:
        return [{"id": f"piper:{k}", "name": v[3], "gender": v[2], "lang": k.split("-")[0].replace("_", "-"), "language": f"{v[1]} (downloads on first use)", "provider": "piper"}
                for k, v in PIPER_CATALOG.items()]

    def _load(self, name: str):
        with self._lock:
            if name in self._voices:
                return self._voices[name]
            if name not in PIPER_CATALOG:
                raise TTSError(f"Unknown voice '{name}'.")
            try:
                from piper import PiperVoice
            except ImportError as e:
                raise TTSError("The Piper plugin is not installed. Run `npm run setup`.") from e
            from clue.core.config import get_settings
            from clue.core.models_dl import download

            d = get_settings().storage_dir / "models" / "piper"
            d.mkdir(parents=True, exist_ok=True)
            try:
                for ext in (".onnx", ".onnx.json"):
                    if not (d / f"{name}{ext}").exists():  # a finished file exists only after the .part rename, so it is complete
                        download(f"{PIPER_BASE}/{PIPER_CATALOG[name][0]}/{name}{ext}", d / f"{name}{ext}")
            except Exception as e:  # noqa: BLE001
                raise TTSError(f"Could not download the {PIPER_CATALOG[name][3]} voice ({e.__class__.__name__}). Check your connection and try again; the download resumes.") from e
            self._voices[name] = PiperVoice.load(str(d / f"{name}.onnx"))
            return self._voices[name]

    def synthesize(self, text: str, voice: str, speed: float, out_path: Path) -> None:
        import wave

        if not text.strip():
            raise TTSError("Nothing to say: the text is empty.")
        v = self._load(voice.removeprefix("piper:"))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            from piper import SynthesisConfig

            cfg = SynthesisConfig(length_scale=1.0 / max(0.5, min(2.0, speed)))  # length_scale > 1 is slower
            with wave.open(str(out_path), "wb") as w:
                v.synthesize_wav(text, w, syn_config=cfg)  # type: ignore[attr-defined]
        except Exception as e:  # noqa: BLE001
            raise TTSError(f"The Piper voice failed ({e.__class__.__name__}).") from e


class Router(TTSProvider):
    """Routes by voice id prefix and merges voice lists from enabled providers."""
    name = "router"

    def __init__(self):
        self.kokoro, self.edge, self.piper = KokoroProvider(), EdgeProvider(), PiperProvider()

    def voices(self) -> list[dict]:
        out = self.kokoro.voices()
        if piper_enabled():
            out = out + self.piper.voices()
        if edge_enabled():
            try:
                out = out + self.edge.voices()
            except TTSError:
                pass  # offline: local voices still work
        return out

    def synthesize(self, text: str, voice: str, speed: float, out_path: Path) -> None:
        if voice.startswith("edge:"):
            if not edge_enabled():
                raise TTSError("Online voices are turned off. Ask the admin to enable the edge-tts plugin, or choose a local voice.")
            return self.edge.synthesize(text, voice, speed, out_path)
        if voice.startswith("piper:"):
            if not piper_enabled():
                raise TTSError("Piper voices are turned off. Ask the admin to enable the Piper plugin, or choose a Kokoro voice.")
            return self.piper.synthesize(text, voice, speed, out_path)
        return self.kokoro.synthesize(text, voice, speed, out_path)


def get_tts() -> TTSProvider:
    return Router()
