import pytest
from sqlalchemy import select

import clue.ai.align as align
import clue.jobs.handlers  # noqa: F401
from clue.ai import tts as ttsmod
from clue.core import credits, storage
from clue.core.media import probe
from clue.models import Asset, Job, Project, ProjectVersion, User
from clue.worker import run_once
from tests.conftest import signup
from tests.test_pipeline import FakeTTS
from tests.test_styles import _auth, clip_file, run_job, upload

STORY = {"style": "text_story", "spec": {"text": "The door was open. The kettle was warm. Nobody was home."}}


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    monkeypatch.setattr("clue.jobs.styles.get_tts", lambda: FakeTTS())
    monkeypatch.setattr("clue.ai.tts.get_tts", lambda: FakeTTS())
    monkeypatch.setattr(align, "_failed", True)
    FakeTTS.broken = False


def bal(db):
    db.expire_all()
    return credits.balance(db, db.scalar(select(User)).id)


def make_project(client, db, h):
    jid, pid, j = run_job(client, h, STORY)
    assert j["status"] == "done", j
    return pid


def test_load_returns_scene_and_signed_files(client, db):
    h = _auth(client)
    pid = make_project(client, db, h)
    p = client.get(f"/api/projects/{pid}").json()
    assert p["version"] == 0 and len(p["scene"]["scenes"]) >= 1 and p["output_url"]
    first = p["scene"]["scenes"][0]["audio_path"]
    assert client.get(p["files"][first]).status_code == 200
    client.cookies.clear()
    _auth(client, "other@example.com")
    assert client.get(f"/api/projects/{pid}").status_code == 404


def test_save_is_conflict_safe_and_keeps_history(client, db):
    h = _auth(client)
    pid = make_project(client, db, h)
    p = client.get(f"/api/projects/{pid}").json()
    scene = p["scene"]
    scene["scenes"][0]["text"] = "Edited text"
    r = client.put(f"/api/projects/{pid}/scene", json={"scene": scene, "base_version": 0, "title": "My cut"}, headers=h)
    assert r.status_code == 200 and r.json()["version"] == 1
    stale = client.put(f"/api/projects/{pid}/scene", json={"scene": scene, "base_version": 0}, headers=h)
    assert stale.status_code == 409 and "changed elsewhere" in stale.json()["detail"]
    vs = client.get(f"/api/projects/{pid}/versions").json()
    assert len(vs) == 1 and vs[0]["version"] == 0
    back = client.post(f"/api/projects/{pid}/versions/{vs[0]['id']}/restore", headers=h).json()
    assert back["scene"]["scenes"][0]["text"] != "Edited text" and back["version"] == 2
    assert db.get(Project, pid).title in ("My cut",)


def test_save_rejects_other_users_files_traversal_and_bad_data(client, db):
    h = _auth(client)
    pid = make_project(client, db, h)
    scene = client.get(f"/api/projects/{pid}").json()["scene"]
    for bad in ("someone-else/jobs/x/scene000.wav", "../.secret", "../../etc/passwd"):
        s = {**scene, "scenes": [{**scene["scenes"][0], "audio_path": bad}]}
        assert client.put(f"/api/projects/{pid}/scene", json={"scene": s, "base_version": 0}, headers=h).status_code == 422, bad
    assert client.put(f"/api/projects/{pid}/scene", json={"scene": {"scenes": []}, "base_version": 0}, headers=h).status_code == 422
    s = {**scene, "scenes": [{**scene["scenes"][0], "duration": -3}]}
    assert client.put(f"/api/projects/{pid}/scene", json={"scene": s, "base_version": 0}, headers=h).status_code == 422
    assert client.put(f"/api/projects/{pid}/scene", json={"scene": scene, "base_version": 0}, headers=h).status_code == 200


