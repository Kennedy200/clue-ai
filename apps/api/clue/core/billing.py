"""Built-in ("internal") billing engine.

The gateway here is simulated: it never moves real money. A payment-gateway plugin can replace `Gateway`.
All amounts are minor units (kobo / cents). Annual = 50% off, i.e. 6x the monthly price, billed once.
Plan credits are granted when a period starts (annual: 12 months at once) and do not expire.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from clue.core import credits
from clue.core.ids import utcnow
from clue.core.mail import send_mail
from clue.models import Invoice, Plan, Subscription, User

TOPUPS = {  # id: (credits, NGN kobo, USD cents)
    "pack_100": (100, 600_000, 450),
    "pack_300": (300, 1_500_000, 1100),
    "pack_1000": (1000, 4_500_000, 3300),
}
RETRY_DAYS = [1, 3, 5]  # after a failed renewal; one more failure drops the user to Free
PERIOD = {"month": timedelta(days=30), "year": timedelta(days=365)}


class BillingError(Exception):
    pass


class Gateway:
    """Simulated card gateway. A user can be marked `prefs.sim_decline = true` to test failures."""

    name = "internal"

    def charge(self, user: User, amount: int, currency: str) -> bool:
        if amount <= 0:
            return True
        return not (user.prefs or {}).get("sim_decline")


gateway = Gateway()


def plan_price(plan: Plan, interval: str, currency: str) -> int:
    monthly = plan.price_ngn_month * 100 if currency == "NGN" else plan.price_usd_month
    return monthly * 6 if interval == "year" else monthly


def _credits_for(plan: Plan, interval: str) -> int:
    return plan.monthly_credits * (12 if interval == "year" else 1)


def money(amount: int, cur: str) -> str:
    return f"₦{amount / 100:,.2f}" if cur == "NGN" else f"${amount / 100:,.2f}"


def _next_number(db: Session) -> str:
    n = (db.scalar(select(func.count()).select_from(Invoice)) or 0) + 1
    return f"CLUE-{utcnow().year}-{n:06d}"


def _invoice(db: Session, user: User, kind: str, desc: str, amount: int, cur: str, status: str, lines: list, idem: str | None = None) -> Invoice:
    for _ in range(5):
        inv = Invoice(number=_next_number(db), user_id=user.id, kind=kind, description=desc, amount=amount, currency=cur,
                      status=status, lines=lines, idem_key=idem, paid_at=utcnow() if status == "paid" else None)
        db.add(inv)
        try:
            db.commit()
            return inv
        except IntegrityError:
            db.rollback()
            if idem and (ex := db.scalar(select(Invoice).where(Invoice.idem_key == idem))):
                return ex
    raise BillingError("Could not create the invoice. Please try again.")


def _receipt(db: Session, user: User, inv: Invoice) -> None:
    body = f"Thanks for your payment.\n\nInvoice {inv.number}\n{inv.description}\nTotal: {money(inv.amount, inv.currency)}\n\n(Simulated payment: no real money moved.)"
    send_mail(db, user.email, f"Clue AI receipt {inv.number}", body)


def get_sub(db: Session, user_id: str) -> Subscription | None:
    return db.scalar(select(Subscription).where(Subscription.user_id == user_id))


def _start_period(db: Session, user: User, sub: Subscription, plan: Plan, now: datetime) -> None:
    sub.plan_id, sub.status, sub.failed_attempts, sub.next_retry_at = plan.id, "active", 0, None
    sub.period_start, sub.period_end = now, now + PERIOD[sub.interval]
    sub.pending_plan_id = sub.pending_interval = None
    user.plan_id = plan.id
    db.commit()
    credits.grant(db, user.id, _credits_for(plan, sub.interval), f"{plan.name} plan credits", ref_id=f"plan:{sub.id}:{now:%Y%m%d%H%M%S}")


def subscribe(db: Session, user: User, plan_id: str, interval: str = "month", currency: str = "NGN", now: datetime | None = None) -> dict:
    """Start or change a plan. Upgrades are charged now (prorated); downgrades wait for the period end."""
    now = now or utcnow()
    plan = db.get(Plan, plan_id)
    if plan is None or interval not in PERIOD or currency not in ("NGN", "USD"):
        raise BillingError("Unknown plan.")
    if plan.id == "free":
        return cancel(db, user)
    sub = get_sub(db, user.id)
    cur_plan = db.get(Plan, sub.plan_id) if sub and sub.status != "cancelled" else None
    same = bool(sub and cur_plan and cur_plan.id == plan.id and sub.interval == interval)
    if same and not sub.cancel_at_period_end:
        raise BillingError("You are already on this plan.")
    if same and sub.cancel_at_period_end:
        sub.cancel_at_period_end = False  # changed their mind: keep it
        db.commit()
        return {"ok": True, "message": "Your plan will keep renewing."}

    new_price = plan_price(plan, interval, currency)
    paid_now = bool(sub and cur_plan and cur_plan.id != "free" and sub.status == "active" and sub.currency == currency)
    if paid_now and new_price <= plan_price(cur_plan, sub.interval, currency):
        sub.pending_plan_id, sub.pending_interval, sub.cancel_at_period_end = plan.id, interval, False
        db.commit()
        return {"ok": True, "message": f"You'll move to {plan.name} on {sub.period_end:%d %b %Y}. Until then you keep {cur_plan.name}."}

    amount, lines = new_price, [{"label": f"{plan.name} ({'yearly' if interval == 'year' else 'monthly'})", "amount": new_price}]
    if paid_now:
        total, left = (sub.period_end - sub.period_start).total_seconds(), max(0.0, (sub.period_end - now).total_seconds())
        credit = int(plan_price(cur_plan, sub.interval, currency) * (left / total)) if total else 0
        amount = max(0, new_price - credit)
        lines.append({"label": f"Unused time on {cur_plan.name}", "amount": -credit})
    kind = "upgrade" if paid_now else "subscription"
    desc = f"{plan.name} plan, {'yearly' if interval == 'year' else 'monthly'}"
    if not gateway.charge(user, amount, currency):
        _invoice(db, user, kind, desc, amount, currency, "failed", lines)
        raise BillingError("Your payment was declined. Nothing was charged and your plan has not changed.")
    inv = _invoice(db, user, kind, desc, amount, currency, "paid", lines)
    if sub is None:
        sub = Subscription(user_id=user.id, plan_id=plan.id, interval=interval, currency=currency, period_start=now, period_end=now)
        db.add(sub)
        db.flush()
    sub.interval, sub.currency, sub.cancel_at_period_end = interval, currency, False
    _start_period(db, user, sub, plan, now)
    _receipt(db, user, inv)
    return {"ok": True, "message": f"You're on {plan.name}.", "invoice": inv.number}


def cancel(db: Session, user: User) -> dict:
    sub = get_sub(db, user.id)
    if sub is None or sub.status == "cancelled" or sub.plan_id == "free":
        raise BillingError("You don't have a paid plan to cancel.")
    sub.cancel_at_period_end, sub.pending_plan_id = True, None
    db.commit()
    send_mail(db, user.email, "Your Clue AI plan will end", f"Your plan stays active until {sub.period_end:%d %b %Y}, then moves to Free. You keep your credits.")
    return {"ok": True, "message": f"Cancelled. You keep your plan until {sub.period_end:%d %b %Y}."}


def top_up(db: Session, user: User, pack_id: str, currency: str = "NGN", idem: str | None = None) -> dict:
    pack = TOPUPS.get(pack_id)
    if pack is None or currency not in ("NGN", "USD"):
        raise BillingError("Unknown credit pack.")
    n, ngn, usd = pack
    amount = ngn if currency == "NGN" else usd
    if idem:
        idem = f"{user.id}:{idem}"[:64]
        if ex := db.scalar(select(Invoice).where(Invoice.idem_key == idem)):
            return {"ok": True, "message": "Already processed.", "invoice": ex.number, "credits": credits.balance(db, user.id)}
    desc = f"{n} credits top-up"
    lines = [{"label": desc, "amount": amount}]
    if not gateway.charge(user, amount, currency):
        _invoice(db, user, "topup", desc, amount, currency, "failed", lines)
        raise BillingError("Your payment was declined. Nothing was charged.")
    inv = _invoice(db, user, "topup", desc, amount, currency, "paid", lines, idem)
    credits.grant(db, user.id, n, desc, ref_id=f"topup:{inv.id}")
    _receipt(db, user, inv)
    return {"ok": True, "message": f"{n} credits added.", "invoice": inv.number, "credits": credits.balance(db, user.id)}


def renew_due(db: Session, now: datetime | None = None) -> dict:
    """Run by the worker every few minutes: renew, retry failed payments, apply cancellations."""
    now = now or utcnow()
    out = {"renewed": 0, "ended": 0, "failed": 0, "downgraded": 0}
    subs = db.scalars(select(Subscription).where(Subscription.period_end <= now, Subscription.status != "cancelled")).all()
    for sub in subs:
        user = db.get(User, sub.user_id)
        if user is None:
            continue
        if sub.status == "past_due" and sub.next_retry_at and sub.next_retry_at > now:
            continue
        if sub.cancel_at_period_end:
            sub.status, sub.plan_id, user.plan_id, sub.cancel_at_period_end = "cancelled", "free", "free", False
            db.commit()
            out["ended"] += 1
            continue
        plan = db.get(Plan, sub.pending_plan_id or sub.plan_id)
        interval = sub.pending_interval or sub.interval
        amount = plan_price(plan, interval, sub.currency)
        desc = f"{plan.name} renewal, {'yearly' if interval == 'year' else 'monthly'}"
        lines = [{"label": desc, "amount": amount}]
        if gateway.charge(user, amount, sub.currency):
            inv = _invoice(db, user, "subscription", desc, amount, sub.currency, "paid", lines)
            sub.interval = interval
            if sub.pending_plan_id and sub.pending_plan_id != sub.plan_id:
                out["downgraded"] += 1
            _start_period(db, user, sub, plan, now)
            _receipt(db, user, inv)
            out["renewed"] += 1
            continue
        _invoice(db, user, "subscription", desc, amount, sub.currency, "failed", lines)
        sub.failed_attempts += 1
        out["failed"] += 1
        if sub.failed_attempts > len(RETRY_DAYS):
            sub.status, sub.plan_id, user.plan_id = "cancelled", "free", "free"
            send_mail(db, user.email, "Your Clue AI plan has ended", "We couldn't take your payment after several tries, so your account moved to Free. Your credits and videos are safe.")
        else:
            sub.status, sub.next_retry_at = "past_due", now + timedelta(days=RETRY_DAYS[sub.failed_attempts - 1])
            send_mail(db, user.email, "Payment failed for your Clue AI plan", f"We couldn't renew your plan. We'll try again on {sub.next_retry_at:%d %b %Y}. You can also pay from the Billing page.")
        db.commit()
    return out


def view(db: Session, user: User) -> dict:
    sub = get_sub(db, user.id)
    plan = db.get(Plan, user.plan_id)
    return {
        "plan_id": user.plan_id, "plan_name": plan.name if plan else user.plan_id, "credits": credits.balance(db, user.id),
        "gateway": gateway.name, "simulated": True,
        "subscription": None if sub is None else {
            "status": sub.status, "interval": sub.interval, "currency": sub.currency, "period_end": sub.period_end.isoformat(),
            "cancel_at_period_end": sub.cancel_at_period_end, "pending_plan_id": sub.pending_plan_id,
            "next_retry_at": sub.next_retry_at.isoformat() if sub.next_retry_at else None},
        "topups": [{"id": k, "credits": v[0], "ngn": v[1], "usd": v[2]} for k, v in TOPUPS.items()],
    }
