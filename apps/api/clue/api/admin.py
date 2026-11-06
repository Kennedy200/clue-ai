"""Admin panel API: users, credits, plans, audit log, cost dashboard, and .xlsx export/import."""
from __future__ import annotations

import io
from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from openpyxl import Workbook, load_workbook
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from clue.api.deps import admin_user
from clue.core import credits
from clue.core.db import get_db
from clue.core.ids import utcnow
from clue.models import ApiUsage, AuditLog, CreditLedger, Invoice, Job, Plan, Project, Subscription, User

router = APIRouter(prefix="/admin", tags=["admin"])
MAX_XLSX = 2 * 1024 * 1024


def audit(db: Session, actor: User, action: str, **detail) -> None:
    db.add(AuditLog(actor_id=actor.id, action=action, detail=detail))
    db.commit()


# ---------- users ----------
def _user_row(db: Session, u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "plan_id": u.plan_id, "is_admin": u.is_admin, "is_suspended": u.is_suspended,
            "credits": credits.balance(db, u.id), "created_at": u.created_at.isoformat(), "verified": u.email_verified}


@router.get("/users")
def users(q: str = "", a: User = Depends(admin_user), db: Session = Depends(get_db)):
    stmt = select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc()).limit(100)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(func.lower(User.email).like(like) | func.lower(User.name).like(like))
    return [_user_row(db, u) for u in db.scalars(stmt)]


def _target(db: Session, uid: str) -> User:
    u = db.get(User, uid)
    if u is None or u.deleted_at:
        raise HTTPException(404, "User not found.")
    return u


class Suspend(BaseModel):
    suspended: bool


@router.post("/users/{uid}/suspend")
def suspend(uid: str, body: Suspend, a: User = Depends(admin_user), db: Session = Depends(get_db)):
    u = _target(db, uid)
    if u.id == a.id:
        raise HTTPException(400, "You cannot suspend yourself.")
    u.is_suspended = body.suspended
    db.commit()
    audit(db, a, "user.suspend" if body.suspended else "user.unsuspend", user=u.email)
    return {"ok": True}


class Adjust(BaseModel):
    amount: int = Field(ge=-100000, le=100000)
    reason: str = Field(min_length=3, max_length=120)


@router.post("/users/{uid}/credits")
def adjust_credits(uid: str, body: Adjust, a: User = Depends(admin_user), db: Session = Depends(get_db)):
    u = _target(db, uid)
    if body.amount == 0:
        raise HTTPException(422, "Enter a non-zero amount.")
    if body.amount < 0 and credits.balance(db, u.id) + body.amount < 0:
        raise HTTPException(400, "That would make the balance negative.")
    credits.grant(db, u.id, body.amount, f"admin: {body.reason}")
    audit(db, a, "credits.adjust", user=u.email, amount=body.amount, reason=body.reason)
    return {"balance": credits.balance(db, u.id)}


class SetPlan(BaseModel):
    plan_id: str


@router.post("/users/{uid}/plan")
def set_plan(uid: str, body: SetPlan, a: User = Depends(admin_user), db: Session = Depends(get_db)):
    u = _target(db, uid)
    if db.get(Plan, body.plan_id) is None:
        raise HTTPException(404, "Unknown plan.")
    u.plan_id = body.plan_id
    db.commit()
    audit(db, a, "user.plan", user=u.email, plan=body.plan_id)
    return {"ok": True}


# ---------- plans ----------
@router.get("/plans")
def plans(a: User = Depends(admin_user), db: Session = Depends(get_db)):
    return [{"id": p.id, "name": p.name, "price_ngn_month": p.price_ngn_month, "price_usd_month": p.price_usd_month, "monthly_credits": p.monthly_credits, "features": p.features}
            for p in db.scalars(select(Plan).order_by(Plan.sort))]


class PlanEdit(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    price_ngn_month: int = Field(ge=0, le=100_000_000)
    price_usd_month: int = Field(ge=0, le=10_000_000)
    monthly_credits: int = Field(ge=0, le=1_000_000)


@router.put("/plans/{pid}")
def edit_plan(pid: str, body: PlanEdit, a: User = Depends(admin_user), db: Session = Depends(get_db)):
    p = db.get(Plan, pid)
    if p is None:
        raise HTTPException(404, "Unknown plan.")
    if pid == "free" and (body.price_ngn_month or body.price_usd_month):
        raise HTTPException(400, "The Free plan must stay free.")
    p.name, p.price_ngn_month, p.price_usd_month, p.monthly_credits = body.name.strip(), body.price_ngn_month, body.price_usd_month, body.monthly_credits
    db.commit()
    audit(db, a, "plan.edit", plan=pid, **body.model_dump())
    return {"ok": True}


# ---------- audit + dashboard ----------
@router.get("/audit")
def audit_log(a: User = Depends(admin_user), db: Session = Depends(get_db)):
    emails = {u.id: u.email for u in db.scalars(select(User))}
    return [{"at": r.created_at.isoformat(), "actor": emails.get(r.actor_id or "", "system"), "action": r.action, "detail": r.detail}
            for r in db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200))]