def test_history_is_capped(client, db):
    h = _auth(client)
    pid = make_project(client, db, h)
    scene = client.get(f"/api/projects/{pid}").json()["scene"]
    for v in range(35):
        assert client.put(f"/api/projects/{pid}/scene", json={"scene": scene, "base_version": v}, headers=h).status_code == 200
    assert db.query(ProjectVersion).filter_by(project_id=pid).count() == 30


def test_revoice_one_scene_costs_one_credit_and_refunds_on_failure(client, db):
    h = _auth(client)
    pid = make_project(client, db, h)
    before = bal(db)
    r = client.post(f"/api/projects/{pid}/scene-voice", json={"text": "A brand new line of narration.", "voice": "fake"}, headers=h)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["duration"] > 0.5 and len(d["words"]) == 6 and bal(db) == before - 1
    assert client.get(d["url"]).status_code == 200
    FakeTTS.broken = True
    r = client.post(f"/api/projects/{pid}/scene-voice", json={"text": "Will fail", "voice": "fake"}, headers=h)
    assert r.status_code == 503 and bal(db) == before - 1  # failed attempt refunded


def test_revoice_whole_video_job_updates_scenes_and_version(client, db):
    h = _auth(client)
    pid = make_project(client, db, h)
    before_audio = client.get(f"/api/projects/{pid}").json()["scene"]["scenes"][0]["audio_path"]
    r = client.post(f"/api/projects/{pid}/regen-voice", json={"voice": "fake", "speed": 1.2}, headers=h)
    assert r.status_code == 200 and r.json()["credits"] == 1
    run_once("w")
    j = client.get(f"/api/jobs/{r.json()['job_id']}").json()
    assert j["status"] == "done", j
    p = client.get(f"/api/projects/{pid}").json()
    assert p["version"] == 1 and p["scene"]["scenes"][0]["audio_path"] != before_audio
    assert len(client.get(f"/api/projects/{pid}/versions").json()) == 1


def test_asset_import_blocks_ssrf_and_records_attribution(client, db, monkeypatch):
    h = _auth(client)
    ok = {"provider": "wikimedia", "url": "https://upload.wikimedia.org/x.jpg", "title": "Lagos", "author": "Ada", "license": "CC BY 4.0", "page_url": "https://commons.wikimedia.org/wiki/File:x.jpg"}
    for bad in ("http://upload.wikimedia.org/x.jpg", "https://evil.example.com/x.jpg", "https://169.254.169.254/latest/meta-data", "file:///etc/passwd"):
        assert client.post("/api/assets/import", json={**ok, "url": bad}, headers=h).status_code == 422, bad
    assert client.post("/api/assets/import", json={**ok, "provider": "other"}, headers=h).status_code == 422
    from clue.api import editor
    (storage.root() / "cache" / "assets").mkdir(parents=True, exist_ok=True)
    (storage.root() / "cache/assets/fake.jpg").write_bytes(b"\xff\xd8x")
    monkeypatch.setattr(editor, "fetch", lambda res, uid, timeout=90: "cache/assets/fake.jpg")
    thumb = {**ok, "url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/f/f6/x.jpg/1920px-x.jpg"}  # what the search really returns
    assert client.post("/api/assets/import", json=thumb, headers=h).status_code == 200
    r = client.post("/api/assets/import", json=ok, headers=h)
    assert r.status_code == 200 and "Ada" in r.json()["attribution"] and "CC BY 4.0" in r.json()["attribution"]
    assert db.scalar(select(Asset)).provider == "wikimedia"


def test_rerender_uses_edited_scene_and_gates_modes(client, db):
    h = _auth(client)
    pid = make_project(client, db, h)
    assert client.post(f"/api/projects/{pid}/render", json={"mode": "pro"}, headers=h).status_code == 403
    scene = client.get(f"/api/projects/{pid}").json()["scene"]
    scene["captions"]["name"] = "yellow-box"
    scene["captions"].update({"box": True, "outline": "FFD400", "outline_width": 14, "color": "111111"})
    client.put(f"/api/projects/{pid}/scene", json={"scene": scene, "base_version": 0}, headers=h)
    r = client.post(f"/api/projects/{pid}/render", json={"mode": "fast"}, headers=h)
    assert r.status_code == 200 and r.json()["credits"] == 5
    run_once("w")
    j = client.get(f"/api/jobs/{r.json()['job_id']}").json()
    assert j["status"] == "done", j
    db.expire_all()
    assert db.get(Project, pid).status == "done" and db.get(Project, pid).scene_json["captions"]["box"] is True


