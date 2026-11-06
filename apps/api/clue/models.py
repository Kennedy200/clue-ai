"""ORM models (PostgreSQL-compatible: text ULID keys, naive-UTC timestamps)."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from clue.core.db import Base
from clue.core.ids import new_id, utcnow


class _Row:
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class User(_Row, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120), default="")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    plan_id: Mapped[str] = mapped_column(String(40), default="free")
    referral_code: Mapped[str] = mapped_column(String(16), unique=True, default=lambda: new_id()[-8:])
    referred_by: Mapped[str | None] = mapped_column(String(26), nullable=True)
    prefs: Mapped[dict] = mapped_column(JSON, default=dict)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Session(_Row, Base):
    __tablename__ = "sessions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class EmailToken(_Row, Base):
    __tablename__ = "email_tokens"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # verify | reset
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    encrypted: Mapped[bool] = mapped_column(Boolean, default=False)


class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    price_ngn_month: Mapped[int] = mapped_column(Integer, default=0)
    price_usd_month: Mapped[int] = mapped_column(Integer, default=0)  # cents
    monthly_credits: Mapped[int] = mapped_column(Integer, default=0)
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class CreditLedger(_Row, Base):
    """Append-only. balance = SUM(delta). kind: grant | reserve | settle | refund."""
    __tablename__ = "credit_ledger"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    delta: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(200), default="")
    ref_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class Job(_Row, Base):
    __tablename__ = "jobs"
    type: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(12), default="queued", index=True)  # queued|running|done|failed|cancelled
    user_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    stage: Mapped[str] = mapped_column(String(60), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_by: Mapped[str | None] = mapped_column(String(40), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    credit_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)


class DevMail(_Row, Base):
    __tablename__ = "dev_mail"
    to: Mapped[str] = mapped_column(String(255), index=True)
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)


class AuditLog(_Row, Base):
    __tablename__ = "audit_log"
    actor_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class ApiUsage(_Row, Base):
    """Every LLM call: model, tokens, estimated cost, feature, user."""
    __tablename__ = "api_usage"
    user_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(120))
    feature: Mapped[str] = mapped_column(String(40))
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd_micro: Mapped[int] = mapped_column(Integer, default=0)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)


class LlmCache(Base):
    __tablename__ = "llm_cache"
    hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    response: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SupportTicket(_Row, Base):
    __tablename__ = "support_tickets"
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="open")


class Review(_Row, Base):
    """Real user reviews only; shown publicly once approved by an admin."""
    __tablename__ = "reviews"
    user_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    rating: Mapped[int] = mapped_column(Integer)
    body: Mapped[str] = mapped_column(Text)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)


class Project(_Row, Base):
    __tablename__ = "projects"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="Untitled")
    style: Mapped[str] = mapped_column(String(30), default="text_story")
    status: Mapped[str] = mapped_column(String(12), default="draft")  # draft|rendering|done|failed
    scene_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)  # milliseconds
