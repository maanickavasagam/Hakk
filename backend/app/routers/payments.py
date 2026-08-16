"""Mock checkout. Clicking Pay marks the stage paid in the database — there is no
gateway behind this yet, and the UI says so."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Case, Payment, Stage, User
from ..security import current_user
from ..services import rules
from ..services.scheduler import generate_stage_draft
from ..services.timeline import log_activity, stage_payload, start_stage_clock

router = APIRouter(prefix="/api/cases/{case_id}/payments", tags=["payments"])


class PayRequest(BaseModel):
    kind: str = "single"  # single | bundle
    stage_id: int | None = None


def _get_case(db: Session, user: User, case_id: int) -> Case:
    case = db.get(Case, case_id)
    if case is None or case.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    return case


@router.get("/options")
def options(
    case_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    case = _get_case(db, user, case_id)
    if not case.sector:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Classify the case first")
    rule = rules.get(case.sector)
    locked = [s for s in sorted(case.stages, key=lambda s: s.index) if not s.paid]
    return {
        "single": [
            {
                "stage_id": s.id,
                "index": s.index,
                "name": s.name,
                "authority": s.authority,
                "price_paise": s.price_paise,
            }
            for s in locked
        ],
        "bundle": {
            "price_paise": rule["bundle_price_paise"],
            "stage_count": len(locked),
            "label": f"Unlock all {len(locked)} remaining stages",
        }
        if locked
        else None,
        "mock": True,
        "note": "Mock checkout — no real gateway is connected. Paying marks the stage unlocked instantly.",
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def pay(
    case_id: int,
    payload: PayRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    case = _get_case(db, user, case_id)
    if not case.sector:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Classify the case first")

    txn = "MOCK-" + secrets.token_hex(6).upper()
    unlocked: list[Stage] = []

    if payload.kind == "bundle":
        rule = rules.get(case.sector)
        amount = rule["bundle_price_paise"]
        for stage in sorted(case.stages, key=lambda s: s.index):
            if not stage.paid:
                stage.paid = True
                if stage.status == "locked" or stage.status == "awaiting_payment":
                    stage.status = "locked" if stage.index > case.current_stage_index + 1 else "paid"
                unlocked.append(stage)
        db.add(
            Payment(
                case_id=case.id,
                stage_id=None,
                kind="bundle",
                amount_paise=amount,
                mock_txn_id=txn,
            )
        )
        detail = f"Full bundle — {len(unlocked)} stage(s) unlocked for ₹{amount / 100:.0f}."
    else:
        stage = db.get(Stage, payload.stage_id) if payload.stage_id else None
        if stage is None or stage.case_id != case.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Stage not found")
        if stage.paid:
            raise HTTPException(status.HTTP_409_CONFLICT, "That stage is already unlocked")
        amount = stage.price_paise
        stage.paid = True
        stage.status = "paid"
        unlocked.append(stage)
        db.add(
            Payment(
                case_id=case.id,
                stage_id=stage.id,
                kind="single",
                amount_paise=amount,
                mock_txn_id=txn,
            )
        )
        detail = (
            f"Stage {stage.index + 1} ({stage.name}) unlocked for ₹{amount / 100:.0f}."
        )

    log_activity(db, case, "Payment received (mock)", f"{detail} Txn {txn}.", actor="user", icon="card")

    # If the current stage already lapsed while the next one was locked, the
    # payment is what unblocks it — advance immediately rather than waiting for
    # the next scheduler tick.
    current = next((s for s in case.stages if s.index == case.current_stage_index), None)
    if current is not None and current.status == "lapsed":
        nxt = next((s for s in case.stages if s.index == current.index + 1), None)
        if nxt is not None and nxt.paid:
            case.current_stage_index = nxt.index
            draft = generate_stage_draft(db, case, nxt, auto=True)
            start_stage_clock(db, case, nxt)
            log_activity(
                db,
                case,
                f"Auto-escalated to Stage {nxt.index + 1}",
                f"Unlock received after Stage {current.index + 1} lapsed. Draft #{draft.id} "
                f"for the {nxt.authority} generated from the case history, citing "
                f"{nxt.regulation}.",
                actor="agent",
                icon="zap",
            )

    db.commit()
    return {
        "ok": True,
        "mock_txn_id": txn,
        "amount_paise": amount,
        "unlocked_stage_ids": [s.id for s in unlocked],
        "stages": [stage_payload(s) for s in sorted(case.stages, key=lambda s: s.index)],
        "current_stage_index": case.current_stage_index,
    }
