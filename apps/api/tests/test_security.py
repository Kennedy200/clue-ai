import re

from sqlalchemy import select

from clue.core import ratelimit, storage
from clue.models import DevMail, Job, Project, User
from tests.conftest import signup


def hdr(client):
    return {"x-csrf-token": client.get("/api/auth/me").json()["csrf"]}


def test_admin_email_cannot_be_claimed_by_a_stranger_on_a_hosted_install(client, db, monkeypatch):
    from clue.core.config import get_settings

    monkeypatch.setattr(get_settings(), "admin_email", "owner@example.com")
    # saas mode: signing up with the admin address does NOT make you admin until you prove you own the inbox
    signup(client, "owner@example.com")
    assert db.scalar(select(User).where(User.email == "owner@example.com")).is_admin is False
    assert client.get("/api/admin/dashboard").status_code == 403
    m = db.scalars(select(DevMail).where(DevMail.to == "owner@example.com")).all()[-1]
    client.post("/api/auth/verify", json={"token": re.search(r"token=(\S+)", m.body).group(1)})
    db.expire_all()
    assert db.scalar(select(User).where(User.email == "owner@example.com")).is_admin is True


def test_changing_password_signs_out_other_devices(client, db):
    from fastapi.testclient import TestClient

    signup(client, "p@example.com")
    other = TestClient(client.app)
    other.post("/api/auth/login", json={"email": "p@example.com", "password": "password123"})
    assert other.get("/api/auth/me").status_code == 200
    r = client.post("/api/auth/change-password", json={"current": "password123", "new": "another-pass-456"}, headers=hdr(client))
    assert r.status_code == 200
    assert other.get("/api/auth/me").status_code == 401  # the other device is out
    assert client.get("/api/auth/me").status_code == 200  # this one stays in


def test_rate_limit_is_per_client_behind_a_proxy(client):
    ratelimit.reset()
    for i in range(5):
        r = client.post("/api/auth/signup", json={"email": f"x{i}@example.com", "password": "password123"}, headers={"x-forwarded-for": "10.0.0.1"})
        assert r.status_code == 200
        client.cookies.clear()
    assert client.post("/api/auth/signup", json={"email": "x9@example.com", "password": "password123"}, headers={"x-forwarded-for": "10.0.0.1"}).status_code == 429
    # a different visitor behind the same proxy is not locked out by the first one
    assert client.post("/api/auth/signup", json={"email": "y@example.com", "password": "password123"}, headers={"x-forwarded-for": "10.0.0.2"}).status_code == 200


def test_oversized_bodies_are_refused_and_headers_are_set(client):
    r = client.post("/api/auth/login", content=b"x" * 10, headers={"content-length": str(5 * 1024 * 1024), "content-type": "application/json"})
    assert r.status_code == 413
    h = client.get("/api/health").headers
    assert h["x-content-type-options"] == "nosniff" and "referrer-policy" in h


def test_csrf_required_and_cookie_is_httponly(client):
    r = client.post("/api/auth/signup", json={"email": "c@example.com", "password": "password123"})
    sc = r.headers["set-cookie"].lower()
    assert "httponly" in sc and "samesite=lax" in sc
    assert client.post("/api/auth/change-password", json={"current": "password123", "new": "another-pass-456"}).status_code == 403
    assert client.post("/api/billing/cancel").status_code == 403


def test_files_cannot_be_forged_traversed_or_read_across_users(client, db):
    signup(client, "a@example.com")
    a = db.scalar(select(User).where(User.email == "a@example.com"))
    f = storage.root() / a.id / "secret.txt"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("mine")
    ok = client.get(f"/api/files/sign?path={a.id}/secret.txt").json()["url"]
    assert client.get(ok).status_code == 200
    forged = f"/api/files?path={a.id}/secret.txt&t=9999999999.{'0' * 32}"
    assert client.get(forged).status_code == 403
    assert client.get("/api/files?path=../../.env&t=1.1").status_code in (400, 403)
    t = storage.sign("../../.env", 60)
    assert client.get(f"/api/files?path=../../.env&t={t}").status_code in (400, 404)
    client.cookies.clear()
    signup(client, "b@example.com")
    assert client.get(f"/api/files/sign?path={a.id}/secret.txt").status_code == 404  # not B's file


def test_other_users_objects_are_invisible(client, db):
    signup(client, "a@example.com")
    a = db.scalar(select(User).where(User.email == "a@example.com"))
    p = Project(user_id=a.id, title="private", scene_json={"scenes": [], "captions": {}}, status="done", output_path=f"{a.id}/o.mp4")
    j = Job(type="render_video", user_id=a.id, payload={})
    db.add_all([p, j])
    db.commit()
    client.cookies.clear()
    signup(client, "b@example.com")
    h = hdr(client)
    for method, path in [("get", f"/api/projects/{p.id}"), ("get", f"/api/projects/{p.id}/download-url"), ("get", f"/api/jobs/{j.id}"),
                         ("post", f"/api/jobs/{j.id}/cancel"), ("delete", f"/api/projects/{p.id}"), ("get", f"/api/projects/{p.id}/publish-pack"),
                         ("get", f"/api/projects/{p.id}/versions")]:
        r = getattr(client, method)(path, headers=h)
        assert r.status_code == 404, (method, path, r.status_code)
    assert client.get("/api/projects").json() == []


def test_suspended_users_lose_access_immediately(client, db):
    signup(client, "s@example.com")
    u = db.scalar(select(User).where(User.email == "s@example.com"))
    u.is_suspended = True
    db.commit()
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={"email": "s@example.com", "password": "password123"}).status_code in (401, 403)


def test_error_responses_do_not_leak_internals(client):
    assert client.get("/api/projects/does-not-exist").status_code == 401
    signup(client, "e@example.com")
    r = client.get("/api/projects/does-not-exist")
    assert r.status_code == 404 and "Traceback" not in r.text and "sqlalchemy" not in r.text.lower()
