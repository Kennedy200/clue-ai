import io
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from openpyxl import Workbook, load_workbook
from sqlalchemy import select

from clue.api import youtube
from clue.core import credits
from clue.core.ids import utcnow
from clue.core.settings_store import get_setting
from clue.models import AuditLog, DevMail, Invoice, Job, Project, User
from tests.conftest import signup


def mk(client, db, email, plan="business", admin=False, pw="password123"):
    client.cookies.clear()
    client.post("/api/auth/signup", json={"email": email, "password": pw})
    u = db.scalar(select(User).where(User.email == email))
    u.plan_id, u.is_admin = plan, admin
    db.commit()
    return {"x-csrf-token": client.get("/api/auth/me").json()["csrf"]}


def invite_token(db, email):
    m = db.scalars(select(DevMail).where(DevMail.to == email, DevMail.subject.like("%invited you%"))).all()[-1]
    return parse_qs(urlparse(m.body.split("Accept the invite (valid 7 days): ")[1].split("\n")[0]).query)["invite"][0]


def test_team_roles_and_permissions(client, db):
    h = mk(client, db, "owner@example.com")
    tid = client.post("/api/teams", json={"name": "Studio"}, headers=h).json()["id"]
    assert client.post(f"/api/teams/{tid}/invite", json={"email": "ed@example.com", "role": "editor"}, headers=h).status_code == 200
    assert client.post(f"/api/teams/{tid}/invite", json={"email": "vw@example.com", "role": "viewer"}, headers=h).status_code == 200
    ho = h
    mk(client, db, "ed@example.com", plan="free")
    # a stranger cannot use someone else's invite
    hs = mk(client, db, "stranger@example.com", plan="free")
    assert client.post("/api/teams/accept", json={"token": invite_token(db, "ed@example.com")}, headers=hs).status_code == 403
    client.cookies.clear()
    client.post("/api/auth/login", json={"email": "ed@example.com", "password": "password123"})
    he = {"x-csrf-token": client.get("/api/auth/me").json()["csrf"]}
    assert client.post("/api/teams/accept", json={"token": invite_token(db, "ed@example.com")}, headers=he).status_code == 200
    assert client.post("/api/teams/accept", json={"token": invite_token(db, "ed@example.com")}, headers=he).status_code == 400  # single use
    client.cookies.clear()
    client.post("/api/auth/signup", json={"email": "vw@example.com", "password": "password123"})
    hv = {"x-csrf-token": client.get("/api/auth/me").json()["csrf"]}
    assert client.post("/api/teams/accept", json={"token": invite_token(db, "vw@example.com")}, headers=hv).status_code == 200
    # viewer: can read, cannot invite or change roles
    assert client.get(f"/api/teams/{tid}").json()["role"] == "viewer"
    assert client.post(f"/api/teams/{tid}/invite", json={"email": "x@example.com"}, headers=hv).status_code == 403
    uid = db.scalar(select(User.id).where(User.email == "ed@example.com"))
    assert client.put(f"/api/teams/{tid}/members/{uid}", json={"role": "viewer"}, headers=hv).status_code == 403
    # a non-member cannot even see it
    client.cookies.clear()
    client.post("/api/auth/login", json={"email": "stranger@example.com", "password": "password123"})
    assert client.get(f"/api/teams/{tid}").status_code == 404
    # editor cannot make admins; owner can; owner cannot be removed
    client.cookies.clear()
    client.post("/api/auth/login", json={"email": "ed@example.com", "password": "password123"})
    he = {"x-csrf-token": client.get("/api/auth/me").json()["csrf"]}
    assert client.post(f"/api/teams/{tid}/invite", json={"email": "z@example.com"}, headers=he).status_code == 403
    client.cookies.clear()
    client.post("/api/auth/login", json={"email": "owner@example.com", "password": "password123"})
    ho = {"x-csrf-token": client.get("/api/auth/me").json()["csrf"]}
    assert client.put(f"/api/teams/{tid}/members/{uid}", json={"role": "admin"}, headers=ho).status_code == 200
    oid = db.scalar(select(User.id).where(User.email == "owner@example.com"))
    assert client.delete(f"/api/teams/{tid}/members/{oid}", headers=ho).status_code == 400
    assert client.delete(f"/api/teams/{tid}", headers=ho).status_code == 200


