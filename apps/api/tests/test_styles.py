import pytest
from sqlalchemy import select

import clue.ai.align as align
import clue.jobs.handlers  # noqa: F401
from clue.core import credits, storage
from clue.core.media import probe, run_ffmpeg
from clue.models import Job, Project, User
from clue.worker import run_once
from tests.conftest import signup
from tests.test_pipeline import FakeTTS


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    monkeypatch.setattr("clue.jobs.styles.get_tts", lambda: FakeTTS())
    monkeypatch.setattr(align, "_failed", True)
    FakeTTS.broken = False


def _auth(client, email="a@example.com"):
    signup(client, email)
    return {"x-csrf-token": client.get("/api/auth/me").json()["csrf"]}


def _make(tmp_path, name, args):
    f = tmp_path / name
    run_ffmpeg([*args, str(f)])
    return f


def upload(client, h, path, chunk=64 * 1024):
    data = path.read_bytes()
    r = client.post("/api/uploads/init", json={"name": path.name, "size": len(data)}, headers=h)
    assert r.status_code == 200, r.text
    uid, off = r.json()["id"], 0
    while off < len(data):
        r = client.put(f"/api/uploads/{uid}?offset={off}", content=data[off : off + chunk], headers=h)
        assert r.status_code == 200, r.text
        off = r.json()["offset"]
    r = client.post(f"/api/uploads/{uid}/finish", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def clip_file(tmp_path, name="c.mp4", with_audio=True):
    args = ["-f", "lavfi", "-i", "testsrc=s=640x360:d=5:r=25"]
    if with_audio:
        args += ["-f", "lavfi", "-i", "sine=frequency=200:duration=5", "-shortest", "-metadata", "title=SECRET-GPS-TITLE", "-c:a", "aac"]
    return _make(tmp_path, name, [*args, "-c:v", "libx264"])


def run_job(client, h, body):
    r = client.post("/api/render/create", json=body, headers=h)
    assert r.status_code == 200, r.text
    jid = r.json()["job_id"]
    while run_once("t"):
        pass
    return jid, r.json()["project_id"], client.get(f"/api/jobs/{jid}").json()


def scene_json(db, pid):
    db.expire_all()
    return db.get(Project, pid).scene_json


def out_info(db, jid):
    db.expire_all()
    rel = db.get(Job, jid).result["output"]
    p = probe(storage.safe_path(rel))
    v = next(s for s in p["streams"] if s["codec_type"] == "video")
    return (v["width"], v["height"]), float(p["format"]["duration"])


def test_upload_resume_validate_and_strip_metadata(client, db, tmp_path):
    h = _auth(client)
    f = clip_file(tmp_path)
    data = f.read_bytes()
    uid = client.post("/api/uploads/init", json={"name": "c.mp4", "size": len(data)}, headers=h).json()["id"]
    assert client.put(f"/api/uploads/{uid}?offset=0", content=data[:1000], headers=h).json()["offset"] == 1000
    assert client.put(f"/api/uploads/{uid}?offset=0", content=data[:1000], headers=h).status_code == 409  # duplicate chunk
    assert client.post(f"/api/uploads/{uid}/finish", headers=h).status_code == 409  # incomplete
    assert client.get(f"/api/uploads/{uid}").json()["offset"] == 1000  # resume point
    client.put(f"/api/uploads/{uid}?offset=1000", content=data[1000:], headers=h)
    a = client.post(f"/api/uploads/{uid}/finish", headers=h).json()
    assert a["kind"] == "video" and a["has_audio"] and a["width"] == 640
    tags = probe(storage.safe_path(a["path"]))["format"].get("tags", {})
    assert "SECRET-GPS-TITLE" not in str(tags)  # metadata stripped
    assert [x["id"] for x in client.get("/api/media").json()] == [a["id"]]
    other = _auth(client, "other@example.com") if client.cookies.clear() is None else None
    assert client.get(f"/api/uploads/{uid}", headers=other).status_code == 404
    assert client.get("/api/media").json() == []


def test_upload_rejections(client, tmp_path):
    h = _auth(client)
    assert client.post("/api/uploads/init", json={"name": "x.exe", "size": 10}, headers=h).status_code == 415
    assert client.post("/api/uploads/init", json={"name": "big.mp4", "size": 300 * 1024 * 1024}, headers=h).status_code == 413  # free plan cap
    fake = tmp_path / "fake.mp4"
    fake.write_bytes(b"this is not a video" * 50)
    uid = client.post("/api/uploads/init", json={"name": "fake.mp4", "size": fake.stat().st_size}, headers=h).json()["id"]
    client.put(f"/api/uploads/{uid}?offset=0", content=fake.read_bytes(), headers=h)
    assert client.post(f"/api/uploads/{uid}/finish", headers=h).status_code == 422
    assert client.put("/api/uploads/../../etc?offset=0", content=b"x", headers=h).status_code in (404, 405)


def test_ranking_countdown_with_badges(client, db, tmp_path):
    h = _auth(client)
    body = {"style": "ranking", "title": "Top foods", "spec": {"title": "Top three Nigerian foods", "items": [
        {"label": "Jollof rice", "text": "Always wins the party."}, {"label": "Suya"}, {"label": "Pounded yam", "text": "Best with egusi."}]}}
    jid, pid, j = run_job(client, h, body)
    assert j["status"] == "done", j
    sj = scene_json(db, pid)
    assert [s["badge"] for s in sj["scenes"]] == [None, "3", "2", "1"]  # countdown order, best last
    assert "Number 3" in sj["scenes"][1]["text"] and "Pounded yam" in sj["scenes"][1]["text"]
    assert out_info(db, jid)[0] == (1080, 1920)


def test_ranking_needs_two_items_fails_fast_and_refunds(client, db):
    h = _auth(client)
    jid, _, j = run_job(client, h, {"style": "ranking", "spec": {"items": [{"label": "Only one"}]}})
    assert j["status"] == "failed" and "at least 2" in j["error"]
    assert db.get(Job, jid).attempts == 1  # user errors are not retried
    db.expire_all()
    assert credits.balance(db, db.scalar(select(User)).id) == 15


def test_split_screen_with_uploaded_bottom_loop(client, db, tmp_path):
    h = _auth(client)
    loop = upload(client, h, clip_file(tmp_path, "loop.mp4", with_audio=False))
    jid, pid, j = run_job(client, h, {"style": "split_screen", "spec": {"text": "Top half story. Another line.", "bottom_asset_id": loop["id"]}})
    assert j["status"] == "done", j
    sj = scene_json(db, pid)
    assert sj["layout"] == "split" and sj["scenes"][0]["visual2"]["kind"] == "video"
    assert out_info(db, jid)[0] == (1080, 1920)


def test_commentary_ducks_original_audio(client, db, tmp_path):
    h = _auth(client)
    clip = upload(client, h, clip_file(tmp_path))
    jid, pid, j = run_job(client, h, {"style": "commentary", "spec": {"clip_asset_id": clip["id"], "lines": ["Look at that.", "Unbelievable."], "original_volume": 0.2}})
    assert j["status"] == "done", j
    vis = scene_json(db, pid)["scenes"][1]["visual"]
    assert vis["kind"] == "video" and vis["audio_volume"] == 0.2 and vis["start"] > 0 and vis["has_audio"] is True


def test_video_story_without_image_source_uses_procedural(client, db):
    h = _auth(client)
    jid, pid, j = run_job(client, h, {"style": "video_story", "spec": {"image_source": "none", "scenes": [
        {"text": "Lagos wakes up early.", "on_screen_text": "6 AM"}, {"text": "Traffic builds by seven."}]}})
    assert j["status"] == "done", j
    assert [s["on_screen_text"] for s in scene_json(db, pid)["scenes"]] == ["6 AM", None]


def test_pro_mode_music_ducking_and_plan_gating(client, db, tmp_path):
    h = _auth(client)
    music = upload(client, h, _make(tmp_path, "m.mp3", ["-f", "lavfi", "-i", "sine=frequency=110:duration=4", "-c:a", "libmp3lame"]))
    assert music["kind"] == "audio"
    body = {"style": "text_story", "spec": {"text": "A calm story. With two sentences."}, "mode": "pro", "music_asset_id": music["id"]}
    assert client.post("/api/render/create", json=body, headers=h).status_code == 403  # free plan has Fast only
    u = db.scalar(select(User))
    u.plan_id = "creator"
    db.commit()
    credits.grant(db, u.id, 50, "test")
    jid, pid, j = run_job(client, h, body)
    assert j["status"] == "done", j
    p = probe(storage.safe_path(db.get(Job, jid).result["output"]))
    assert any(s["codec_type"] == "audio" for s in p["streams"])
    # music in Fast mode is refused with a clear message
    jid2, _, j2 = run_job(client, h, {**body, "mode": "fast"})
    assert j2["status"] == "failed" and "Pro or Cinematic" in j2["error"]


def test_asset_ownership_enforced(client, db, tmp_path):
    h = _auth(client)
    clip = upload(client, h, clip_file(tmp_path))
    client.cookies.clear()
    h2 = _auth(client, "thief@example.com")
    jid, _, j = run_job(client, h2, {"style": "commentary", "spec": {"clip_asset_id": clip["id"], "lines": ["Mine now."]}})
    assert j["status"] == "failed" and "not found" in j["error"]
