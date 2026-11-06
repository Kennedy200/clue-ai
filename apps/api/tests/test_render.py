import pytest

from clue.core import storage
from clue.core.media import MediaError, probe, run_ffmpeg
from clue.render.captions import build_ass
from clue.render.compiler import render
from clue.render.scene import CaptionStyle, Scene, SceneProject, Visual, Word


def _make_assets():
    d = storage.user_dir("tester", "assets")
    run_ffmpeg(["-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-ar", "24000", str(d / "a1.wav")])
    run_ffmpeg(["-f", "lavfi", "-i", "sine=frequency=330:duration=1.5", "-ar", "24000", str(d / "a2.wav")])
    run_ffmpeg(["-f", "lavfi", "-i", "testsrc=s=800x600:d=1", "-frames:v", "1", str(d / "img.png")])
    return "tester/assets/a1.wav", "tester/assets/a2.wav", "tester/assets/img.png"


def _project(a1, a2, img, **kw):
    return SceneProject(
        scenes=[
            Scene(id="s1", text="Hello brave world", audio_path=a1, duration=2.2,
                  words=[Word(w="Hello", start=0.1, end=0.6), Word(w="brave", start=0.7, end=1.2), Word(w="world", start=1.3, end=2.0)]),
            Scene(id="s2", text="Second {scene} \\N hack", audio_path=a2, duration=1.7, visual=Visual(kind="image", path=img),
                  words=[Word(w="Second", start=0.1, end=0.6), Word(w="{evil}", start=0.7, end=1.0), Word(w="\\Nhack", start=1.0, end=1.5)]),
        ],
        watermark="Made with Clue AI", **kw)


def test_golden_render_produces_valid_vertical_mp4(tmp_path):
    a1, a2, img = _make_assets()
    out = tmp_path / "out.mp4"
    stages = []
    info = render(_project(a1, a2, img), out, on_progress=lambda p, s: stages.append(p))
    p = probe(out)
    v = next(s for s in p["streams"] if s["codec_type"] == "video")
    a = next(s for s in p["streams"] if s["codec_type"] == "audio")
    assert (v["width"], v["height"]) == (1080, 1920)
    assert v["codec_name"] == "h264" and a["codec_name"] == "aac"
    assert int(a["sample_rate"]) == 48000
    assert abs(float(p["format"]["duration"]) - 3.9) < 0.3
    assert stages[-1] == 100 and stages == sorted(stages)
    assert info["size"] > 10_000


def test_mode_cap_enforced(tmp_path):
    a1, a2, img = _make_assets()
    proj = _project(a1, a2, img)
    proj.scenes[0].duration = 70
    with pytest.raises(MediaError, match="allows 60s"):
        render(proj, tmp_path / "x.mp4")


def test_asset_path_traversal_rejected(tmp_path):
    a1, _, _ = _make_assets()
    proj = SceneProject(scenes=[Scene(id="s", text="x", audio_path="../../etc/passwd", duration=1)])
    with pytest.raises(ValueError):
        render(proj, tmp_path / "x.mp4")


def test_ass_sanitises_user_text():
    a1, a2, img = _make_assets()
    ass = build_ass(_project(a1, a2, img))
    assert "{evil}" not in ass and "(evil)" in ass
    assert "\\Nhack" not in ass
    assert "Made with Clue AI" in ass
    assert ass.count("Dialogue:") >= 6


def test_signed_urls_expire_and_reject_tampering():
    tok = storage.sign("u/a.mp4", ttl=60)
    assert storage.verify("u/a.mp4", tok)
    assert not storage.verify("u/b.mp4", tok)
    assert not storage.verify("u/a.mp4", storage.sign("u/a.mp4", ttl=-5))
    with pytest.raises(ValueError):
        storage.safe_path("../secret")


def _clip_with_tone(name="clip.mp4"):
    d = storage.user_dir("tester", "assets")
    run_ffmpeg(["-f", "lavfi", "-i", "testsrc=s=1280x720:d=6:r=30", "-f", "lavfi", "-i", "sine=frequency=220:duration=6", "-shortest",
                "-c:v", "libx264", "-c:a", "aac", str(d / name)])
    return f"tester/assets/{name}"


def test_split_screen_badge_title_and_source_audio_mix(tmp_path):
    a1, a2, img = _make_assets()
    clip = _clip_with_tone()
    proj = SceneProject(layout="split", scenes=[
        Scene(id="s1", text="Number three", audio_path=a1, duration=2.0, badge="3", on_screen_text="Top picks",
              visual=Visual(kind="video", path=clip, start=1.0, has_audio=True, audio_volume=0.3), visual2=Visual(kind="procedural", seed=5),
              words=[Word(w="Number", start=0.1, end=0.6), Word(w="three", start=0.7, end=1.2)]),
        Scene(id="s2", text="Number two", audio_path=a2, duration=1.5, badge="2",
              visual=Visual(kind="image", path=img), words=[Word(w="Number", start=0.1, end=0.6), Word(w="two", start=0.7, end=1.2)]),
    ])
    info = render(proj, tmp_path / "split.mp4")
    p = probe(tmp_path / "split.mp4")
    v = next(s for s in p["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (1080, 1920)
    assert abs(info["duration"] - 3.5) < 0.3
    ass = build_ass(proj)
    assert "Style: Badge" in ass and ",Badge,,0,0,0,,3" in ass and ",Title,,0,0,0,,Top picks" in ass
    assert "Alignment" in ass and ",5,80,80,0,1" in ass  # split layout centres captions on the seam


def test_caption_presets_render_in_every_mode(tmp_path):
    from clue.render.caption_styles import PRESETS, preset
    a1, a2, img = _make_assets()
    assert len(PRESETS) >= 8
    for name in PRESETS:
        ass = build_ass(_project(a1, a2, img, captions=preset(name), mode="pro"))
        assert "Style: Main" in ass
    box = build_ass(_project(a1, a2, img, captions=preset("yellow-box")))
    assert ",3,14,0," in box  # BorderStyle 3 draws a box
    up = build_ass(_project(a1, a2, img, captions=preset("pop-single"), mode="pro"))
    bs = chr(92)  # a literal backslash; ASS override tags start with it
    assert "HELLO" in up and f"{bs}fscx82" in up and f"{bs}t(0,110" in up  # uppercase + pop animation as real ASS tags
    assert "\x0c" not in up and "\t" not in up  # and never as form-feed/tab control characters
    fast = build_ass(_project(a1, a2, img, captions=preset("pop-single"), mode="fast"))
    assert f"{bs}fscx82" not in fast  # animation is a Pro/Cinematic feature


def test_pro_fade_and_cinematic_grade_render_valid_video(tmp_path):
    a1, a2, img = _make_assets()
    proj = _project(a1, a2, img, mode="cinematic")
    proj.scenes[0].transition = "fade"
    out = tmp_path / "cin.mp4"
    info = render(proj, out)
    p = probe(out)
    assert any(s["codec_type"] == "audio" for s in p["streams"]) and abs(info["duration"] - 3.9) < 0.3
    plain = tmp_path / "plain.mp4"
    render(_project(a1, a2, img, mode="fast"), plain)
    assert out.stat().st_size > plain.stat().st_size  # film grain adds real detail/bitrate
