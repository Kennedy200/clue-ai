"""Public (no login) endpoints for the marketing site."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from clue.core.config import get_settings
from clue.core.db import get_db
from clue.core.mail import send_mail
from clue.core.ratelimit import limit
from clue.models import Plan, Review, SupportTicket

router = APIRouter(tags=["public"])


class Contact(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    message: str = Field(min_length=5, max_length=4000)


@router.post("/contact", dependencies=[Depends(limit("contact", 5, 300))])
def contact(body: Contact, db: Session = Depends(get_db)):
    t = SupportTicket(name=body.name.strip(), email=body.email.lower(), message=body.message.strip())
    db.add(t)
    db.commit()
    send_mail(db, get_settings().admin_email, f"Support: message from {t.name}", f"From: {t.name} <{t.email}>\n\n{t.message}")
    return {"ok": True, "ticket": t.id}


@router.get("/reviews")
def reviews(db: Session = Depends(get_db)):
    rows = db.scalars(select(Review).where(Review.approved.is_(True)).order_by(Review.id.desc()).limit(12)).all()
    return [{"name": r.name, "rating": r.rating, "body": r.body} for r in rows]


@router.get("/plans")
def plans(db: Session = Depends(get_db)):
    rows = db.scalars(select(Plan).order_by(Plan.sort)).all()
    return [
        {"id": p.id, "name": p.name, "price_ngn_month": p.price_ngn_month, "price_usd_month": p.price_usd_month,
         "monthly_credits": p.monthly_credits, "features": p.features}
        for p in rows
    ]