def test_failed_rerender_unlocks_editor_and_refunds(client, db, monkeypatch):
    h = _auth(client)
    pid = make_project(client, db, h)
    start = bal(db)
    import clue.jobs.handlers as H

    def boom(*a, **k):
        raise RuntimeError("encoder crashed")

    monkeypatch.setattr(H, "render", boom)
    r = client.post(f"/api/projects/{pid}/render", json={"mode": "fast"}, headers=h)
    run_once("w")
    run_once("w")
    assert client.get(f"/api/jobs/{r.json()['job_id']}").json()["status"] == "failed"
    db.expire_all()
    assert db.get(Project, pid).status == "done"  # still editable, still has its previous video
    assert bal(db) == start
    scene = client.get(f"/api/projects/{pid}").json()["scene"]
    assert client.put(f"/api/projects/{pid}/scene", json={"scene": scene, "base_version": 0}, headers=h).status_code == 200


def test_upload_creates_480p_proxy_used_by_the_editor(client, db, tmp_path):
    h = _auth(client)
    a = upload(client, h, clip_file(tmp_path, "src.mp4"))
    run_once("w")  # make_proxy
    db.expire_all()
    row = db.get(Asset, a["id"])
    assert row.proxy_path and probe(storage.safe_path(row.proxy_path))["streams"][0]["height"] == 480
    jid, pid, j = run_job(client, h, {"style": "commentary", "spec": {"clip_asset_id": a["id"], "lines": ["Look at that."]}})
    files = client.get(f"/api/projects/{pid}").json()["files"]
    assert files[a["path"]].find("proxy") != -1  # preview uses the light copy


def test_delete_project(client, db):
    h = _auth(client)
    pid = make_project(client, db, h)
    out = db.get(Project, pid).output_path
    assert client.delete(f"/api/projects/{pid}", headers=h).status_code == 200
    assert client.get(f"/api/projects/{pid}").status_code == 404 and not (storage.root() / out).exists()


def test_edge_plugin_is_off_by_default_and_admin_only(client, db, monkeypatch):
    h = _auth(client)
    monkeypatch.setattr(ttsmod.EdgeProvider, "voices", lambda self: [{"id": "edge:en-NG-AbeoNeural", "name": "Abeo", "gender": "male", "lang": "en-NG", "language": "en-NG (online)", "provider": "edge"}])
    ttsmod.reset_edge_cache()
    assert client.post("/api/admin/plugins/tts/edge", json={"enabled": True}, headers=h).status_code == 403
    router = ttsmod.Router()
    router.kokoro.voices = lambda: [{"id": "af_heart"}]  # type: ignore[method-assign]
    assert [v["id"] for v in router.voices()] == ["af_heart"]
    with pytest.raises(ttsmod.TTSError, match="turned off"):
        router.synthesize("hello", "edge:en-NG-AbeoNeural", 1.0, storage.root() / "x.wav")
    u = db.scalar(select(User))
    u.is_admin = True
    db.commit()
    assert client.post("/api/admin/plugins/tts/edge", json={"enabled": True}, headers=h).status_code == 200
    assert "edge:en-NG-AbeoNeural" in [v["id"] for v in router.voices()]
    listing = client.get("/api/plugins").json()
    assert next(p for p in listing if p["name"] == "edge")["enabled"] is True
    assert client.post("/api/admin/plugins/tts/nope", json={"enabled": True}, headers=h).status_code == 404
