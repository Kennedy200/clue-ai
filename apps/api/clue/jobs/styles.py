"""Builders for the video styles. Each returns a SceneProject; voice/timing/captions are shared."""
from __future__ import annotations

import logging
import re
import time
from collections import Counter
from collections.abc import Callable

from sqlalchemy.orm import Session

from clue.ai.align import align
from clue.ai.tts import get_tts
from clue.assets.providers import PROVIDERS, AssetError, fetch
from clue.core import storage
from clue.core.media import duration
from clue.jobs.text_story import PAD, split_scenes
from clue.models import Asset
from clue.render.scene import CaptionStyle, Scene, SceneProject, Visual

log = logging.getLogger("clue.styles")
STYLES = ["text_story", "video_story", "commentary", "split_screen", "ranking"]
STOP = set("the a an and or but if then of to in on at for with from by is are was were be been it its this that these those i you he she we they my your his her our their as not no so do did does have has had will would can could just very really about into out up down over after before when what which who how why there here than too also more most some any all".split())


class SpecError(ValueError):
    """The request is invalid in a way the user can fix; the message is shown to them. Never retried."""
    retryable = False


def keywords(text: str, n: int = 3) -> list[str]:
    """Cheap, LLM-free visual keywords: the most frequent/longest non-stopwords."""
    words = [w for w in re.findall(r"[A-Za-z]{4,}", text.lower()) if w not in STOP]
    ranked = [w for w, _ in Counter(words).most_common()]
    ranked.sort(key=lambda w: (-words.count(w), -len(w)))
    return ranked[:n] or ["abstract background"]


class Ctx:
    def __init__(self, db: Session, user_id: str, job_id: str, voice: str, speed: float, seed: int, on_progress: Callable[[int, str], None]):
        self.db, self.user_id, self.job_id, self.voice, self.speed, self.seed, self.on_progress = db, user_id, job_id, voice, speed, seed, on_progress
        self.tts = get_tts()
        self.dir = storage.user_dir(user_id, f"jobs/{job_id}")
        self.n = 0
        self._last_ai_image = 0.0

    def asset(self, asset_id: str | None, kinds: tuple[str, ...]) -> Asset | None:
        if not asset_id:
            return None
        a = self.db.get(Asset, asset_id)
        if a is None or a.user_id != self.user_id:
            raise SpecError("One of the selected media files was not found. Pick it again from your library.")
        if a.kind not in kinds:
            raise SpecError(f"'{a.name}' is a {a.kind} file, but a {' or '.join(kinds)} file is needed here.")
        return a

    def speak(self, text: str, **scene_kw) -> Scene:
        """TTS one scene, measure the real duration, and time every word."""
        i, self.n = self.n, self.n + 1
        wav = self.dir / f"scene{i:03d}.wav"
        self.tts.synthesize(text, self.voice, self.speed, wav)
        dur = duration(wav) + PAD
        return Scene(id=f"s{i}", text=text, audio_path=f"{self.user_id}/jobs/{self.job_id}/{wav.name}", duration=round(dur, 3),
                     words=align(text, wav, dur), **scene_kw)

    def ai_image(self, kws: list[str], source: str) -> Visual | None:
        """Best-effort image for a scene. Never raises: the renderer falls back to a procedural background."""
        if source == "none":
            return None
        query = ", ".join(kws[:3])
        try:
            if source == "ai":
                wait = 3.0 - (time.time() - self._last_ai_image)  # be gentle with the anonymous tier
                if wait > 0:
                    time.sleep(wait)
                self._last_ai_image = time.time()
                res = PROVIDERS["pollinations"].search(f"{query}, vertical, cinematic, no text", 1)
            else:
                res = PROVIDERS["wikimedia"].search(query, 3)
            if res:
                return Visual(kind="image", path=fetch(res[0], self.user_id, timeout=60), attribution=res[0].attribution)
        except (AssetError, Exception) as e:  # noqa: BLE001
            log.warning("image lookup failed for %r: %s", query, e)
        return None


def _visual_from_asset(a: Asset | None, default_seed: int, start: float = 0.0, volume: float | None = None) -> Visual:
    if a is None:
        return Visual(kind="procedural", seed=default_seed)
    if a.kind == "image":
        return Visual(kind="image", path=a.path)
    return Visual(kind="video", path=a.path, start=start, has_audio=a.has_audio, audio_volume=volume)


def text_story(ctx: Ctx, spec: dict) -> list[Scene]:
    text = (spec.get("text") or "").strip()
    chunks = split_scenes(text)
    if not chunks:
        raise SpecError("Please enter some text for the story.")
    bg = ctx.asset(spec.get("background_asset_id"), ("video", "image"))
    out = []
    for i, c in enumerate(chunks):
        ctx.on_progress(2 + int(3 * i / len(chunks)), f"voice {i + 1}/{len(chunks)}")
        out.append(ctx.speak(c, visual=_visual_from_asset(bg, ctx.seed + i)))
    return out