def test_team_needs_business_plan(client, db):
    h = mk(client, db, "f@example.com", plan="free")
    assert client.post("/api/teams", json={"name": "Nope"}, headers=h).status_code == 403


def test_brand_kit_gate_apply_and_team_share(client, db):
    h = mk(client, db, "free@example.com", plan="free")
    assert client.post("/api/brand-kits", json={"name": "K"}, headers=h).status_code == 403
    h = mk(client, db, "biz@example.com")
    kit = client.post("/api/brand-kits", json={"name": "Lagos Gold", "caption": {"highlight": "FFD700", "font": "Arial", "uppercase": True}, "is_default": True}, headers=h)
    assert kit.status_code == 200, kit.text
    kid = kit.json()["id"]
    u = db.scalar(select(User).where(User.email == "biz@example.com"))
    p = Project(user_id=u.id, title="t", scene_json={"scenes": [{"text": "hello"}], "captions": {"highlight": "C8FF3D", "size": 84}}, status="done", output_path="u/x.mp4")
    db.add(p)
    db.commit()
    assert client.post(f"/api/projects/{p.id}/apply-brand", json={"kit_id": kid}, headers=h).status_code == 200
    db.refresh(p)
    assert p.scene_json["captions"]["highlight"] == "FFD700" and p.scene_json["captions"]["size"] == 84 and p.version == 1
    # another user cannot use my kit
    h2 = mk(client, db, "other@example.com")
    assert client.post(f"/api/projects/{p.id}/apply-brand", json={"kit_id": kid}, headers=h2).status_code == 404
    assert client.get("/api/brand-kits").json() == []


def test_bulk_csv(client, db):
    h = mk(client, db, "bulk@example.com")
    u = db.scalar(select(User).where(User.email == "bulk@example.com"))
    credits.grant(db, u.id, 100, "test")
    before = credits.balance(db, u.id)
    csv_text = "title,text\nOne,Stop scrolling and listen to this.\nTwo,Here is another short story for you.\n"
    r = client.post("/api/bulk/text-stories", json={"csv": csv_text}, headers=h)
    assert r.status_code == 200 and r.json()["created"] == 2, r.text
    db.expire_all()
    assert credits.balance(db, u.id) == before - 10 and len(db.scalars(select(Job).where(Job.type == "render_text_story")).all()) == 2
    # bad rows are reported, and nothing is charged
    bad = client.post("/api/bulk/text-stories", json={"csv": "title,text\nA,hi\n"}, headers=h)
    assert bad.status_code == 422 and "row 2" in bad.json()["detail"]
    assert client.post("/api/bulk/text-stories", json={"csv": "name,body\nA,hello there friend\n"}, headers=h).status_code == 422
    big = "text\n" + "\n".join(f"story number {i} is here" for i in range(30))
    assert client.post("/api/bulk/text-stories", json={"csv": big}, headers=h).status_code == 422
    # semicolon CSV (common from Excel in Nigeria/Europe) works
    assert client.post("/api/bulk/text-stories", json={"csv": "title;text\nS;a semicolon separated story\n"}, headers=h).json()["created"] == 1
    # not enough credits: nothing created
    low = mk(client, db, "low@example.com")
    lu = db.scalar(select(User).where(User.email == "low@example.com"))
    credits.grant(db, lu.id, -(credits.balance(db, lu.id) - 7), "drain")
    jobs_before = len(db.scalars(select(Job)).all())
    r = client.post("/api/bulk/text-stories", json={"csv": csv_text}, headers=low)  # needs 10, has 7
    assert r.status_code == 402 and len(db.scalars(select(Job)).all()) == jobs_before
    # the free plan cannot use bulk
    fh = mk(client, db, "fr@example.com", plan="free")
    assert client.post("/api/bulk/text-stories", json={"csv": csv_text}, headers=fh).status_code == 403


