from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import CONTACT_EMAIL, CONTACT_PHONE, demo_clock
from ..db import get_db
from ..models import Case, Notification, User, iso
from ..security import current_user
from ..services import classifier, rules

router = APIRouter(prefix="/api", tags=["meta"])


class ClockRequest(BaseModel):
    seconds_per_day: float = Field(gt=0.05, le=86400)
    enabled: bool = True


class ChatRequest(BaseModel):
    message: str


@router.get("/config")
def config() -> dict:
    return {
        "demo_clock": demo_clock.as_dict(),
        "sectors": rules.sectors(),
        "contact": {"email": CONTACT_EMAIL, "phone": CONTACT_PHONE},
        "llm_enabled": classifier.llm_available(),
        "llm_provider": classifier.llm_provider(),
    }


@router.post("/config/clock")
def set_clock(payload: ClockRequest) -> dict:
    """Compressed demo timescale is configurable at runtime, so the walkthrough
    can be sped up or slowed down without a restart."""
    demo_clock.enabled = payload.enabled
    demo_clock.seconds_per_day = payload.seconds_per_day
    return demo_clock.as_dict()


@router.get("/notifications")
def notifications(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    notes = db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id, Notification.read.is_(False))
        .order_by(Notification.id.desc())
        .limit(30)
    ).all()
    case_refs = {
        c.id: c.reference
        for c in db.scalars(select(Case).where(Case.user_id == user.id)).all()
    }
    return {
        "notifications": [
            {
                "id": n.id,
                "case_id": n.case_id,
                "case_reference": case_refs.get(n.case_id),
                "kind": n.kind,
                "title": n.title,
                "body": n.body,
                "severity": n.severity,
                "emailed": n.emailed,
                "created_at": iso(n.created_at),
            }
            for n in notes
        ]
    }


@router.post("/notifications/{notification_id}/read")
def mark_read(
    notification_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    note = db.get(Notification, notification_id)
    if note is not None and note.user_id == user.id:
        note.read = True
        db.commit()
    return {"ok": True}


@router.get("/news")
def news() -> dict:
    """Placeholder article cards shaped like a real news-API response, so
    swapping in a live feed is a fetch change and nothing more."""
    return {
        "status": "ok",
        "source": "placeholder",
        "totalResults": 5,
        "articles": [
            {
                "title": "Consumer Commissions clear record backlog as e-Daakhil filings cross 2 lakh",
                "source": {"id": None, "name": "The Hindu BusinessLine"},
                "description": "Online filing through the e-Daakhil portal has cut the average time to first hearing, with district commissions reporting faster admission decisions under Section 36 of the Consumer Protection Act.",
                "url": "#",
                "publishedAt": "2026-08-05T09:30:00Z",
                "category": "Consumer courts",
            },
            {
                "title": "RBI tightens turnaround norms for failed UPI transactions",
                "source": {"id": None, "name": "Mint"},
                "description": "Banks failing to auto-reverse a failed UPI debit within the prescribed window must pay compensation per day of delay, the central bank reiterated in a circular to all regulated entities.",
                "url": "#",
                "publishedAt": "2026-08-03T06:15:00Z",
                "category": "Banking",
            },
            {
                "title": "What the E-Commerce Rules actually require of a Grievance Officer",
                "source": {"id": None, "name": "Bar and Bench"},
                "description": "Rule 4(5) requires acknowledgement within 48 hours and redressal within one month, an obligation many marketplaces still treat as advisory, lawyers say.",
                "url": "#",
                "publishedAt": "2026-07-29T11:45:00Z",
                "category": "E-commerce",
            },
            {
                "title": "TRAI flags rising billing complaints against broadband providers",
                "source": {"id": None, "name": "Economic Times Telecom"},
                "description": "Complaint centre dockets rose sharply last quarter, with billing disputes and unrequested plan migrations accounting for most escalations to Appellate Authorities.",
                "url": "#",
                "publishedAt": "2026-07-24T14:00:00Z",
                "category": "Telecom",
            },
            {
                "title": "Your two-year clock: limitation under Section 69 explained",
                "source": {"id": None, "name": "LiveLaw"},
                "description": "A complaint filed more than two years after the cause of action is barred unless delay is condoned, a deadline consumers routinely miss while waiting on customer support.",
                "url": "#",
                "publishedAt": "2026-07-18T08:20:00Z",
                "category": "Explainer",
            },
        ],
    }


@router.post("/support/chat")
def support_chat(payload: ChatRequest) -> dict:
    """Small scripted helper on the 'couldn't classify' screen - deliberately a
    dead-end-avoidance tool, not a general assistant."""
    text = payload.message.lower()
    if any(w in text for w in ("lawyer", "advocate", "legal help", "sue")):
        reply = (
            "If your case is already past the escalation stages, we can flag it for a "
            "lawyer from the case page. Lawyer matching itself is rolling out shortly. "
            "In the meantime our team can point you to a consumer advocate."
        )
    elif any(w in text for w in ("refund", "money back", "not received")):
        reply = (
            "Refund and non-delivery disputes usually sit under either the E-Commerce "
            "Rules or the RBI Ombudsman scheme, depending on who holds your money. Tell "
            "us who you paid and we can place it correctly."
        )
    elif any(w in text for w in ("hospital", "school", "electricity", "railway", "builder")):
        reply = (
            f"That sector isn't in Hakk yet - we currently cover "
            f"{classifier.sector_list()}. Our team handles everything else manually, "
            f"and the contact details are just above."
        )
    elif any(w in text for w in ("how long", "time", "deadline", "when")):
        reply = (
            "Each stage has its own statutory window - 30 days for an e-commerce "
            "Grievance Officer, 30 days before the RBI Ombudsman will admit a bank "
            "complaint, and so on. Hakk tracks each one and escalates when it lapses."
        )
    else:
        reply = (
            "Thanks - that's noted. A member of our team will pick this up. If it's "
            "urgent, the email and phone number above reach us directly during "
            "business hours."
        )
    return {"reply": reply, "contact": {"email": CONTACT_EMAIL, "phone": CONTACT_PHONE}}
