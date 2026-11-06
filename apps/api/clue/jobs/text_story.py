"""Text Story pipeline: story text -> scenes -> TTS per scene -> word timing -> SceneProject -> MP4."""
from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from clue.ai.align import align
from clue.ai.tts import get_tts
from clue.core import storage
from clue.core.media import duration
from clue.render.scene import CaptionStyle, Scene, SceneProject, Visual

PAD = 0.3  # seconds of breathing room after each scene's speech


def split_scenes(text: str, max_chars: int = 180) -> list[str]:
    """Group sentences into scene-sized chunks (a sentence is never split unless it is very long)."""
    text = re.sub(r"\s+", " ", text.strip())
    sentences = re.findall(r"[^.!?…]+[.!?…]*", text)
    scenes, cur = [], ""
    for s in (x.strip() for x in sentences if x.strip()):
        if cur and len(cur) + len(s) + 1 > max_chars:
            scenes.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        scenes.append(cur)
    out: list[str] = []
    for sc in scenes:  # hard-wrap pathological sentences without punctuation
        while len(sc) > max_chars * 2:
            cut = sc.rfind(" ", 0, max_chars * 2)
            cut = cut if cut > 0 else max_chars * 2
            out.append(sc[:cut].strip())
            sc = sc[cut:].strip()
        out.append(sc)
    return out


def build_project(user_id: str, job_id: str, text: str, voice: str, speed: float, seed: int, caption: CaptionStyle,
                  watermark: str | None, mode: str, on_progress: Callable[[int, str], None]) -> SceneProject:
    tts = get_tts()
    chunks = split_scenes(text)
    if not chunks:
        raise ValueError("Please enter some text for the story.")
    base = storage.user_dir(user_id, f"jobs/{job_id}")
    scenes = []
    for i, chunk in enumerate(chunks):
        on_progress(2 + int(3 * i / len(chunks)), f"voice {i + 1}/{len(chunks)}")
        wav = base / f"scene{i:03d}.wav"
        tts.synthesize(chunk, voice, speed, wav)
        dur = duration(wav) + PAD
        scenes.append(Scene(id=f"s{i}", text=chunk, audio_path=f"{user_id}/jobs/{job_id}/{wav.name}", duration=round(dur, 3),
                            words=align(chunk, wav, dur), visual=Visual(kind="procedural", seed=seed + i)))
    return SceneProject(scenes=scenes, captions=caption, watermark=watermark, mode=mode)  # type: ignore[arg-type]


def output_path(user_id: str, job_id: str) -> tuple[Path, str]:
    rel = f"{user_id}/outputs/{job_id}.mp4"
    return storage.root() / rel, rel
