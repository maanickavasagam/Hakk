"""Deadline engine.

Runs on a background APScheduler job. Every tick it walks each active case and,
where a paid stage's deadline has lapsed, generates the next draft from the case
history and advances the ladder — writing each step to the per-case activity log
so the automation is provable on screen rather than merely asserted.
"""

from __future__ import annotations

import datetime as dt
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import SCHEDULER_INTERVAL_SECONDS
from ..db import SessionLocal
from ..models import Case, Document, Draft, Notification, Stage, utcnow
from . import drafter
from .timeline import log_activity, notify, start_stage_clock

log = logging.getLogger("hakk.scheduler")

ACTIVE_STATUSES = {"active"}


def _aware(value: dt.datetime | None) -> dt.datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)


def _documents_payload(case: Case, db: Session) -> list[dict]:
    docs = db.scalars(select(Document).where(Document.case_id == case.id)).all()
    payload = []
    for doc in docs:
        source = doc.confirmed if doc.is_confirmed and doc.confirmed else doc.extracted
        payload.append(
            {"filename": doc.filename, "fields": (source or {}).get("fields", [])}
        )
    return payload


def _history(case: Case, upto_index: int) -> list[dict]:
    items = []
    for stage in case.stages:
        if stage.index >= upto_index:
            continue

        if stage.outcome == "rejected":
            outcome = (
                f"the complaint was rejected outright, which under {stage.regulation} "
                f"opens the next rung immediately rather than after the "
                f"{stage.deadline_days:g}-day window"
            )
        elif stage.outcome == "unsatisfactory":
            outcome = (
                f"a response was received but did not redress the grievance, which under "
                f"{stage.regulation} opens the next rung without waiting out the "
                f"{stage.deadline_days:g}-day window"
            )
        elif stage.status == "lapsed":
            outcome = (
                f"the {stage.deadline_days:g}-day window under {stage.regulation} "
                f"expired without a substantive response"
            )
        elif stage.status == "completed":
            outcome = "the complaint was marked resolved at that stage"
        else:
            outcome = f"the stage is recorded as {stage.status}"

        if stage.outcome_note:
            outcome += f'. The response given was: "{stage.outcome_note}"'
        if stage.ack_breached:
            outcome += (
                f". The {stage.ack_hours:g}-hour acknowledgement required by "
                f"{stage.regulation} was also not given"
            )

        items.append(
            {
                "index": stage.index,
                "name": stage.name,
                "authority": stage.authority,
                "outcome": outcome,
            }
        )
    return items


def generate_stage_draft(db: Session, case: Case, stage: Stage, auto: bool) -> Draft:
    ordered = sorted(case.stages, key=lambda s: s.index)
    next_stage = next((s for s in ordered if s.index == stage.index + 1), None)

    ctx = {
        "stage": {
            "index": stage.index,
            "name": stage.name,
            "authority": stage.authority,
            "regulation": stage.regulation,
            "regulation_note": stage.regulation_note,
            "deadline_days": stage.deadline_days,
            "ack_hours": stage.ack_hours,
        },
        "answers": case.answers or {},
        "documents": _documents_payload(case, db),
        "company": case.company,
        "user_name": case.user.full_name,
        "user_email": case.user.email,
        "user_phone": case.user.phone,
        "history": _history(case, stage.index),
        "next_stage_name": next_stage.authority if next_stage else None,
    }

    result = drafter.generate(ctx)

    for old in case.drafts:
        if old.stage_id == stage.id and old.status == "pending_review":
            old.status = "superseded"

    draft = Draft(
        case_id=case.id,
        stage_id=stage.id,
        subject=result["subject"],
        body=result["body"],
        legal_basis=result["legal_basis"],
        status="pending_review",
        generated_by=result["generated_by"],
        auto_generated=auto,
    )
    db.add(draft)
    db.flush()
    return draft


def _missing_documents(case: Case, stage: Stage, db: Session) -> bool:
    count = db.scalar(
        select(Document.id).where(Document.case_id == case.id).limit(1)
    )
    return count is None and bool(stage.required_documents)


def _already_notified(db: Session, case_id: int, kind: str) -> bool:
    return (
        db.scalar(
            select(Notification.id)
            .where(Notification.case_id == case_id, Notification.kind == kind)
            .limit(1)
        )
        is not None
    )


