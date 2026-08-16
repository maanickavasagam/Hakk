from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(value: dt.datetime | None) -> str | None:
    """Serialise as explicit UTC.

    SQLite drops the tzinfo on round-trip, so a bare .isoformat() yields a naive
    string that browsers parse as *local* time — which silently shifts every
    deadline by the client's UTC offset. Always stamp the offset.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.isoformat()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    full_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cases: Mapped[list["Case"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class OtpCode(Base):
    __tablename__ = "otp_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(6))
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    # Six digits is only 10^6 guesses; without a cap the real-OTP path would be
    # trivially brute-forceable. Burned after MAX_OTP_ATTEMPTS wrong tries.
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    reference: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    company: Mapped[str | None] = mapped_column(String(160), nullable=True)

    # intake -> classifying -> unclassified | active -> lawyer_handoff | resolved
    status: Mapped[str] = mapped_column(String(32), default="intake", index=True)

    sector: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sector_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    classification_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    classified_by: Mapped[str | None] = mapped_column(String(32), nullable=True)

    answers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    current_stage_index: Mapped[int] = mapped_column(Integer, default=0)

    lawyer_handoff: Mapped[bool] = mapped_column(Boolean, default=False)
    handoff_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship(back_populates="cases")
    stages: Mapped[list["Stage"]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="Stage.index"
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    drafts: Mapped[list["Draft"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="Activity.id.desc()"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class Stage(Base):
    __tablename__ = "stages"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    index: Mapped[int] = mapped_column(Integer)

    key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(160))
    authority: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text, default="")

    # Real statutory windows — always displayed as-is, never compressed.
    deadline_days: Mapped[float] = mapped_column(Float)
    ack_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    regulation: Mapped[str] = mapped_column(String(240))
    regulation_note: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    required_documents: Mapped[list[str]] = mapped_column(JSON, default=list)

    price_paise: Mapped[int] = mapped_column(Integer, default=4900)
    # locked | awaiting_payment | paid | awaiting_response | lapsed | completed
    status: Mapped[str] = mapped_column(String(32), default="locked")
    paid: Mapped[bool] = mapped_column(Boolean, default=False)

    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Acknowledgement is a separate, shorter obligation from redressal wherever a
    # regulation imposes one (48h under E-Commerce Rule 4(5), 72h under TCCR
    # Reg 13(1)(b)). Breaching it does not shorten the redressal window — it is
    # recorded as a documented breach and pleaded at the next rung.
    ack_deadline_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ack_breached: Mapped[bool] = mapped_column(Boolean, default=False)

    # How the stage actually ended: "" while it runs, else timeout | rejected |
    # unsatisfactory | resolved. `outcome_note` carries the company's own words,
    # which the next draft quotes back at them.
    outcome: Mapped[str] = mapped_column(String(24), default="")
    outcome_note: Mapped[str] = mapped_column(Text, default="")

    case: Mapped[Case] = relationship(back_populates="stages")
    drafts: Mapped[list["Draft"]] = relationship(back_populates="stage")


class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    stage_id: Mapped[int | None] = mapped_column(ForeignKey("stages.id"), nullable=True)

    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    legal_basis: Mapped[str] = mapped_column(String(300), default="")
    # pending_review | approved | sent | superseded
    status: Mapped[str] = mapped_column(String(24), default="pending_review")
    generated_by: Mapped[str] = mapped_column(String(32), default="template")
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    case: Mapped[Case] = relationship(back_populates="drafts")
    stage: Mapped[Stage | None] = relationship(back_populates="drafts")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)

    extracted: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    confirmed: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    extraction_method: Mapped[str] = mapped_column(String(48), default="none")
    extraction_note: Mapped[str] = mapped_column(Text, default="")
    raw_text: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    case: Mapped[Case] = relationship(back_populates="documents")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    stage_id: Mapped[int | None] = mapped_column(ForeignKey("stages.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(16), default="single")  # single | bundle
    amount_paise: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="paid")
    mock_txn_id: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Activity(Base):
    """Per-case audit log. Every automated action writes here so the automation
    is visible on screen rather than merely claimed."""

    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    actor: Mapped[str] = mapped_column(String(16), default="system")  # system | user | agent
    event: Mapped[str] = mapped_column(String(80))
    detail: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(32), default="activity")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    case: Mapped[Case] = relationship(back_populates="activities")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(16), default="info")  # info | warn | urgent
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    # Whether an email alert was successfully dispatched for this row. False
    # covers both "not attempted" (SMTP unconfigured) and "attempted and
    # failed" — the in-app toast/banner is always the notification of record
    # either way, so the distinction isn't surfaced to the user.
    emailed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    case: Mapped[Case] = relationship(back_populates="notifications")