@router.get("/dashboard")
def dashboard(a: User = Depends(admin_user), db: Session = Depends(get_db)):
    now = utcnow()
    since = now - timedelta(days=30)
    revenue: dict[str, int] = defaultdict(int)
    for cur, amt in db.execute(select(Invoice.currency, func.sum(Invoice.amount)).where(Invoice.status == "paid", Invoice.created_at >= since).group_by(Invoice.currency)):
        revenue[cur] = int(amt or 0)
    cost_feat: dict[str, dict] = {}
    for feat, n, micro, fails in db.execute(select(ApiUsage.feature, func.count(), func.sum(ApiUsage.cost_usd_micro), func.sum(case((ApiUsage.ok.is_(True), 0), else_=1))).where(ApiUsage.created_at >= since).group_by(ApiUsage.feature)):
        cost_feat[feat] = {"calls": n, "usd": round((micro or 0) / 1_000_000, 4), "failed": int(fails or 0)}
    total_calls = sum(v["calls"] for v in cost_feat.values())
    videos = db.scalar(select(func.count()).select_from(Project).where(Project.status == "done", Project.created_at >= since)) or 0
    total_usd = round(sum(v["usd"] for v in cost_feat.values()), 4)
    return {
        "users": db.scalar(select(func.count()).select_from(User).where(User.deleted_at.is_(None))) or 0,
        "new_users_7d": db.scalar(select(func.count()).select_from(User).where(User.created_at >= now - timedelta(days=7))) or 0,
        "paid_subscribers": db.scalar(select(func.count()).select_from(Subscription).where(Subscription.status.in_(["active", "past_due"]))) or 0,
        "videos_30d": videos, "revenue_30d_minor": dict(revenue),
        "jobs": dict(db.execute(select(Job.status, func.count()).group_by(Job.status)).all()),
        "llm": {"calls_30d": total_calls, "usd_30d": total_usd, "by_feature": cost_feat, "usd_per_video": round(total_usd / videos, 4) if videos else None},
        "credits_in_circulation": int(db.scalar(select(func.coalesce(func.sum(CreditLedger.delta), 0))) or 0),
    }


