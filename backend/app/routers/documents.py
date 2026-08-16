from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR
from ..db import get_db
from ..models import Case, Document, User, iso
from ..security import current_user
from ..services import extraction
from ..services.timeline import log_activity

router = APIRouter(prefix="/api/cases/{case_id}/documents", tags=["documents"])

MAX_BYTES = 15 * 1024 * 1024
ALLOWED_SUFFIXES = {
    ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff",
    ".txt", ".csv", ".md", ".eml",
}


class ConfirmField(BaseModel):
    key: str
    label: str
    value: str
    display: str | None = None


class ConfirmRequest(BaseModel):
    fields: list[ConfirmField]


def _get_case(db: Session, user: User, case_id: int) -> Case:
    case = db.get(Case, case_id)
    if case is None or case.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    return case


def _payload(doc: Document) -> dict:
    source = doc.confirmed if doc.is_confirmed and doc.confirmed else doc.extracted
    return {
        "id": doc.id,
        "filename": doc.filename,
        "content_type": doc.content_type,
        "size_bytes": doc.size_bytes,
        "is_confirmed": doc.is_confirmed,
        "extraction_method": doc.extraction_method,
        "extraction_note": doc.extraction_note,
        "disclaimer": (doc.extracted or {}).get("disclaimer", ""),
        "fields": (source or {}).get("fields", []),
        "created_at": iso(doc.created_at),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload(
    case_id: int,
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    case = _get_case(db, user, case_id)

    original = Path(file.filename or "upload").name
    suffix = Path(original).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported file type '{suffix or 'unknown'}'. Upload a PDF, image or text file.",
        )

    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File exceeds 15 MB")
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The uploaded file is empty")

    stored_name = f"{case.id}_{secrets.token_hex(8)}{suffix}"
    path = UPLOAD_DIR / stored_name
    path.write_bytes(data)

    analysis = extraction.analyse(path, file.content_type or "")

    doc = Document(
        case_id=case.id,
        filename=original,
        stored_name=stored_name,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(data),
        extracted=analysis,
        confirmed={},
        is_confirmed=False,
        extraction_method=analysis["method"],
        extraction_note=analysis["note"],
        raw_text=analysis["raw_text"],
    )
    db.add(doc)
    db.flush()

    detected = len(analysis["fields"])
    log_activity(
        db,
        case,
        "Document uploaded",
        f"{original} - {detected} field(s) detected via {analysis['method']}. "
        f"Awaiting your confirmation.",
        actor="user",
        icon="upload",
    )
    db.commit()
    return _payload(doc)


@router.get("")
def list_documents(
    case_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    case = _get_case(db, user, case_id)
    return {"documents": [_payload(d) for d in sorted(case.documents, key=lambda d: d.id)]}


@router.post("/{document_id}/confirm")
def confirm(
    case_id: int,
    document_id: int,
    payload: ConfirmRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    """The user confirms or corrects what was read. Their version wins."""
    case = _get_case(db, user, case_id)
    doc = db.get(Document, document_id)
    if doc is None or doc.case_id != case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")

    fields = [f.model_dump() for f in payload.fields if f.value.strip()]
    for field in fields:
        if not field.get("display"):
            field["display"] = field["value"]

    original = {f["key"]: f["value"] for f in (doc.extracted or {}).get("fields", [])}
    corrected = [f["label"] for f in fields if original.get(f["key"]) != f["value"]]

    doc.confirmed = {"fields": fields}
    doc.is_confirmed = True

    detail = f"{doc.filename} - {len(fields)} field(s) confirmed."
    if corrected:
        detail += f" Corrected by you: {', '.join(corrected)}."
    log_activity(db, case, "Extracted details confirmed", detail, actor="user", icon="check")
    db.commit()
    return _payload(doc)


@router.delete("/{document_id}")
def delete_document(
    case_id: int,
    document_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    case = _get_case(db, user, case_id)
    doc = db.get(Document, document_id)
    if doc is None or doc.case_id != case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    (UPLOAD_DIR / doc.stored_name).unlink(missing_ok=True)
    db.delete(doc)
    log_activity(db, case, "Document removed", doc.filename, actor="user", icon="trash")
    db.commit()
    return {"ok": True}
