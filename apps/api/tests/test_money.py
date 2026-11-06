from datetime import timedelta

from sqlalchemy import select

from clue.ai import score as S
from clue.core import billing, credits
from clue.core.ids import utcnow
from clue.models import CreditLedger, DevMail, Invoice, User
from tests.conftest import signup


def user(db, email="a@example.com"):
    return db.scalar(select(User).where(User.email == email))


def authed(client, email="a@example.com"):
    r = client.post("/api/auth/signup", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    me = client.get("/api/auth/me")
    h = {"x-csrf-token": me.json().get("csrf", "")}
    return h


def test_subscribe_grants_credits_invoice_and_receipt(client, db):
    h = authed(client)
    before = credits.balance(db, user(db).id)
    r = client.post("/api/billing/subscribe", json={"plan_id": "creator", "interval": "month", "currency": "NGN"}, headers=h)
    assert r.status_code == 200, r.text
    db.expire_all()
    u = user(db)
    assert u.plan_id == "creator" and credits.balance(db, u.id) == before + 500
    inv = client.get("/api/billing/invoices").json()
    assert len(inv) == 1 and inv[0]["amount"] == 1_990_000 and inv[0]["status"] == "paid" and inv[0]["number"].startswith("CLUE-")
    assert db.scalar(select(DevMail).where(DevMail.subject.like("Clue AI receipt%")))
    html = client.get(f"/api/billing/invoices/{inv[0]['id']}/html")
    assert html.status_code == 200 and "Invoice CLUE-" in html.text


def test_annual_is_half_price_per_month_and_grants_a_year(client, db):
    h = authed(client)
    before = credits.balance(db, user(db).id)
    client.post("/api/billing/subscribe", json={"plan_id": "starter", "interval": "year", "currency": "USD"}, headers=h)
    db.expire_all()
    assert client.get("/api/billing/invoices").json()[0]["amount"] == 700 * 6
    assert credits.balance(db, user(db).id) == before + 200 * 12


def test_cannot_see_someone_elses_invoice(client, db):
    h = authed(client, "a@example.com")
    client.post("/api/billing/subscribe", json={"plan_id": "starter"}, headers=h)
    iid = client.get("/api/billing/invoices").json()[0]["id"]
    client.post("/api/auth/logout", headers=h)
    authed(client, "b@example.com")
    assert client.get(f"/api/billing/invoices/{iid}/html").status_code == 404


def test_upgrade_is_prorated_and_downgrade_waits(client, db):
    h = authed(client)
    client.post("/api/billing/subscribe", json={"plan_id": "starter"}, headers=h)
    r = client.post("/api/billing/subscribe", json={"plan_id": "creator"}, headers=h)
    assert r.status_code == 200
    up = client.get("/api/billing/invoices").json()[0]
    assert up["kind"] == "upgrade" and 1_000_000 < up["amount"] < 1_990_000  # creator minus unused starter time
    r = client.post("/api/billing/subscribe", json={"plan_id": "starter"}, headers=h)
    assert "move to Starter" in r.json()["message"]
    db.expire_all()
    assert user(db).plan_id == "creator"  # still creator until the period ends
    out = billing.renew_due(db, utcnow() + timedelta(days=31))
    db.expire_all()
    assert out["renewed"] == 1 and out["downgraded"] == 1 and user(db).plan_id == "starter"


def test_cancel_keeps_plan_until_period_end_then_free(client, db):
    h = authed(client)
    client.post("/api/billing/subscribe", json={"plan_id": "starter"}, headers=h)
    assert client.post("/api/billing/cancel", headers=h).status_code == 200
    db.expire_all()
    assert user(db).plan_id == "starter"
    billing.renew_due(db, utcnow() + timedelta(days=31))
    db.expire_all()
    assert user(db).plan_id == "free"
    assert client.post("/api/billing/cancel", headers=h).status_code == 400  # nothing left to cancel
    assert len(client.get("/api/billing/invoices").json()) == 1  # no charge at the end


def test_declined_card_changes_nothing(client, db):
    h = authed(client)
    u = user(db)
    u.prefs = {"sim_decline": True}
    db.commit()
    bal = credits.balance(db, u.id)
    r = client.post("/api/billing/subscribe", json={"plan_id": "creator"}, headers=h)
    assert r.status_code == 400 and "declined" in r.json()["detail"]
    db.expire_all()
    assert user(db).plan_id == "free" and credits.balance(db, u.id) == bal
    assert client.get("/api/billing/invoices").json()[0]["status"] == "failed"


def test_failed_renewal_retries_then_downgrades(client, db):
    h = authed(client)
    client.post("/api/billing/subscribe", json={"plan_id": "starter"}, headers=h)
    u = user(db)
    u.prefs = {"sim_decline": True}
    db.commit()
    t = utcnow() + timedelta(days=31)
    assert billing.renew_due(db, t)["failed"] == 1
    db.expire_all()
    sub = billing.get_sub(db, u.id)
    assert sub.status == "past_due" and user(db).plan_id == "starter"
    assert billing.renew_due(db, t + timedelta(hours=2))["failed"] == 0  # too early to retry
    for days in (2, 6, 12):
        billing.renew_due(db, t + timedelta(days=days))
    db.expire_all()
    assert user(db).plan_id == "free" and billing.get_sub(db, u.id).status == "cancelled"
    assert db.scalar(select(DevMail).where(DevMail.subject.like("Payment failed%")))


def test_topup_and_idempotency(client, db):
    h = authed(client)
    before = credits.balance(db, user(db).id)
    body = {"pack_id": "pack_100", "currency": "NGN", "idempotency_key": "k1"}
    assert client.post("/api/billing/topup", json=body, headers=h).status_code == 200
    again = client.post("/api/billing/topup", json=body, headers=h)  # double-click / retry
    assert again.json()["message"] == "Already processed."
    db.expire_all()
    assert credits.balance(db, user(db).id) == before + 100
    assert len(client.get("/api/billing/invoices").json()) == 1
    assert client.post("/api/billing/topup", json={"pack_id": "nope"}, headers=h).status_code == 400


def test_ledger_is_append_only_sum(client, db):
    h = authed(client)
    client.post("/api/billing/topup", json={"pack_id": "pack_300"}, headers=h)
    led = client.get("/api/billing/ledger").json()
    assert led["balance"] == sum(e["delta"] for e in led["entries"])


def test_referrals_reward_both_sides(client, db):
    authed(client, "a@example.com")
    code = client.get("/api/referrals").json()["code"]
    client.cookies.clear()
    r = client.post("/api/auth/signup", json={"email": "b@example.com", "password": "password123", "referral_code": code})
    assert r.status_code == 200
    client.cookies.clear()
    client.post("/api/auth/login", json={"email": "a@example.com", "password": "password123"})
    info = client.get("/api/referrals").json()
    assert info["friends"] == 1 and info["earned"] == 10 and info["link"].endswith(f"?ref={code}")


def test_score_good_beats_bad_and_explains():
    good = "Stop wasting 3 hours a day on email. Here is the exact rule I use. Check it once at noon. Reply in two lines. Your inbox stays clean. Follow for more habits."
    bad = "Hello guys welcome to my video today we are basically going to talk about various things that are really very important for productivity optimisation in general"
    g, b = S.score_script(good), S.score_script(bad)
    assert g["score"] >= 75 and b["score"] <= 45 and g["score"] > b["score"] + 30
    assert sum(g["parts"].values()) == g["score"] and b["tips"]
    assert S.score_script("hi")["score"] == 0


def test_score_endpoints_fix_hook_without_key_is_free(client, db):
    h = authed(client)
    bal = credits.balance(db, user(db).id)
    script = "Hello everyone, today I will explain how to save money on data bundles every month in Nigeria."
    r = client.post("/api/score", json={"script": script}, headers=h)
    assert r.status_code == 200 and 0 <= r.json()["score"] <= 100
    f = client.post("/api/score/fix-hook", json={"script": script}, headers=h)
    assert f.status_code == 200 and f.json()["source"] == "template" and len(f.json()["hooks"]) == 3 and f.json()["charged"] == 0
    db.expire_all()
    assert credits.balance(db, user(db).id) == bal  # the failed AI attempt was refunded


def test_clue_card_is_a_png_with_invite(client):
    h = authed(client)
    r = client.post("/api/score/card", json={"script": "Stop scrolling. You need to hear this 1 trick. Follow for more.", "title": "My test"}, headers=h)
    assert r.status_code == 200 and r.content[:8] == b"\x89PNG\r\n\x1a\n" and len(r.content) > 5000
    from io import BytesIO

    from PIL import Image
    assert Image.open(BytesIO(r.content)).size == (1080, 1350)


def test_billing_requires_login(client):
    assert client.get("/api/billing").status_code == 401
    assert client.post("/api/score", json={"script": "x" * 20}).status_code in (401, 403)