def advance_from(db: Session, case: Case, current: Stage) -> None:
    """Close out `current` and move the ladder on.

    Called from two places that reach the same point by different routes: the
    deadline engine when a window runs out, and the user recording that the
    company rejected the complaint or answered inadequately. Both mean this rung
    is finished, so the downstream handling — handoff when the ladder ends,
    document prompts, payment gating, auto-drafting — is identical and lives
    here once. The caller owns setting `current.status` and `current.outcome`.
    """
    ordered = sorted(case.stages, key=lambda s: s.index)
    next_stage = next((s for s in ordered if s.index == current.index + 1), None)

    if next_stage is None:
        case.status = "lawyer_handoff"
        case.lawyer_handoff = True
        case.handoff_reason = (
            "All configured escalation stages have been exhausted without redressal."
        )
        log_activity(
            db,
            case,
            "Flagged for lawyer handoff",
            "The configured ladder is exhausted. This case now needs a lawyer.",
            icon="scale",
        )
        notify(
            db,
            case,
            f"handoff:{case.id}",
            "Case flagged for a lawyer",
            "Every stage in the ladder has been exhausted. We are matching you "
            "with a consumer lawyer.",
            severity="urgent",
        )
        return

    if _missing_documents(case, next_stage, db):
        next_stage.status = "action_needed" if next_stage.paid else "awaiting_payment"
        notify(
            db,
            case,
            f"docs:{next_stage.id}",
            f"Action needed — documents for Stage {next_stage.index + 1}",
            "Upload the documents listed for the next stage so the escalation "
            "can cite them.",
            severity="warn",
        )
        log_activity(
            db,
            case,
            "Action needed: supporting documents",
            f"Stage {next_stage.index + 1} ({next_stage.name}) needs: "
            + ", ".join(next_stage.required_documents[:3]),
            icon="upload",
        )

    if next_stage.paid:
        case.current_stage_index = next_stage.index
        draft = generate_stage_draft(db, case, next_stage, auto=True)
        start_stage_clock(db, case, next_stage)
        log_activity(
            db,
            case,
            f"Auto-escalated to Stage {next_stage.index + 1}",
            f"Draft #{draft.id} for the {next_stage.authority} generated "
            f"automatically from the case history, citing {next_stage.regulation}.",
            actor="agent",
            icon="zap",
        )
        notify(
            db,
            case,
            f"advanced:{next_stage.id}",
            f"Escalated to Stage {next_stage.index + 1}",
            f"A draft addressed to the {next_stage.authority} is ready for your review.",
            severity="info",
        )
    else:
        next_stage.status = "awaiting_payment"
        log_activity(
            db,
            case,
            f"Stage {next_stage.index + 1} awaiting unlock",
            f"{next_stage.name} is ready to file but has not been unlocked. "
            f"Escalation is paused until it is.",
            icon="lock",
        )
        notify(
            db,
            case,
            f"unlock:{next_stage.id}",
            f"Unlock Stage {next_stage.index + 1} to continue",
            f"{next_stage.name} — ₹{next_stage.price_paise / 100:.0f} to unlock, "
            f"or take the full bundle.",
            severity="warn",
        )


def _process_case(db: Session, case: Case) -> bool:
    """Returns True if anything changed."""
    now = utcnow()
    ordered = sorted(case.stages, key=lambda s: s.index)
    current = next((s for s in ordered if s.index == case.current_stage_index), None)
    if current is None:
        return False

    changed = False

    # --- approaching-deadline reminder -----------------------------------
    deadline = _aware(current.deadline_at)
    if current.status == "awaiting_response" and deadline:
        started = _aware(current.started_at) or deadline
        total = (deadline - started).total_seconds() or 1
        remaining = (deadline - now).total_seconds()
        kind = f"approaching:{current.id}"
        if 0 < remaining <= total * 0.35 and not _already_notified(db, case.id, kind):
            notify(
                db,
                case,
                kind,
                f"Deadline approaching — Stage {current.index + 1}",
                f"The {current.deadline_days:g}-day window under {current.regulation} "
                f"is almost up for {current.name}. Hakk will escalate automatically "
                f"if there is no response.",
                severity="warn",
            )
            log_activity(
                db,
                case,
                f"Reminder: Stage {current.index + 1} deadline approaching",
                f"{current.name} — statutory window closing.",
                icon="bell",
            )
            changed = True

    # --- acknowledgement-window breach -------------------------------------
    # Recorded, not acted on. Where a regulation imposes a short acknowledgement
    # duty (48h under E-Commerce Rule 4(5), 72h under TCCR Reg 13(1)(b)) missing
    # it is a breach in its own right — but it does not shorten the redressal
    # window, so escalating early on this alone would be legally wrong. What it
    # does is go into the record and get pleaded at the next rung.
    ack_deadline = _aware(current.ack_deadline_at)
    if (
        current.status == "awaiting_response"
        and ack_deadline
        and not current.acknowledged_at
        and not current.ack_breached
        and now >= ack_deadline
    ):
        current.ack_breached = True
        changed = True
        log_activity(
            db,
            case,
            f"Stage {current.index + 1} acknowledgement window breached",
            f"{current.ack_hours:g}-hour acknowledgement required by {current.regulation} "
            f"passed with nothing received. Recorded as a breach and cited in the next "
            f"escalation. The {current.deadline_days:g}-day redressal window keeps running.",
            icon="alert",
        )
        notify(
            db,
            case,
            f"ack:{current.id}",
            f"No acknowledgement — Stage {current.index + 1}",
            f"{case.company or 'The company'} did not acknowledge within the "
            f"{current.ack_hours:g} hours its own regulation requires. That breach is now "
            f"on record; the {current.deadline_days:g}-day window continues.",
            severity="warn",
        )

    # --- lapse and escalate ----------------------------------------------
    if current.status == "awaiting_response" and deadline and now >= deadline:
        current.status = "lapsed"
        current.outcome = "timeout"
        changed = True
        log_activity(
            db,
            case,
            f"Stage {current.index + 1} deadline lapsed",
            f"{current.deadline_days:g}-day window under {current.regulation} expired "
            f"with no substantive response from {case.company or 'the company'}.",
            icon="alert",
        )
        notify(
            db,
            case,
            f"lapsed:{current.id}",
            f"Stage {current.index + 1} deadline lapsed",
            f"{current.name}: the statutory window closed without redressal.",
            severity="urgent",
        )

        advance_from(db, case, current)

    return changed


def tick() -> None:
    db: Session = SessionLocal()
    try:
        cases = db.scalars(select(Case).where(Case.status.in_(ACTIVE_STATUSES))).all()
        changed = False
        for case in cases:
            try:
                if _process_case(db, case):
                    changed = True
            except Exception:
                log.exception("scheduler failed on case %s", case.id)
                db.rollback()
        if changed:
            db.commit()
    finally:
        db.close()


_scheduler: BackgroundScheduler | None = None


def start() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        tick,
        "interval",
        seconds=SCHEDULER_INTERVAL_SECONDS,
        id="hakk-deadline-engine",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    log.info("deadline engine started (every %ss)", SCHEDULER_INTERVAL_SECONDS)
    return _scheduler


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