# ---------- xlsx ----------
def _safe(v):
    """Stop spreadsheet formula injection: a text cell starting with = + - @ would run as a formula in Excel."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


def _sheet(wb: Workbook, title: str, headers: list[str], rows) -> None:
    ws = wb.create_sheet(title)
    ws.append(headers)
    for r in rows:
        ws.append([_safe(c) for c in r])
    for i, h in enumerate(headers, start=1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = max(12, min(40, len(h) + 4))


@router.get("/export.xlsx")
def export_xlsx(a: User = Depends(admin_user), db: Session = Depends(get_db)):
    wb = Workbook()
    wb.remove(wb.active)
    _sheet(wb, "Plans", ["id", "name", "price_ngn_month", "price_usd_month", "monthly_credits"],
           [(p.id, p.name, p.price_ngn_month, p.price_usd_month, p.monthly_credits) for p in db.scalars(select(Plan).order_by(Plan.sort))])
    _sheet(wb, "Users", ["email", "name", "plan", "credits", "admin", "suspended", "created"],
           [(u.email, u.name, u.plan_id, credits.balance(db, u.id), u.is_admin, u.is_suspended, u.created_at.isoformat()) for u in db.scalars(select(User).where(User.deleted_at.is_(None)))])
    emails = {u.id: u.email for u in db.scalars(select(User))}
    _sheet(wb, "Invoices", ["number", "email", "kind", "description", "amount_minor", "currency", "status", "date"],
           [(i.number, emails.get(i.user_id, ""), i.kind, i.description, i.amount, i.currency, i.status, i.created_at.isoformat()) for i in db.scalars(select(Invoice).order_by(Invoice.created_at))])
    _sheet(wb, "Ledger", ["email", "delta", "kind", "reason", "date"],
           [(emails.get(l.user_id, ""), l.delta, l.kind, l.reason, l.created_at.isoformat()) for l in db.scalars(select(CreditLedger).order_by(CreditLedger.created_at).limit(20000))])
    _sheet(wb, "LlmUsage", ["feature", "model", "tokens_in", "tokens_out", "usd", "ok", "date"],
           [(x.feature, x.model, x.tokens_in, x.tokens_out, x.cost_usd_micro / 1_000_000, x.ok, x.created_at.isoformat()) for x in db.scalars(select(ApiUsage).order_by(ApiUsage.created_at).limit(20000))])
    _sheet(wb, "CreditGrants", ["email", "amount", "reason"], [])  # an empty template for the import below
    buf = io.BytesIO()
    wb.save(buf)
    return Response(buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="clue-export.xlsx"'})


def _rows(ws):
    it = ws.iter_rows(values_only=True)
    head = [str(h or "").strip().lower() for h in next(it, [])]
    for n, r in enumerate(it, start=2):
        if all(c is None or str(c).strip() == "" for c in r):
            continue
        yield n, dict(zip(head, r))


def _int(v, lo: int, hi: int, name: str) -> int:
    try:
        if isinstance(v, bool) or (isinstance(v, float) and v != int(v)):
            raise ValueError
        n = int(str(v).strip())
    except (ValueError, TypeError):
        raise ValueError(f"{name} must be a whole number")
    if not lo <= n <= hi:
        raise ValueError(f"{name} must be between {lo} and {hi}")
    return n


@router.post("/import.xlsx")
async def import_xlsx(request: Request, apply: bool = False, a: User = Depends(admin_user), db: Session = Depends(get_db)):
    """Body = the .xlsx bytes. Sheets understood: Plans (updates by id) and CreditGrants (email, amount, reason).
    Without ?apply=true it only validates and reports what would change. Nothing is applied unless every row is valid."""
    data = await request.body()
    if not data or len(data) > MAX_XLSX:
        raise HTTPException(413 if data else 422, "Upload an .xlsx file up to 2 MB.")
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:
        raise HTTPException(422, "That is not a valid .xlsx file.")
    errors, plan_ops, grants = [], [], []
    if "Plans" in wb.sheetnames:
        for n, r in _rows(wb["Plans"]):
            try:
                pid = str(r.get("id") or "").strip()
                p = db.get(Plan, pid)
                if p is None:
                    raise ValueError(f"unknown plan id '{pid}' (new plans are not created from Excel)")
                ngn, usd, cr = _int(r.get("price_ngn_month"), 0, 100_000_000, "price_ngn_month"), _int(r.get("price_usd_month"), 0, 10_000_000, "price_usd_month"), _int(r.get("monthly_credits"), 0, 1_000_000, "monthly_credits")
                name = str(r.get("name") or "").strip()
                if not name or len(name) > 80:
                    raise ValueError("name is required (80 characters max)")
                if pid == "free" and (ngn or usd):
                    raise ValueError("the Free plan must stay free")
                plan_ops.append((p, name, ngn, usd, cr))
            except ValueError as e:
                errors.append({"sheet": "Plans", "row": n, "error": str(e)})
    if "CreditGrants" in wb.sheetnames:
        for n, r in _rows(wb["CreditGrants"]):
            try:
                email = str(r.get("email") or "").strip().lower()
                u = db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
                if u is None:
                    raise ValueError(f"no user with email '{email}'")
                amt = _int(r.get("amount"), -100000, 100000, "amount")
                if amt == 0:
                    raise ValueError("amount cannot be 0")
                reason = str(r.get("reason") or "").strip()
                if len(reason) < 3:
                    raise ValueError("reason is required (3+ characters)")
                grants.append((u, amt, reason[:100]))
            except ValueError as e:
                errors.append({"sheet": "CreditGrants", "row": n, "error": str(e)})
    if not plan_ops and not grants and not errors:
        raise HTTPException(422, "No Plans or CreditGrants rows found. Download the export to see the expected sheets.")
    # a negative grant must not push anyone below zero (counting several rows for the same person)
    running: dict[str, int] = {}
    for u, amt, _ in grants:
        running[u.id] = running.get(u.id, credits.balance(db, u.id)) + amt
        if running[u.id] < 0 and not any(e["error"].startswith(f"balance for {u.email}") for e in errors):
            errors.append({"sheet": "CreditGrants", "row": 0, "error": f"balance for {u.email} would go negative"})
    summary = {"plans": len(plan_ops), "grants": len(grants), "credits_total": sum(g[1] for g in grants)}
    if errors:
        return {"ok": False, "applied": False, "errors": errors[:50], "summary": summary}
    if apply:
        for p, name, ngn, usd, cr in plan_ops:
            p.name, p.price_ngn_month, p.price_usd_month, p.monthly_credits = name, ngn, usd, cr
        db.commit()
        for u, amt, reason in grants:
            credits.grant(db, u.id, amt, f"admin import: {reason}")
        audit(db, a, "xlsx.import", **summary)
    return {"ok": True, "applied": apply, "errors": [], "summary": summary}
