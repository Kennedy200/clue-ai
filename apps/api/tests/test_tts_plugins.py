import shutil
from pathlib import Path

import pytest
from sqlalchemy import select

from clue.ai import tts as T
from clue.core import storage
from clue.core.config import ROOT, get_settings
from clue.core.media import duration
from clue.models import User
from tests.test_styles import _auth

REAL = ROOT / "storage" / "models" / "piper"


def test_piper_catalog_is_complete_and_well_formed():
    v = T.PiperProvider().voices()
    assert len(v) >= 10 and len({x["id"] for x in v}) == len(v)
    assert all(x["id"].startswith("piper:") and x["gender"] in ("male", "female") for x in v)
    langs = {x["language"].split(" (")[0] for x in v}
    assert {"French", "Spanish", "Arabic", "Swahili"} <= langs  # the languages Kokoro does not cover well
    for k, (path, *_rest) in T.PIPER_CATALOG.items():
        assert path.endswith("/medium") and k.startswith(path.split("/")[1])


def test_plugins_are_off_until_an_admin_enables_them(client, db):
    h = _auth(client)
    T.reset_edge_cache()
    router = T.Router()
    router.kokoro.voices = lambda: [{"id": "af_heart"}]  # type: ignore[method-assign]
    assert [x["id"] for x in router.voices()] == ["af_heart"]
    with pytest.raises(T.TTSError, match="turned off"):
        router.synthesize("hello", "piper:en_GB-alba-medium", 1.0, storage.root() / "x.wav")
    db.scalar(select(User)).is_admin = True
    db.commit()
    assert client.post("/api/admin/plugins/tts/piper", json={"enabled": True}, headers=h).status_code == 200
    ids = [x["id"] for x in router.voices()]
    assert "af_heart" in ids and "piper:sw_CD-lanfrica-medium" in ids
    listing = {p["name"]: p for p in client.get("/api/plugins").json() if p["kind"] == "tts"}
    assert listing["piper"]["enabled"] is True and listing["edge"]["enabled"] is False
    assert "licence" in listing["piper"]["description"].lower() and "commercial" in listing["edge"]["description"].lower()  # both warn about licensing


@pytest.mark.skipif(not (REAL / "en_GB-alba-medium.onnx").exists(), reason="real Piper voice not downloaded on this machine")
def test_piper_really_speaks_and_speed_changes_length(client, db):
    h = _auth(client)
    d = get_settings().storage_dir / "models" / "piper"
    d.mkdir(parents=True, exist_ok=True)
    for ext in (".onnx", ".onnx.json"):
        shutil.copyfile(REAL / f"en_GB-alba-medium{ext}", d / f"en_GB-alba-medium{ext}")
    db.scalar(select(User)).is_admin = True
    db.commit()
    client.post("/api/admin/plugins/tts/piper", json={"enabled": True}, headers=h)
    r = T.Router()
    text = "The door was already open when I got home, and nothing felt right."
    slow, fast = storage.root() / "slow.wav", storage.root() / "fast.wav"
    r.synthesize(text, "piper:en_GB-alba-medium", 0.8, slow)
    r.synthesize(text, "piper:en_GB-alba-medium", 1.4, fast)
    assert duration(slow) > 2.5 and duration(fast) > 1.0
    assert duration(slow) > duration(fast) * 1.3  # speed really changes the pace
    assert Path(slow).read_bytes()[:4] == b"RIFF"
