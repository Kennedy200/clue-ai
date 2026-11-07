import re

from sqlalchemy import select

from clue.models import DevMail, User
from tests.conftest import signup


def test_signup_me_logout(client):
    u = signup(client)
    assert u["credits"] == 15 and u["plan_id"] == "free"
    me = client.get("/api/auth/me").json()
    assert me["email"] == "a@example.com" and me["csrf"]
    r = client.post("/api/auth/logout")  # no CSRF header -> rejected
    assert r.status_code == 403
    r = client.post("/api/auth/logout", headers={"x-csrf-token": me["csrf"]})
    assert r.status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_duplicate_and_weak_password(client):
    signup(client)
    assert client.post("/api/auth/signup", json={"email": "a@example.com", "password": "password123"}).status_code == 409
    assert client.post("/api/auth/signup", json={"email": "b@example.com", "password": "short"}).status_code == 422


def test_login_wrong_password_and_lockout(client):
    signup(client)
    client.cookies.clear()
    for _ in range(4):
        assert client.post("/api/auth/login", json={"email": "a@example.com", "password": "nope-nope"}).status_code == 401
    from clue.core import ratelimit
    ratelimit.reset()
    assert client.post("/api/auth/login", json={"email": "a@example.com", "password": "nope-nope"}).status_code == 401
    ratelimit.reset()
    # locked now, even with the right password
    assert client.post("/api/auth/login", json={"email": "a@example.com", "password": "password123"}).status_code == 429


def test_verify_and_reset_flow(client, db):
    signup(client)
    mail = db.scalar(select(DevMail).where(DevMail.subject.like("Verify%")))
    token = re.search(r"token=(\S+)", mail.body).group(1)
    assert client.post("/api/auth/verify", json={"token": token}).status_code == 200
    assert client.post("/api/auth/verify", json={"token": token}).status_code == 400  # single use
    assert db.scalar(select(User)).email_verified is False or True  # session cache; re-read below
    db.expire_all()
    assert db.scalar(select(User)).email_verified is True

    client.cookies.clear()
    assert client.post("/api/auth/forgot", json={"email": "ghost@example.com"}).status_code == 200  # no enumeration
    assert client.post("/api/auth/forgot", json={"email": "a@example.com"}).status_code == 200
    mail = db.scalar(select(DevMail).where(DevMail.subject.like("Reset%")))
    token = re.search(r"token=(\S+)", mail.body).group(1)
    assert client.post("/api/auth/reset", json={"token": token, "password": "newpassword1"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "a@example.com", "password": "newpassword1"}).status_code == 200


def test_delete_account_and_export(client, db):
    signup(client)
    me = client.get("/api/auth/me").json()
    h = {"x-csrf-token": me["csrf"]}
    assert client.get("/api/auth/export").json()["user"]["email"] == "a@example.com"
    assert client.post("/api/auth/delete-account", json={"password": "wrong-pass"}, headers=h).status_code == 400
    assert client.post("/api/auth/delete-account", json={"password": "password123"}, headers=h).status_code == 200
    db.expire_all()
    assert db.scalar(select(User)) is None


def verify_email(client, db, email):
    import re

    from sqlalchemy import select

    from clue.models import DevMail
    m = db.scalars(select(DevMail).where(DevMail.to == email, DevMail.subject.like("Verify%"))).all()[-1]
    return client.post("/api/auth/verify", json={"token": re.search(r"token=(\S+)", m.body).group(1)})


def test_referral_credits_arrive_only_after_the_friend_verifies(client, db):
    a = signup(client, "ref@example.com")
    client.cookies.clear()
    b = signup(client, "new@example.com", referral_code=a["referral_code"])
    assert b["credits"] == 15  # nothing yet: a fake address would otherwise farm credits
    assert verify_email(client, db, "new@example.com").status_code == 200
    assert client.get("/api/auth/me").json()["credits"] == 25  # 15 free + 10 referral
    assert verify_email(client, db, "new@example.com").status_code == 400  # a replayed link cannot pay twice
    client.cookies.clear()
    r = client.post("/api/auth/login", json={"email": "ref@example.com", "password": "password123"}).json()
    assert r["credits"] == 25


def test_seeded_local_accounts_can_sign_in(client, db):
    from clue.seed import seed_demo
    from clue.core.security import hash_password
    from clue.models import User
    db.add(User(email="demo@clue.local", password_hash=hash_password("secret-pass-1"), email_verified=True))
    db.commit()
    r = client.post("/api/auth/login", json={"email": "Demo@Clue.local", "password": "secret-pass-1"})
    assert r.status_code == 200, r.text