def test_calendar_crud_ownership_and_publish_pack(client, db):
    h = mk(client, db, "cal@example.com", plan="starter")
    r = client.post("/api/calendar", json={"title": "Monday post", "scheduled_at": "2026-12-01T09:00:00", "platform": "youtube"}, headers=h)
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    assert client.put(f"/api/calendar/{pid}", json={"title": "Monday post", "scheduled_at": "2026-12-02T09:00:00", "status": "published"}, headers=h).json()["status"] == "published"
    assert len(client.get("/api/calendar").json()) == 1
    other = mk(client, db, "cal2@example.com", plan="starter")
    assert client.delete(f"/api/calendar/{pid}", headers=other).status_code == 404
    assert client.post("/api/calendar", json={"title": "x", "scheduled_at": "2026-12-01T09:00:00", "project_id": "nope"}, headers=other).status_code == 404
    u = db.scalar(select(User).where(User.email == "cal2@example.com"))
    p = Project(user_id=u.id, title="Save data", status="done", output_path="u/x.mp4", scene_json={"scenes": [{"text": "Data bundles drain your money. Track data usage weekly and data savings grow."}]})
    db.add(p)
    db.commit()
    pack = client.get(f"/api/projects/{p.id}/publish-pack").json()
    assert "#data" in pack["hashtags"] and pack["title"] == "Save data" and "/api/files?path=u/x.mp4" in pack["download_url"]


def test_analytics(client, db):
    h = mk(client, db, "an@example.com", plan="starter")
    u = db.scalar(select(User).where(User.email == "an@example.com"))
    db.add(Project(user_id=u.id, title="a", style="ranking", status="done", duration=60000))
    db.commit()
    a = client.get("/api/analytics").json()
    assert a["videos"] == 1 and a["by_style"] == {"ranking": 1} and a["minutes_made"] == 1.0


