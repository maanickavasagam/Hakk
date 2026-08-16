from __future__ import annotations

import secrets
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import CONTACT_EMAIL, CONTACT_PHONE
from ..db import get_db
from ..models import Case, Draft, Notification, User, iso, utcnow
from ..security import current_user
from ..services import classifier, intake_extractor, rules
from ..services.intake_fields import (
    DESIRED_RESOLUTION_OPTIONS,
    PRIOR_CONTACT_OPTIONS,
    WHAT_HAPPENED_OPTIONS,
)
from ..services.scheduler import advance_from, generate_stage_draft
from ..services.timeline import build_timeline, log_activity, notify, stage_payload, start_stage_clock

router = APIRouter(prefix="/api/cases", tags=["cases"])


# --------------------------------------------------------------------------
# Guided intake question flow — a fixed, ordered set of questions, not a chat.
# --------------------------------------------------------------------------
INTAKE_QUESTIONS = [
    {
        "id": "what_happened",
        "step": 1,
        "title": "What went wrong?",
        "help": "Pick the closest match. You can add detail in the next box.",
        "type": "select",
        "required": True,
        "options": WHAT_HAPPENED_OPTIONS,
    },
    {
        "id": "what_happened_detail",
        "step": 1,
        "title": "Describe it in your own words",
        "help": "Two or three sentences is plenty. Include amounts and reference numbers if you have them.",
        "type": "textarea",
        "required": True,
        "placeholder": "On 14 March I ordered a pair of headphones for ₹2,500. They were never delivered but the tracking was marked complete...",
    },
    {
        "id": "company",
        "step": 2,
        "title": "Which company or service?",
        "help": "The brand you paid or contracted with.",
        "type": "text",
        "required": True,
        "placeholder": "e.g. Flipkart, HDFC Bank, Airtel",
    },
    {
        "id": "reference_number",
        "step": 2,
        "title": "Order, transaction or account reference",
        "help": "Optional — if you have it, your complaint will cite it.",
        "type": "text",
        "required": False,
        "placeholder": "e.g. OD4521987, UTR 402318774512",
    },
    {
        "id": "amount_involved",
        "step": 2,
        "title": "Amount involved (₹)",
        "help": "Optional. The value in dispute.",
        "type": "number",
        "required": False,
        "placeholder": "2500",
    },
    {
        "id": "when_it_happened",
        "step": 3,
        "title": "When did this happen?",
        "help": "The date of the transaction or the incident. Limitation periods run from here.",
        "type": "date",
        "required": True,
    },
    {
        "id": "desired_resolution",
        "step": 4,
        "title": "What outcome do you want?",
        "help": "This becomes the relief clause in your complaint.",
        "type": "select",
        "required": True,
        "options": DESIRED_RESOLUTION_OPTIONS,
    },
    {
        "id": "prior_contact",
        "step": 5,
        "title": "Have you already contacted them?",
        "help": "Forums ask for this. Be accurate — it shapes which rung we start on.",
        "type": "select",
        "required": True,
        "options": PRIOR_CONTACT_OPTIONS,
    },
    {
        "id": "prior_contact_detail",
        "step": 5,
        "title": "What did they say?",
        "help": "Optional. Include ticket or docket numbers if you were given any.",
        "type": "textarea",
        "required": False,
        "placeholder": "Raised ticket #4471 on 20 March. Was told it would be resolved in 48 hours. No response since.",
    },
]

STEP_TITLES = {
    1: "What happened",
    2: "Who and how much",
    3: "When",
    4: "What you want",
    5: "Prior contact",
}


class CreateCaseRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class AnswersRequest(BaseModel):
    answers: dict


class DraftEditRequest(BaseModel):
    subject: str | None = None
    body: str | None = None


class AcknowledgementRequest(BaseModel):
    reference: str | None = Field(default=None, max_length=120)


