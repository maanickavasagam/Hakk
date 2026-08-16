"""Document text extraction.

IMPORTANT product framing: this is a COMPLETENESS check, not a fraud or
authenticity check. We pull structured fields out of whatever text we can read so
the user can confirm or correct them, and so later drafts can cite the right
order ID and amount. We make no claim about whether a document is genuine.

Extraction ladder, best available first:
  1. PDF text layer          (pypdf)
  2. Image OCR               (pytesseract, only if the binary is installed)
  3. Plain text / filename   (always available)
Whatever we manage, the user confirms or corrects the result in the UI.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_CURRENCY = r"(?:₹|rs\.?|inr)\s*"
_AMOUNT = r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)"

FIELD_PATTERNS: list[tuple[str, str, str]] = [
    # (field key, human label, regex with one capture group)
    ("order_id", "Order ID", r"(?:order|order\s*(?:id|no\.?|number)|ord)\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-/]{4,24})"),
    ("invoice_no", "Invoice No.", r"(?:invoice|bill)\s*(?:id|no\.?|number)?\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-/]{3,24})"),
    ("transaction_id", "Transaction ID", r"(?:txn|transaction|utr|rrn|reference)\s*(?:id|no\.?|number)?\s*[:#\-]?\s*([A-Z0-9]{6,30})"),
    ("amount", "Amount", _CURRENCY + _AMOUNT),
    ("total", "Total", r"(?:total|grand\s*total|amount\s*payable)\s*[:\-]?\s*" + _CURRENCY + "?" + _AMOUNT),
    ("date", "Date", r"(?:date|dated|on)\s*[:\-]?\s*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})"),
    ("account_last4", "Account (last 4)", r"(?:a/c|account|card)\s*(?:no\.?|number)?\s*[:\-]?\s*(?:x{2,}|\*{2,})?(\d{4})\b"),
    ("mobile", "Mobile Number", r"\b((?:\+91[\-\s]?)?[6-9]\d{9})\b"),
    ("email", "Email", r"\b([\w.+-]+@[\w-]+\.[\w.]{2,})\b"),
    ("tracking_id", "Tracking ID", r"(?:awb|tracking|consignment)\s*(?:id|no\.?|number)?\s*[:#\-]?\s*([A-Z0-9]{6,24})"),
]

_NOISE = {"NUMBER", "DETAILS", "STATUS", "TOTAL", "AMOUNT", "DATE", "SUMMARY"}


def _read_pdf(path: Path) -> tuple[str, str]:
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover
        return "", "pypdf not installed"
    try:
        reader = PdfReader(str(path))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # corrupt / encrypted PDF
        return "", f"PDF could not be parsed ({exc.__class__.__name__})"
    if text.strip():
        return text, "pdf_text_layer"
    return "", "PDF has no selectable text layer (likely a scan)"


def _read_image(path: Path) -> tuple[str, str]:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return "", "OCR engine not installed"
    try:
        text = pytesseract.image_to_string(Image.open(path))
    except Exception as exc:
        # pytesseract raises if the tesseract binary itself is missing.
        return "", f"OCR unavailable ({exc.__class__.__name__})"
    if text.strip():
        return text, "image_ocr"
    return "", "No text detected in the image"


def _read_text(path: Path) -> tuple[str, str]:
    try:
        return path.read_text(encoding="utf-8", errors="ignore"), "plain_text"
    except Exception:
        return "", "File could not be read as text"


def extract_text(path: Path, content_type: str) -> tuple[str, str, str]:
    """Returns (text, method, note)."""
    suffix = path.suffix.lower()
    if suffix == ".pdf" or "pdf" in content_type:
        text, method = _read_pdf(path)
        if text:
            return text, method, "Read from the PDF's embedded text layer."
        return "", "none", method
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"} or content_type.startswith("image/"):
        text, method = _read_image(path)
        if text:
            return text, method, "Read via optical character recognition."
        return "", "none", method
    if suffix in {".txt", ".csv", ".md", ".json", ".eml"} or content_type.startswith("text/"):
        text, method = _read_text(path)
        if text:
            return text, method, "Read as plain text."
        return "", "none", method
    return "", "none", "Unsupported file type for automatic reading"


def _clean(field: str, value: str) -> str | None:
    value = value.strip().strip(".,;:-")
    if not value:
        return None
    if field in {"amount", "total"}:
        return value.replace(",", "")
    if field in {"order_id", "invoice_no", "transaction_id", "tracking_id"}:
        if value.upper() in _NOISE or not any(ch.isdigit() for ch in value):
            return None
    return value


def parse_fields(text: str) -> list[dict[str, Any]]:
    """Pull candidate structured fields out of raw text, first match wins."""
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key, label, pattern in FIELD_PATTERNS:
        if key in seen:
            continue
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        value = _clean(key, match.group(1))
        if not value:
            continue
        seen.add(key)
        display = value
        if key in {"amount", "total"}:
            try:
                display = f"₹{float(value):,.2f}".rstrip("0").rstrip(".")
            except ValueError:
                display = f"₹{value}"
        found.append({"key": key, "label": label, "value": value, "display": display})
    return found


def analyse(path: Path, content_type: str) -> dict[str, Any]:
    text, method, note = extract_text(path, content_type)
    fields = parse_fields(text) if text else []
    if text and not fields:
        note = f"{note} No recognisable order, amount or reference fields were found — please add them manually."
    elif not text:
        note = f"{note}. Please enter the details manually below."
    return {
        "method": method,
        "note": note,
        "raw_text": text[:20000],
        "fields": fields,
        "disclaimer": (
            "Completeness check only — Hakk reads your document to pull out reference "
            "numbers and amounts so your complaint cites them correctly. This is not a "
            "fraud, forgery or authenticity check."
        ),
    }