# ---------------- YouTube (mocked Google; never run against the real service here) ----------------
def test_youtube_not_configured_then_oauth_and_upload(client, db, monkeypatch, tmp_path):
    h = mk(client, db, "yt@example.com", plan="starter")
    assert client.get("/api/youtube/status").json() == {"configured": False, "connected": False, "redirect_uri": youtube.redirect_uri()}
    assert client.get("/api/youtube/auth-url").status_code == 400
    ha = mk(client, db, "boss@example.com", plan="business", admin=True)
    assert client.post("/api/admin/youtube", json={"client_id": "cid-123456789", "client_secret": "secret-1"}, headers=ha).status_code == 200
    from clue.core.db import SessionLocal
    with SessionLocal() as s:
        assert get_setting(s, "youtube_client_secret") == "secret-1"
        from clue.models import Setting
        assert s.get(Setting, "youtube_client_secret").encrypted is True  # stored encrypted
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, str(req.url)))
        if req.url.path == "/token":
            body = req.content.decode()
            if "authorization_code" in body:
                return httpx.Response(200, json={"access_token": "a", "refresh_token": "r1"})
            return httpx.Response(200, json={"access_token": "a2"})
        if req.url.path == "/upload/youtube/v3/videos":
            return httpx.Response(200, headers={"location": "https://upload.example/session1"})
        if req.url.host == "upload.example":
            return httpx.Response(200, json={"id": "VID123"})
        return httpx.Response(404)

    monkeypatch.setattr(youtube, "http", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(youtube, "TOKEN_URL", "https://oauth.example/token")
    h = mk(client, db, "yt2@example.com", plan="starter")
    url = client.get("/api/youtube/auth-url").json()["url"]
    q = parse_qs(urlparse(url).query)
    assert q["scope"] == [youtube.SCOPE] and q["access_type"] == ["offline"]
    bad = client.get("/api/youtube/callback?code=x&state=forged", follow_redirects=False)
    assert "bad_state" in bad.headers["location"]
    ok = client.get(f"/api/youtube/callback?code=abc&state={q['state'][0]}", follow_redirects=False)
    assert "yt=connected" in ok.headers["location"]
    assert client.get(f"/api/youtube/callback?code=abc&state={q['state'][0]}", follow_redirects=False).headers["location"].endswith("bad_state")  # state is single use
    assert client.get("/api/youtube/status").json()["connected"] is True
    # publish -> job -> worker
    import clue.jobs.handlers  # noqa: F401
    from clue.core import storage
    from clue.worker import run_once
    u = db.scalar(select(User).where(User.email == "yt2@example.com"))
    out = storage.root() / "u" / "x.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"0" * 2048)
    p = Project(user_id=u.id, title="T", status="done", output_path="u/x.mp4")
    db.add(p)
    db.commit()
    r = client.post("/api/youtube/publish", json={"project_id": p.id, "title": "T", "privacy": "private"}, headers=h)
    assert r.status_code == 200, r.text
    while run_once("w"):
        pass
    db.expire_all()
    job = db.get(Job, r.json()["job_id"])
    assert job.status == "done" and job.result["url"] == "https://youtu.be/VID123", job.error
    # another user cannot publish my project
    h3 = mk(client, db, "yt3@example.com", plan="starter")
    assert client.post("/api/youtube/publish", json={"project_id": p.id, "title": "T"}, headers=h3).status_code == 400  # not connected


# ---------------- admin + xlsx ----------------
def xlsx(sheets: dict) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(r)
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


def test_admin_requires_admin(client, db):
    h = mk(client, db, "n@example.com", plan="free")
    for path in ("/api/admin/users", "/api/admin/dashboard", "/api/admin/export.xlsx", "/api/admin/audit", "/api/admin/plans"):
        assert client.get(path).status_code == 403, path
    assert client.post("/api/admin/import.xlsx", content=b"x", headers=h).status_code == 403


def test_admin_users_credits_suspend_audit(client, db):
    mk(client, db, "victim@example.com", plan="free")
    vid = db.scalar(select(User.id).where(User.email == "victim@example.com"))
    h = mk(client, db, "root@example.com", admin=True)
    assert any(u["email"] == "victim@example.com" for u in client.get("/api/admin/users?q=vict").json())
    r = client.post(f"/api/admin/users/{vid}/credits", json={"amount": 25, "reason": "support goodwill"}, headers=h)
    assert r.status_code == 200
    assert client.post(f"/api/admin/users/{vid}/credits", json={"amount": -9999, "reason": "too much"}, headers=h).status_code == 400
    assert client.post(f"/api/admin/users/{vid}/suspend", json={"suspended": True}, headers=h).status_code == 200
    rid = db.scalar(select(User.id).where(User.email == "root@example.com"))
    assert client.post(f"/api/admin/users/{rid}/suspend", json={"suspended": True}, headers=h).status_code == 400
    client.cookies.clear()
    assert client.post("/api/auth/login", json={"email": "victim@example.com", "password": "password123"}).status_code in (401, 403)
    client.post("/api/auth/login", json={"email": "root@example.com", "password": "password123"})
    actions = [a["action"] for a in client.get("/api/admin/audit").json()]
    assert "credits.adjust" in actions and "user.suspend" in actions


def test_admin_dashboard_numbers(client, db):
    h = mk(client, db, "root@example.com", admin=True)
    client.post("/api/billing/subscribe", json={"plan_id": "starter"}, headers=h)
    from clue.models import ApiUsage
    db.add(ApiUsage(provider="openrouter", model="m", feature="plan", tokens_in=100, tokens_out=50, cost_usd_micro=2000, ok=True))
    db.add(ApiUsage(provider="openrouter", model="m", feature="plan", tokens_in=0, tokens_out=0, cost_usd_micro=0, ok=False))
    db.add(Project(user_id=db.scalar(select(User.id)), title="x", status="done"))
    db.commit()
    d = client.get("/api/admin/dashboard").json()
    assert d["users"] == 1 and d["paid_subscribers"] == 1 and d["revenue_30d_minor"]["NGN"] == 990000
    assert d["llm"]["by_feature"]["plan"] == {"calls": 2, "usd": 0.002, "failed": 1} and d["llm"]["usd_per_video"] == 0.002


def test_xlsx_export_has_sheets_and_blocks_formula_injection(client, db):
    h = mk(client, db, "root@example.com", admin=True)
    u = db.scalar(select(User))
    u.name = "=HYPERLINK(\"http://evil\",\"x\")"
    db.commit()
    r = client.get("/api/admin/export.xlsx")
    assert r.status_code == 200
    wb = load_workbook(io.BytesIO(r.content))
    assert {"Plans", "Users", "Invoices", "Ledger", "LlmUsage", "CreditGrants"} <= set(wb.sheetnames)
    names = [row[1] for row in wb["Users"].iter_rows(min_row=2, values_only=True)]
    assert names[0].startswith("'=")  # neutralised
    assert [c.value for c in wb["Plans"][1]] == ["id", "name", "price_ngn_month", "price_usd_month", "monthly_credits"]


def test_xlsx_import_validates_then_applies_atomically(client, db):
    h = mk(client, db, "root@example.com", admin=True)
    mk(client, db, "target@example.com", plan="free")
    tid = db.scalar(select(User.id).where(User.email == "target@example.com"))
    client.cookies.clear()
    client.post("/api/auth/login", json={"email": "root@example.com", "password": "password123"})
    h = {"x-csrf-token": client.get("/api/auth/me").json()["csrf"]}
    good = xlsx({"Plans": [["id", "name", "price_ngn_month", "price_usd_month", "monthly_credits"], ["starter", "Starter", 8900, 650, 250]],
                 "CreditGrants": [["email", "amount", "reason"], ["target@example.com", 40, "launch promo"]]})
    dry = client.post("/api/admin/import.xlsx", content=good, headers=h).json()
    assert dry["ok"] and not dry["applied"] and dry["summary"] == {"plans": 1, "grants": 1, "credits_total": 40}
    from clue.models import Plan
    assert db.get(Plan, "starter").price_ngn_month == 9900  # a dry run changes nothing
    before = credits.balance(db, tid)
    assert client.post("/api/admin/import.xlsx?apply=true", content=good, headers=h).json()["applied"]
    db.expire_all()
    assert db.get(Plan, "starter").price_ngn_month == 8900 and credits.balance(db, tid) == before + 40
    # one bad row stops everything, with row numbers
    bad = xlsx({"Plans": [["id", "name", "price_ngn_month", "price_usd_month", "monthly_credits"], ["creator", "Creator", 1000, 100, 10], ["ghost", "G", 1, 1, 1], ["free", "Free", 500, 0, 15]],
                "CreditGrants": [["email", "amount", "reason"], ["nobody@example.com", 5, "x"], ["target@example.com", -9999, "too big"]]})
    r = client.post("/api/admin/import.xlsx?apply=true", content=bad, headers=h).json()
    assert not r["ok"] and not r["applied"] and len(r["errors"]) >= 4
    assert any(e["row"] == 3 and "ghost" in e["error"] for e in r["errors"])
    db.expire_all()
    assert db.get(Plan, "creator").price_ngn_month == 19900  # nothing applied
    assert client.post("/api/admin/import.xlsx", content=b"not a spreadsheet", headers=h).status_code == 422
    assert client.post("/api/admin/import.xlsx", content=b"", headers=h).status_code == 422
    assert db.scalar(select(AuditLog).where(AuditLog.action == "xlsx.import")) is not None


def test_ledger_reconciliation_finds_and_fixes_stuck_reservations(client, db):
    from datetime import timedelta

    from clue.models import CreditLedger

    h = mk(client, db, "root@example.com", admin=True)
    u = db.scalar(select(User).where(User.email == "root@example.com"))
    base = credits.balance(db, u.id)
    assert client.get("/api/admin/reconcile").json()["ok"] is True
    # a crash left 5 credits reserved for a job that is gone (made 2 hours ago)
    credits.reserve(db, u.id, 5, "render fast", "lost-ref")
    row = db.scalar(select(CreditLedger).where(CreditLedger.ref_id == "lost-ref"))
    row.created_at = utcnow() - timedelta(hours=2)
    # a fresh reservation (2 minutes old) must NOT be touched
    credits.reserve(db, u.id, 3, "render fast", "fresh-ref")
    # a reservation whose job is still running is fine
    credits.reserve(db, u.id, 2, "render fast", "busy-ref")
    db.scalar(select(CreditLedger).where(CreditLedger.ref_id == "busy-ref")).created_at = utcnow() - timedelta(hours=2)
    db.add(Job(type="render_video", status="running", user_id=u.id, payload={}, credit_ref="busy-ref"))
    db.commit()
    r = client.get("/api/admin/reconcile").json()
    assert [o["ref_id"] for o in r["orphan_reservations"]] == ["lost-ref"] and not r["ok"]
    fixed = client.post("/api/admin/reconcile/fix", headers=h).json()
    assert fixed["refunded"] == 1 and fixed["credits"] == 5 and fixed["ok"] is True
    assert credits.balance(db, u.id) == base - 3 - 2  # only the legitimate holds remain
    assert client.post("/api/admin/reconcile/fix", headers=h).json()["refunded"] == 0  # idempotent
    assert db.scalar(select(AuditLog).where(AuditLog.action == "ledger.reconcile_fix"))
    assert client.get("/api/admin/reconcile").status_code == 200
    mk(client, db, "plain@example.com", plan="free")
    assert client.get("/api/admin/reconcile").status_code == 403
