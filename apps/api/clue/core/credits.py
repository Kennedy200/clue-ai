"""Transactional credit ledger: reserve -> settle/refund. Balance never goes negative."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clue.models import CreditLedger


class InsufficientCredits(Exception):
    pass


def balance(db: Session, user_id: str) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(CreditLedger.delta), 0)).where(CreditLedger.user_id == user_id)) or 0)


def grant(db: Session, user_id: str, amount: int, reason: str, ref_id: str | None = None) -> None:
    db.add(CreditLedger(user_id=user_id, delta=amount, kind="grant", reason=reason, ref_id=ref_id))
    db.commit()


def reserve(db: Session, user_id: str, amount: int, reason: str, ref_id: str) -> None:
    """Hold credits. Idempotent per ref_id. Raises InsufficientCredits rather than going negative."""
    if db.scalar(select(CreditLedger.id).where(CreditLedger.ref_id == ref_id, CreditLedger.kind == "reserve")):
        return
    if balance(db, user_id) < amount:
        raise InsufficientCredits(f"need {amount}")
    db.add(CreditLedger(user_id=user_id, delta=-amount, kind="reserve", reason=reason, ref_id=ref_id))
    db.commit()


def _open_reservation(db: Session, ref_id: str):
    rows = db.scalars(select(CreditLedger).where(CreditLedger.ref_id == ref_id)).all()
    kinds = {r.kind for r in rows}
    if "reserve" in kinds and not kinds & {"settle", "refund"}:
        return -sum(r.delta for r in rows if r.kind == "reserve")
    return None


def refund(db: Session, user_id: str, ref_id: str) -> None:
    """Return a reservation once; no-op if already settled or refunded."""
    amt = _open_reservation(db, ref_id)
    if amt is not None:
        db.add(CreditLedger(user_id=user_id, delta=amt, kind="refund", reason="refund", ref_id=ref_id))
        db.commit()


def settle(db: Session, user_id: str, ref_id: str) -> None:
    """Finalise a reservation (zero-delta marker so it can no longer be refunded)."""
    if _open_reservation(db, ref_id) is not None:
        db.add(CreditLedger(user_id=user_id, delta=0, kind="settle", reason="settled", ref_id=ref_id))
        db.commit()