class ResponseRequest(BaseModel):
    """What the company actually came back with.

    'rejected' and 'unsatisfactory' both open the next rung immediately — every
    ladder Hakk carries says so in its own text (RB-IOS 2026 cl. 10(1)(f),
    Insurance Ombudsman Rules r. 14(3)(a)(i) and (iii), TCCR 2012 reg. 9), and
    waiting out a window whose purpose has already been served just costs the
    user weeks.
    """

    outcome: Literal["rejected", "unsatisfactory", "resolved"]
    note: str = Field(default="", max_length=2000)


class IntakeExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=6000)


def _ref() -> str:
    return "HAKK-" + secrets.token_hex(3).upper()


def _get_case(db: Session, user: User, case_id: int) -> Case:
    case = db.get(Case, case_id)
    if case is None or case.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    return case


def _draft_payload(draft: Draft) -> dict:
    return {
        "id": draft.id,
        "stage_id": draft.stage_id,
        "subject": draft.subject,
        "body": draft.body,
        "legal_basis": draft.legal_basis,
        "status": draft.status,
        "generated_by": draft.generated_by,
        "auto_generated": draft.auto_generated,
        "created_at": iso(draft.created_at),
        "approved_at": iso(draft.approved_at),
    }


def _case_payload(case: Case, db: Session, full: bool = False) -> dict:
    stages = sorted(case.stages, key=lambda s: s.index)
    data = {
        "id": case.id,
        "reference": case.reference,
        "title": case.title,
        "company": case.company,
        "status": case.status,
        "sector": case.sector,
        "sector_label": case.sector_label,
        "confidence": case.confidence,
        "classification_reasoning": case.classification_reasoning,
        "classified_by": case.classified_by,
        "current_stage_index": case.current_stage_index,
        "lawyer_handoff": case.lawyer_handoff,
        "handoff_reason": case.handoff_reason,
        "stage_count": len(stages),
        "created_at": iso(case.created_at),
        "updated_at": iso(case.updated_at),
    }
    if not full:
        current = next((s for s in stages if s.index == case.current_stage_index), None)
        data["current_stage"] = stage_payload(current) if current else None
        return data

    rule = rules.get(case.sector) if case.sector else None
    data.update(
        {
            "answers": case.answers or {},
            "stages": [stage_payload(s) for s in stages],
            "drafts": [_draft_payload(d) for d in sorted(case.drafts, key=lambda d: d.id)],
            "bundle_price_paise": rule["bundle_price_paise"] if rule else None,
            "primary_statute": rule["primary_statute"] if rule else None,
            "documents": [
                {
                    "id": d.id,
                    "filename": d.filename,
                    "content_type": d.content_type,
                    "size_bytes": d.size_bytes,
                    "is_confirmed": d.is_confirmed,
                    "extraction_method": d.extraction_method,
                    "extraction_note": d.extraction_note,
                    "fields": (
                        (d.confirmed or {}).get("fields")
                        if d.is_confirmed
                        else (d.extracted or {}).get("fields")
                    )
                    or [],
                    "created_at": iso(d.created_at),
                }
                for d in sorted(case.documents, key=lambda d: d.id)
            ],
            "activity": [
                {
                    "id": a.id,
                    "actor": a.actor,
                    "event": a.event,
                    "detail": a.detail,
                    "icon": a.icon,
                    "created_at": iso(a.created_at),
                }
                for a in sorted(case.activities, key=lambda a: a.id, reverse=True)
            ],
        }
    )
    return data


@router.get("/intake/questions")
def intake_questions() -> dict:
    steps = []
    for step in sorted(STEP_TITLES):
        steps.append(
            {
                "step": step,
                "title": STEP_TITLES[step],
                "questions": [q for q in INTAKE_QUESTIONS if q["step"] == step],
            }
        )
    return {"steps": steps, "total_steps": len(steps)}


