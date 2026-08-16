"""Timeline construction and stage progression.

The whole ladder is materialised the moment a case is classified, so the user can
see every stage, its statutory deadline and the documents it will need — before
paying for any of it, and before any of it becomes urgent.
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy.orm import Session

from ..config import demo_clock
from ..models import Activity, Case, Notification, Stage, iso, utcnow
from . import mailer, rules

log = logging.getLogger("hakk.timeline")


def log_activity(
    db: Session,
    case: Case,
    event: str,
    detail: str = "",
    actor: str = "system",
    icon: str = "activity",
) -> Activity:
    entry = Activity(case_id=case.id, actor=actor, event=event, detail=detail, icon=icon)
    db.add(entry)
    return entry


def notify(
    db: Session,
    case: Case,
    kind: str,
    title: str,
    body: str = "",
    severity: str = "info",
) -> Notification:
    """Every case notification passes through here — the scheduler's deadline
    reminders, lapses and auto-escalations, and the manual response/handoff
    endpoints in cases.py alike. That makes this the one place email dispatch
    needs wiring in, rather than a call at every one of those sites.

    Delivery is genuinely best-effort: a failed or skipped send never raises
    and never blocks the Notification row (and the toast/banner it drives)
    from being created, which is the notification of record either way.
    """
    note = Notification(
        case_id=case.id,
        user_id=case.user_id,
        kind=kind,
        title=title,
        body=body,
        severity=severity,
    )
    db.add(note)

    if mailer.is_configured():
        try:
            delivered, _ = mailer.send_alert(
                case.user.email,
                title=title,
                body=body,
                severity=severity,
                case_id=case.id,
                case_reference=case.reference,
            )
            note.emailed = delivered
        except Exception:
            # notify() runs inside both request handlers and the scheduler
            # tick — a mail-stack exception must never take either down.
            log.exception("alert email dispatch crashed for case %s (%s)", case.id, kind)

    return note


def build_timeline(db: Session, case: Case, sector: str) -> list[Stage]:
    """Materialise every stage of the matched sector's ladder up front."""
    rule = rules.get(sector)
    if rule is None:
        raise ValueError(f"Unknown sector: {sector}")

    for existing in list(case.stages):
        db.delete(existing)
    db.flush()

    stages: list[Stage] = []
    for index, spec in enumerate(rule["stages"]):
        stage = Stage(
            case_id=case.id,
            index=index,
            key=spec["key"],
            name=spec["name"],
            authority=spec["authority"],
            summary=spec["summary"],
            deadline_days=float(spec["deadline_days"]),
            ack_hours=float(spec["ack_hours"]) if spec.get("ack_hours") else None,
            regulation=spec["regulation"],
            regulation_note=spec["regulation_note"],
            source_url=spec.get("source_url"),
            required_documents=list(spec.get("required_documents", [])),
            price_paise=int(spec.get("price_paise", 4900)),
            # Stage 1 is included — the user pays to unlock escalations.
            status="awaiting_response" if index == 0 else "locked",
            paid=index == 0,
        )
        db.add(stage)
        stages.append(stage)

    db.flush()
    log_activity(
        db,
        case,
        "Timeline generated",
        f"{len(stages)} stages mapped from the {rule['label']} ladder under "
        f"{rule['primary_statute']}. Every deadline below is the real statutory window.",
        icon="route",
    )
    return stages


def start_stage_clock(db: Session, case: Case, stage: Stage) -> None:
    """Begin the deadline countdown for a stage, on the demo timescale."""
    now = utcnow()
    stage.started_at = now
    stage.deadline_at = now + dt.timedelta(seconds=demo_clock.to_seconds(stage.deadline_days))
    stage.status = "awaiting_response"

    ack_note = ""
    if stage.ack_hours:
        # ack_hours is in hours, the clock speaks days — 48h is 2 statutory days.
        stage.ack_deadline_at = now + dt.timedelta(
            seconds=demo_clock.to_seconds(stage.ack_hours / 24.0)
        )
        ack_note = (
            f" A separate {stage.ack_hours:g}-hour acknowledgement window also starts now."
        )

    log_activity(
        db,
        case,
        f"Stage {stage.index + 1} clock started",
        f"{stage.name}. Statutory window: {stage.deadline_days:g} days under "
        f"{stage.regulation}. On the demo timescale that lapses at "
        f"{stage.deadline_at.strftime('%H:%M:%S UTC')}.{ack_note}",
        icon="timer",
    )


def stage_payload(stage: Stage) -> dict:
    now = utcnow()
    remaining = None
    if stage.deadline_at and stage.status in {"awaiting_response", "paid"}:
        deadline = stage.deadline_at
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=dt.timezone.utc)
        remaining = (deadline - now).total_seconds()
    return {
        "id": stage.id,
        "index": stage.index,
        "key": stage.key,
        "name": stage.name,
        "authority": stage.authority,
        "summary": stage.summary,
        "deadline_days": stage.deadline_days,
        "ack_hours": stage.ack_hours,
        "regulation": stage.regulation,
        "regulation_note": stage.regulation_note,
        "source_url": stage.source_url,
        "required_documents": stage.required_documents or [],
        "price_paise": stage.price_paise,
        "status": stage.status,
        "paid": stage.paid,
        "started_at": iso(stage.started_at),
        "deadline_at": iso(stage.deadline_at),
        "completed_at": iso(stage.completed_at),
        "seconds_remaining": remaining,
        "ack_deadline_at": iso(stage.ack_deadline_at),
        "acknowledged_at": iso(stage.acknowledged_at),
        "ack_breached": stage.ack_breached,
        "outcome": stage.outcome,
        "outcome_note": stage.outcome_note,
    }
