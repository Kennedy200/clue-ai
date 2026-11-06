import pytest
from sqlalchemy import select

import clue.ai.align as align
import clue.jobs.handlers  # noqa: F401  (registers handlers)
from clue.ai.tts import TTSError, TTSProvider
from clue.core import credits
from clue.core.media import probe, run_ffmpeg
from clue.jobs.text_story import split_scenes
from clue.models import CreditLedger, Job, User
from clue.worker import run_once
from tests.conftest import signup


class FakeTTS(TTSProvider):
    name = "fake"
    broken = False

    def voices(self):
        return [{"id": "fake", "name": "Fake"}]

    def synthesize(self, text, voice, speed, out_path):
        if FakeTTS.broken:
            raise TTSError("voice engine exploded")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        run_ffmpeg(["-f", "lavfi", "-i", f"sine=frequency=300:duration={0.5 + 0.05 * len(text.split())}", "-ar", "24000", str(out_path)])


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    monkeypatch.setattr("clue.jobs.text_story.get_tts", lambda: FakeTTS())
    monkeypatch.setattr(align, "_failed", True)  # skip whisper: proportional timing
    FakeTTS.broken = False


def _auth(client):
    signup(client)
    return {"x-csrf-token": client.get("/api/auth/me").json()["csrf"]}


def _balance(db, email="a@example.com"):
    db.expire_all()
    return credits.balance(db, db.scalar(select(User).where(User.email == email)).id)


STORY = "The door was already open. I walked in slowly. Nothing was missing, but the kettle was warm."


def test_split_scenes():
    assert len(split_scenes(STORY, 60)) >= 2
    assert split_scenes("   ") == []
    assert all(len(s) <= 400 for s in split_scenes("word " * 500, 180))


def test_text_story_end_to_end(client, db):
    h = _auth(client)
    r = client.post("/api/render/text-story", json={"title": "Door", "text": STORY}, headers=h)
    assert r.status_code == 200, r.text
    job_id, pid = r.json()["job_id"], r.json()["project_id"]
    assert _balance(db) == 10  # 15 - 5 reserved
    assert run_once("test-worker") is True
    j = client.get(f"/api/jobs/{job_id}").json()
    assert j["status"] == "done" and j["progress"] == 100, j
    url = client.get(f"/api/projects/{pid}/download-url").json()["url"]
    f = client.get(url)
    assert f.status_code == 200 and f.headers["content-type"] == "video/mp4"
    out = db.get(Job, job_id).result["output"]
    from clue.core import storage
    info = probe(storage.safe_path(out))
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (1080, 1920)
    assert _balance(db) == 10  # settled, not refunded
    assert client.get(url.replace("t=", "t=0")).status_code == 403  # tampered signature
    # SSE ends with the final state
    ev = client.get(f"/api/jobs/{job_id}/events").text
    assert '"status": "done"' in ev


def test_failure_retries_then_refunds(client, db):
    h = _auth(client)
    FakeTTS.broken = True
    job_id = client.post("/api/render/text-story", json={"text": STORY}, headers=h).json()["job_id"]
    assert _balance(db) == 10
    run_once("w")  # attempt 1 -> requeued
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "queued"
    run_once("w")  # attempt 2 -> failed + refund
    j = client.get(f"/api/jobs/{job_id}").json()
    assert j["status"] == "failed" and "exploded" in j["error"]
    assert _balance(db) == 15
    kinds = [r.kind for r in db.scalars(select(CreditLedger).where(CreditLedger.ref_id == db.get(Job, job_id).credit_ref).order_by(CreditLedger.id))]
    assert kinds == ["reserve", "refund"]


def test_insufficient_credits_blocked_and_no_negative(client, db):
    h = _auth(client)
    for _ in range(3):
        assert client.post("/api/render/text-story", json={"text": STORY}, headers=h).status_code == 200
    r = client.post("/api/render/text-story", json={"text": STORY}, headers=h)
    assert r.status_code == 402 and "Not enough credits" in r.json()["detail"]
    assert _balance(db) == 0


def test_cancel_refunds_and_other_users_cannot_see_job(client, db):
    h = _auth(client)
    job_id = client.post("/api/render/text-story", json={"text": STORY}, headers=h).json()["job_id"]
    assert client.post(f"/api/jobs/{job_id}/cancel", headers=h).status_code == 200
    assert _balance(db) == 15
    assert run_once("w") is False  # cancelled job is not claimable
    client.cookies.clear()
    signup(client, "other@example.com")
    assert client.get(f"/api/jobs/{job_id}").status_code == 404


def test_worker_started_as_main_registers_handlers():
    """Regression: `python -m clue.worker` must see the same handler registry the handlers register into."""
    import os
    import subprocess
    import sys
    r = subprocess.run([sys.executable, "-m", "clue.worker", "--check"], capture_output=True, text=True, timeout=120,
                       env={**os.environ, "PYTHONPATH": os.getcwd()})
    assert r.returncode == 0, r.stderr[-500:]
    assert "render_text_story" in r.stdout and "render_project" in r.stdout
