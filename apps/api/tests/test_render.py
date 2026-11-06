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