def video_story(ctx: Ctx, spec: dict) -> list[Scene]:
    """spec.scenes: [{text, keywords?, on_screen_text?}] (e.g. from the AI planner) or spec.text (split automatically)."""
    scenes = spec.get("scenes")
    if not scenes:
        scenes = [{"text": t} for t in split_scenes((spec.get("text") or "").strip())]
    if not scenes:
        raise SpecError("Please enter a script or generate one first.")
    source = spec.get("image_source", "ai")
    out = []
    for i, s in enumerate(scenes):
        ctx.on_progress(2 + int(3 * i / len(scenes)), f"scene {i + 1}/{len(scenes)}")
        vis = None
        if s.get("asset_id"):
            vis = _visual_from_asset(ctx.asset(s["asset_id"], ("video", "image")), ctx.seed + i)
        if vis is None:
            vis = ctx.ai_image(s.get("keywords") or keywords(s["text"]), source)
        out.append(ctx.speak(s["text"], visual=vis or Visual(kind="procedural", seed=ctx.seed + i), on_screen_text=s.get("on_screen_text")))
    return out


def ranking(ctx: Ctx, spec: dict) -> list[Scene]:
    """spec.items: [{label, text?, asset_id?, keywords?}] listed best-first; played as a countdown N..1."""
    items = spec.get("items") or []
    if len(items) < 2:
        raise SpecError("A ranking needs at least 2 items.")
    if len(items) > 10:
        raise SpecError("A ranking can have at most 10 items.")
    source = spec.get("image_source", "none")
    n, out = len(items), []
    intro = (spec.get("title") or "").strip()
    if intro:
        out.append(ctx.speak(intro, visual=Visual(kind="procedural", seed=ctx.seed), on_screen_text=intro[:60]))
    for pos, it in enumerate(reversed(items)):
        rank = n - pos
        label = (it.get("label") or "").strip()
        if not label:
            raise SpecError(f"Item {rank} needs a name.")
        ctx.on_progress(2 + int(3 * pos / n), f"item {rank}")
        vis = _visual_from_asset(ctx.asset(it.get("asset_id"), ("video", "image")), ctx.seed + pos) if it.get("asset_id") else None
        if vis is None:
            vis = ctx.ai_image(it.get("keywords") or keywords(label + " " + (it.get("text") or "")), source)
        line = f"Number {rank}. {label}." + (f" {it['text'].strip()}" if it.get("text") else "")
        out.append(ctx.speak(line, visual=vis or Visual(kind="procedural", seed=ctx.seed + pos + 1), badge=str(rank), on_screen_text=label[:60]))
    return out


def commentary(ctx: Ctx, spec: dict) -> list[Scene]:
    """The user's clip plays under AI commentary; original audio is ducked to spec.original_volume."""
    clip = ctx.asset(spec.get("clip_asset_id"), ("video",))
    if clip is None:
        raise SpecError("Choose the clip you want to comment on.")
    lines = spec.get("lines") or split_scenes((spec.get("text") or "").strip())
    if not lines:
        raise SpecError("Write the commentary first, or generate it.")
    vol = float(spec.get("original_volume", 0.25))
    clip_len = max(1.0, clip.duration or 1.0)
    out, cursor = [], 0.0
    for i, line in enumerate(lines):
        ctx.on_progress(2 + int(3 * i / len(lines)), f"commentary {i + 1}/{len(lines)}")
        sc = ctx.speak(line, visual=_visual_from_asset(clip, 0, start=cursor % clip_len, volume=vol))
        cursor += sc.duration
        out.append(sc)
    return out


def split_screen(ctx: Ctx, spec: dict) -> list[Scene]:
    """Main story on top, a retention loop (user's or procedural) on the bottom."""
    top = ctx.asset(spec.get("main_asset_id"), ("video", "image"))
    bottom = ctx.asset(spec.get("bottom_asset_id"), ("video", "image"))
    chunks = split_scenes((spec.get("text") or "").strip())
    if not chunks:
        raise SpecError("Please enter the text to narrate on the top half.")
    out = []
    for i, c in enumerate(chunks):
        ctx.on_progress(2 + int(3 * i / len(chunks)), f"voice {i + 1}/{len(chunks)}")
        out.append(ctx.speak(c, visual=_visual_from_asset(top, ctx.seed + i), visual2=_visual_from_asset(bottom, ctx.seed + 4)))
    return out


BUILDERS = {"text_story": text_story, "video_story": video_story, "ranking": ranking, "commentary": commentary, "split_screen": split_screen}


def build(db: Session, user_id: str, job_id: str, style: str, spec: dict, *, voice: str, speed: float, seed: int, caption: CaptionStyle,
          watermark: str | None, mode: str, music_asset_id: str | None, on_progress: Callable[[int, str], None]) -> SceneProject:
    if style not in BUILDERS:
        raise SpecError(f"Unknown style '{style}'.")
    ctx = Ctx(db, user_id, job_id, voice, speed, seed, on_progress)
    scenes = BUILDERS[style](ctx, spec)
    music = ctx.asset(music_asset_id, ("audio",))
    if music and mode == "fast":
        raise SpecError("Background music needs Pro or Cinematic mode.")
    return SceneProject(scenes=scenes, captions=caption, watermark=watermark, mode=mode,  # type: ignore[arg-type]
                        layout="split" if style == "split_screen" else "full", music_path=music.path if music else None)
