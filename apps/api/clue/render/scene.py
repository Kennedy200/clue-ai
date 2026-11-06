"""Scene JSON: the single source of truth read by both the browser preview and the FFmpeg renderer."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MODE_MAX_SECONDS = {"fast": 60, "pro": 180, "cinematic": 180}


class Word(BaseModel):
    w: str
    start: float  # seconds, relative to the scene start
    end: float


class Visual(BaseModel):
    kind: Literal["procedural", "image", "video"] = "procedural"
    path: str | None = None  # file inside storage for image/video
    seed: int = 0  # picks the procedural palette
    attribution: str | None = None


class Scene(BaseModel):
    id: str
    text: str
    audio_path: str | None = None
    duration: float = Field(gt=0)  # seconds; derived from the audio
    words: list[Word] = []
    visual: Visual = Visual()
    on_screen_text: str | None = None
    transition: Literal["cut", "fade"] = "cut"


class CaptionStyle(BaseModel):
    name: str = "bold-highlight"
    font: str = "Arial"
    size: int = 84
    color: str = "FFFFFF"  # RRGGBB
    highlight: str = "C8FF3D"
    outline: str = "000000"
    position: Literal["middle", "lower"] = "lower"
    words_per_chunk: int = Field(default=4, ge=1, le=8)


class SceneProject(BaseModel):
    width: int = 1080
    height: int = 1920
    fps: int = 30
    mode: Literal["fast", "pro", "cinematic"] = "fast"
    scenes: list[Scene]
    captions: CaptionStyle = CaptionStyle()
    watermark: str | None = None  # e.g. "Made with Clue AI" on free hosted plans
    music_path: str | None = None
    music_volume: float = 0.12

    def total_duration(self) -> float:
        return sum(s.duration for s in self.scenes)
