"""Money endpoints: plans/billing/invoices/credit history, referrals, and the Clue Score tools."""
from __future__ import annotations

import html
import re

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clue.ai import score as S
from clue.ai.llm import LLMError
from clue.ai.prompts import tools as P
from clue.api.creative import COST, _guard
from clue.api.deps import admin_user, current_user
from clue.core import billing, credits
from clue.core.config import get_settings
from clue.core.db import get_db
from clue.core.ratelimit import limit
from clue.models import CreditLedger, Invoice, User
from clue.render.card import make_card

router = APIRouter(tags=["money"])


# ---------- billing ----------
@router.get("/billing")
def billing_view(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return {**billing.view(db, u), "mode": get_settings().app_mode}


class SubscribeReq(BaseModel):
    plan_id: str = Field(max_length=40)
    interval: str = Field(default="month", pattern="^(month|year)$")
    currency: str = Field(default="NGN", pattern="^(NGN|USD)$")


def _run(fn, *a):
    try:
        return fn(*a)
    except billing.BillingError as e:
        raise HTTPException(400, str(e))


@router.post("/billing/subscribe", dependencies=[Depends(limit("billing", 20, 60))])
def subscribe(body: SubscribeReq, u: User = Depends(current_user), db: Session = Depends(get_db)):
    return _run(billing.subscribe, db, u, body.plan_id, body.interval, body.currency)


@router.post("/billing/cancel")
def cancel(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return _run(billing.cancel, db, u)


class TopupReq(BaseModel):
    pack_id: str = Field(max_length=40)
    currency: str = Field(default="NGN", pattern="^(NGN|USD)$")
    idempotency_key: str | None = Field(default=None, max_length=40)


@router.post("/billing/topup", dependencies=[Depends(limit("billing", 20, 60))])
def topup(body: TopupReq, u: User = Depends(current_user), db: Session = Depends(get_db)):
    return _run(billing.top_up, db, u, body.pack_id, body.currency, body.idempotency_key)


def _inv(i: Invoice) -> dict:
    return {"id": i.id, "number": i.number, "kind": i.kind, "description": i.description, "amount": i.amount, "currency": i.currency,
            "display": billing.money(i.amount, i.currency), "status": i.status, "date": i.created_at.isoformat()}


@router.get("/billing/invoices")
def invoices(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Invoice).where(Invoice.user_id == u.id).order_by(Invoice.created_at.desc()).limit(100)).all()
    return [_inv(i) for i in rows]


@router.get("/billing/invoices/{iid}/html")
def invoice_html(iid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    i = db.get(Invoice, iid)
    if i is None or i.user_id != u.id:
        raise HTTPException(404, "Invoice not found.")
    e = html.escape
    rows = "".join(f"<tr><td>{e(str(l['label']))}</td><td style='text-align:right'>{e(billing.money(l['amount'], i.currency))}</td></tr>" for l in i.lines)
    body = (f"<!doctype html><meta charset='utf-8'><title>Invoice {e(i.number)}</title>"
            "<style>body{font:16px system-ui;max-width:640px;margin:40px auto;padding:0 16px;color:#0e0b1f}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}table{width:100%;border-collapse:collapse}</style>"
            f"<h1>Clue AI</h1><h2>Invoice {e(i.number)}</h2><p>{e(u.email)}<br>{i.created_at:%d %b %Y} &middot; Status: <b>{e(i.status)}</b></p>"
            f"<table><tr><th>Item</th><th style='text-align:right'>Amount</th></tr>{rows}"
            f"<tr><th>Total</th><th style='text-align:right'>{e(billing.money(i.amount, i.currency))}</th></tr></table>"
            "<p style='color:#666;font-size:13px'>Simulated payment from the built-in billing engine. No real money moved on this installation.</p>"
            "<p><button onclick='print()'>Print or save as PDF</button></p>")
    return Response(body, media_type="text/html", headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'"})


@router.get("/billing/ledger")
def ledger(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(CreditLedger).where(CreditLedger.user_id == u.id, CreditLedger.kind != "settle").order_by(CreditLedger.created_at.desc()).limit(100)).all()
    return {"balance": credits.balance(db, u.id), "entries": [{"date": r.created_at.isoformat(), "delta": r.delta, "kind": r.kind, "reason": r.reason} for r in rows]}


@router.post("/admin/billing/run")
def run_renewals(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    return billing.renew_due(db)


# ---------- referrals ----------
@router.get("/referrals")
def referrals(u: User = Depends(current_user), db: Session = Depends(get_db)):
    s = get_settings()
    n = db.scalar(select(func.count()).select_from(User).where(User.referred_by == u.id)) or 0
    earned = db.scalar(select(func.coalesce(func.sum(CreditLedger.delta), 0)).where(CreditLedger.user_id == u.id, CreditLedger.reason == "referral reward")) or 0
    return {"code": u.referral_code, "link": f"{s.site_url}/signup?ref={u.referral_code}", "friends": n, "earned": int(earned),
            "reward": 10 if s.app_mode == "saas" else 0, "mode": s.app_mode}


# ---------- Clue Score ----------
class ScoreReq(BaseModel):
    script: str = Field(min_length=10, max_length=6000)
    seconds: int | None = Field(default=None, ge=10, le=180)


@router.post("/score", dependencies=[Depends(limit("score", 30, 60))])
def score(body: ScoreReq, u: User = Depends(current_user)):
    return S.score_script(body.script, body.seconds)


@router.post("/score/fix-hook", dependencies=[Depends(limit("score", 30, 60))])
def fix_hook(body: ScoreReq, u: User = Depends(current_user), db: Session = Depends(get_db)):
    """Uses AI (1 credit) when a key is set; otherwise free template hooks so the button always works."""
    before = S.score_script(body.script, body.seconds)
    templates = S.template_hooks(body.script)
    try:
        with _guard(db, u, COST["enhance"], "fix my hook"):
            enh = P.enhance_script(db, body.script, "hook", body.seconds, "standard", u.id)
    except LLMError:
        return {"source": "template", "hooks": templates, "charged": 0, "before": before["score"]}
    first = re.split(r"(?<=[.!?])\s+", enh.script.strip(), maxsplit=1)[0]
    after = S.score_script(enh.script, body.seconds)
    return {"source": "ai", "hooks": [first, *templates[:2]], "script": enh.script, "changes": enh.changes, "charged": COST["enhance"],
            "before": before["score"], "after": after["score"]}


class CardReq(ScoreReq):
    title: str = Field(default="", max_length=120)


@router.post("/score/card", dependencies=[Depends(limit("score", 30, 60))])
def card(body: CardReq, u: User = Depends(current_user)):
    s = get_settings()
    png = make_card(S.score_script(body.script, body.seconds), body.title, f"{s.site_url.split('//')[-1]}/signup?ref={u.referral_code}")
    return Response(png, media_type="image/png", headers={"Content-Disposition": 'attachment; filename="clue-card.png"'})