@router.post("/{case_id}/intake/extract")
def extract_intake(
    case_id: int,
    payload: IntakeExtractRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Turn free text into a candidate set of guided-form answers for the user
    to review and correct. Nothing is saved here — the frontend shows the
    result back for confirmation, then calls PATCH .../answers exactly as the
    guided form does, so everything downstream of intake is unchanged.

    Deliberately not routed into the same-shaped classify() call: extraction
    only produces intake *facts*, not a sector judgment. Whether the resulting
    complaint is one Hakk can handle is decided the normal way, by the actual
    classify step, once the user has confirmed these fields — an out-of-scope
    complaint (a landlord, an employer) is 'understood' here and only turns out
    to be unclassifiable at that later, existing checkpoint.
    """
    case = _get_case(db, user, case_id)

    if not intake_extractor.extraction_available():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Free-text extraction needs an LLM configured. Use the guided questions instead.",
        )

    result = intake_extractor.extract(payload.text)
    if result is None:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Couldn't read that just now. Try again, or use the guided questions instead.",
        )

    log_activity(
        db,
        case,
        "Free-text intake extracted",
        f"{len(result['answers'])} field(s) suggested from the user's own words. "
        f"Awaiting confirmation."
        + ("" if result["understood"] else " The text didn't read as a clear complaint."),
        actor="user",
        icon="edit",
    )
    db.commit()

    return {
        "answers": result["answers"],
        "understood": result["understood"],
        "clarifying_note": result["clarifying_note"],
    }


@router.get("")
def list_cases(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    cases = db.scalars(
        select(Case).where(Case.user_id == user.id).order_by(Case.id.desc())
    ).all()
    return {"cases": [_case_payload(c, db) for c in cases]}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CreateCaseRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    case = Case(
        user_id=user.id,
        reference=_ref(),
        title=payload.title or "New complaint",
        status="intake",
        answers={},
    )
    db.add(case)
    db.flush()
    log_activity(db, case, "Case opened", "Guided intake started.", actor="user", icon="plus")
    db.commit()
    return _case_payload(case, db, full=True)


@router.get("/{case_id}")
def get_case(
    case_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    return _case_payload(_get_case(db, user, case_id), db, full=True)


@router.patch("/{case_id}/answers")
def save_answers(
    case_id: int,
    payload: AnswersRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Structured answers are persisted as they are collected, step by step."""
    case = _get_case(db, user, case_id)
    merged = dict(case.answers or {})
    merged.update({k: v for k, v in payload.answers.items() if v not in (None, "")})
    case.answers = merged

    if merged.get("company"):
        case.company = str(merged["company"])[:160]
    if merged.get("what_happened"):
        subject = merged["what_happened"]
        case.title = f"{subject} — {case.company}" if case.company else str(subject)
    case.updated_at = utcnow()

    answered = sum(1 for q in INTAKE_QUESTIONS if merged.get(q["id"]))
    log_activity(
        db,
        case,
        "Intake answers saved",
        f"{answered} of {len(INTAKE_QUESTIONS)} questions answered.",
        actor="user",
        icon="edit",
    )
    db.commit()
    return _case_payload(case, db, full=True)


@router.post("/{case_id}/classify")
def classify_case(
    case_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    case = _get_case(db, user, case_id)

    missing = [
        q["title"] for q in INTAKE_QUESTIONS if q["required"] and not (case.answers or {}).get(q["id"])
    ]
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Answer the required questions first: {', '.join(missing)}",
        )

    documents = [
        {
            "filename": d.filename,
            "fields": ((d.confirmed if d.is_confirmed else d.extracted) or {}).get("fields", []),
        }
        for d in case.documents
    ]

    result = classifier.classify(case.answers or {}, documents)
    case.confidence = result["confidence"]
    case.classification_reasoning = result["reasoning"]
    case.classified_by = result["classified_by"]

    if not result["confident"]:
        case.status = "unclassified"
        case.sector = None
        case.sector_label = None
        log_activity(
            db,
            case,
            "Could not classify confidently",
            f"Confidence {result['confidence']:.0%} is below the {result['threshold']:.0%} "
            f"threshold. Routed to human support.",
            icon="help",
        )
        db.commit()
        return {
            "classified": False,
            "confidence": result["confidence"],
            "threshold": result["threshold"],
            "reasoning": result["reasoning"],
            "contact": {"email": CONTACT_EMAIL, "phone": CONTACT_PHONE},
            "case": _case_payload(case, db, full=True),
        }

    case.sector = result["sector"]
    case.sector_label = result["sector_label"]
    case.status = "active"
    case.current_stage_index = 0

    log_activity(
        db,
        case,
        f"Classified as {result['sector_label']}",
        f"{result['confidence']:.0%} confidence ({result['classified_by']}). "
        f"{result['reasoning']}",
        icon="target",
    )

    stages = build_timeline(db, case, result["sector"])
    first = stages[0]
    draft = generate_stage_draft(db, case, first, auto=False)
    start_stage_clock(db, case, first)
    log_activity(
        db,
        case,
        "Stage 1 draft generated",
        f"Draft #{draft.id} addressed to the {first.authority}, citing {first.regulation}. "
        f"Awaiting your review.",
        actor="agent",
        icon="file",
    )
    db.commit()

    return {
        "classified": True,
        "confidence": result["confidence"],
        "reasoning": result["reasoning"],
        "key_facts": result["key_facts"],
        "case": _case_payload(case, db, full=True),
    }


@router.patch("/{case_id}/drafts/{draft_id}")
def edit_draft(
    case_id: int,
    draft_id: int,
    payload: DraftEditRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    case = _get_case(db, user, case_id)
    draft = db.get(Draft, draft_id)
    if draft is None or draft.case_id != case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Draft not found")
    if payload.subject is not None:
        draft.subject = payload.subject[:290]
    if payload.body is not None:
        draft.body = payload.body
    log_activity(db, case, "Draft edited", f"Draft #{draft.id} revised.", actor="user", icon="edit")
    db.commit()
    return _draft_payload(draft)


@router.post("/{case_id}/drafts/{draft_id}/approve")
def approve_draft(
    case_id: int,
    draft_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Approve and 'send'. Nothing leaves Hakk without passing through here."""
    case = _get_case(db, user, case_id)
    draft = db.get(Draft, draft_id)
    if draft is None or draft.case_id != case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Draft not found")

    draft.status = "approved"
    draft.approved_at = utcnow()

    stage = next((s for s in case.stages if s.id == draft.stage_id), None)
    if stage is not None:
        log_activity(
            db,
            case,
            f"Stage {stage.index + 1} complaint approved and filed",
            f"Sent to the {stage.authority}. The {stage.deadline_days:g}-day window under "
            f"{stage.regulation} is now running.",
            actor="user",
            icon="send",
        )
    db.commit()
    return {"ok": True, "draft": _draft_payload(draft), "case": _case_payload(case, db, full=True)}


@router.post("/{case_id}/stages/{stage_id}/acknowledge")
def record_acknowledgement(
    case_id: int,
    stage_id: int,
    payload: AcknowledgementRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Record that the company acknowledged the complaint, which stops the
    acknowledgement clock. The redressal window keeps running — acknowledging is
    not redressing."""
    case = _get_case(db, user, case_id)
    stage = next((s for s in case.stages if s.id == stage_id), None)
    if stage is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stage not found")

    stage.acknowledged_at = utcnow()
    detail = f"{case.company or 'The company'} acknowledged Stage {stage.index + 1}"
    if payload.reference:
        detail += f" with reference {payload.reference}"
    if stage.ack_hours:
        within = "within" if not stage.ack_breached else "after"
        detail += (
            f" — {within} the {stage.ack_hours:g}-hour window required by {stage.regulation}"
        )
    log_activity(db, case, "Acknowledgement recorded", detail + ".", actor="user", icon="check")
    db.commit()
    return _case_payload(case, db, full=True)


@router.post("/{case_id}/stages/{stage_id}/response")
def record_response(
    case_id: int,
    stage_id: int,
    payload: ResponseRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Record what the company actually said, and act on it now.

    A rejection or an inadequate reply is not a reason to keep waiting: the
    regulation behind each ladder treats it as the trigger for the next rung in
    its own right. So this escalates immediately rather than running the clock
    down — which is the whole point of tracking the response at all.
    """
    case = _get_case(db, user, case_id)
    stage = next((s for s in case.stages if s.id == stage_id), None)
    if stage is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stage not found")
    if stage.index != case.current_stage_index:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Only the stage currently in progress can be updated"
        )
    if stage.status not in {"awaiting_response", "action_needed", "paid"}:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Stage {stage.index + 1} is not awaiting a response"
        )

    stage.outcome = payload.outcome
    stage.outcome_note = payload.note.strip()

    if payload.outcome == "resolved":
        stage.status = "completed"
        stage.completed_at = utcnow()
        case.status = "resolved"
        log_activity(
            db,
            case,
            f"Stage {stage.index + 1} resolved",
            f"{case.company or 'The company'} resolved the grievance at "
            f"{stage.name}. The case is closed; no further escalation is needed.",
            actor="user",
            icon="check",
        )
        notify(
            db,
            case,
            f"resolved:{case.id}",
            "Complaint resolved",
            f"{stage.name} settled the matter. Nothing further is scheduled.",
            severity="info",
        )
        db.commit()
        return _case_payload(case, db, full=True)

    # Rejected or inadequate — the window has served its purpose, go now.
    stage.status = "lapsed"
    stage.completed_at = utcnow()
    label = (
        "rejected the complaint"
        if payload.outcome == "rejected"
        else "responded without redressing the grievance"
    )
    log_activity(
        db,
        case,
        f"Stage {stage.index + 1} closed early — {payload.outcome}",
        f"{case.company or 'The company'} {label}. Under {stage.regulation} that opens "
        f"the next rung immediately, so Hakk is escalating now rather than waiting out "
        f"the remaining {stage.deadline_days:g}-day window."
        + (f' Recorded response: "{stage.outcome_note}"' if stage.outcome_note else ""),
        actor="user",
        icon="alert",
    )
    notify(
        db,
        case,
        f"early-escalation:{stage.id}",
        f"Escalating now — Stage {stage.index + 1} {payload.outcome}",
        f"No need to wait out the {stage.deadline_days:g}-day window. Moving to the next stage.",
        severity="warn",
    )

    advance_from(db, case, stage)
    db.commit()
    return _case_payload(case, db, full=True)


@router.post("/{case_id}/mark-unresponsive")
def mark_unresponsive(
    case_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    """User-triggered lawyer handoff: the company is still not responding."""
    case = _get_case(db, user, case_id)
    case.lawyer_handoff = True
    case.status = "lawyer_handoff"
    case.handoff_reason = (
        f"{case.company or 'The company'} was marked as still non-responsive by the user "
        f"at stage {case.current_stage_index + 1}."
    )
    log_activity(
        db,
        case,
        "Flagged for lawyer handoff",
        case.handoff_reason,
        actor="user",
        icon="scale",
    )
    notify(
        db,
        case,
        f"handoff-user:{case.id}",
        "Case flagged for a lawyer",
        "We're matching you with a consumer lawyer. Lawyer matching arrives in the next release.",
        severity="urgent",
    )
    db.commit()
    return _case_payload(case, db, full=True)


@router.get("/{case_id}/activity")
def case_activity(
    case_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    case = _get_case(db, user, case_id)
    return {
        "activity": [
            {
                "id": a.id,
                "actor": a.actor,
                "event": a.event,
                "detail": a.detail,
                "icon": a.icon,
                "created_at": iso(a.created_at),
            }
            for a in sorted(case.activities, key=lambda a: a.id, reverse=True)
        ],
        "stages": [stage_payload(s) for s in sorted(case.stages, key=lambda s: s.index)],
        "status": case.status,
        "current_stage_index": case.current_stage_index,
        "lawyer_handoff": case.lawyer_handoff,
        "drafts": [_draft_payload(d) for d in sorted(case.drafts, key=lambda d: d.id)],
    }


@router.get("/{case_id}/notifications")
def case_notifications(
    case_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    case = _get_case(db, user, case_id)
    notes = db.scalars(
        select(Notification)
        .where(Notification.case_id == case.id)
        .order_by(Notification.id.desc())
    ).all()
    return {
        "notifications": [
            {
                "id": n.id,
                "kind": n.kind,
                "title": n.title,
                "body": n.body,
                "severity": n.severity,
                "read": n.read,
                "emailed": n.emailed,
                "created_at": iso(n.created_at),
            }
            for n in notes
        ]
    }
