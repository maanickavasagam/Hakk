"""Free-text intake extraction.

Turns "I ordered headphones from Flipkart on the 14th, paid 2500, they never
showed up" into the same structured shape the guided form collects — so
everything downstream (classify, build_timeline, drafter) stays untouched. This
module only produces a *candidate* answer set; nothing is saved until the user
reviews and confirms it, the same pattern documents.py already uses for
extracted document fields.

Same two-tier fallback as classifier.py: Anthropic, then Groq. Unlike
classification there is no third, keyword-based tier — turning open prose into
nine structured fields isn't something a keyword scorer can do credibly, so
with no LLM key configured this returns None and the caller falls back to the
guided form instead of pretending to have understood.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..config import (
    ANTHROPIC_API_KEY,
    CLASSIFIER_MODEL,
    GROQ_API_KEY,
    GROQ_CLASSIFIER_MODEL,
)
from .intake_fields import (
    DESIRED_RESOLUTION_OPTIONS,
    PRIOR_CONTACT_OPTIONS,
    WHAT_HAPPENED_OPTIONS,
)

log = logging.getLogger("hakk.intake_extractor")

WhatHappened = Literal[tuple(WHAT_HAPPENED_OPTIONS)]  # type: ignore[valid-type]
DesiredResolution = Literal[tuple(DESIRED_RESOLUTION_OPTIONS)]  # type: ignore[valid-type]
PriorContact = Literal[tuple(PRIOR_CONTACT_OPTIONS)]  # type: ignore[valid-type]


class ExtractedIntake(BaseModel):
    understood: bool = Field(
        description=(
            "False only if the text is not a consumer complaint at all — empty, gibberish, "
            "spam, or a question unrelated to a dispute with a company. A complaint about a "
            "sector Hakk doesn't cover (e.g. a landlord, an employer, a hospital) is still "
            "'understood' — sector coverage is decided later by classification, not here."
        )
    )
    clarifying_note: str = Field(
        default="",
        description=(
            "One short sentence on what's missing or ambiguous in what the user wrote, so "
            "they know what to add on the confirmation screen. Empty string if the text was "
            "clear and complete enough to work with."
        ),
    )
    what_happened: WhatHappened = Field(
        description="The closest matching category. Use 'Something else' if none fit well."
    )
    what_happened_detail: str = Field(
        description=(
            "A cleaned-up two-to-three sentence version of what the user described, in their "
            "own facts — do not invent details they didn't give you."
        )
    )
    company: str | None = Field(default=None, description="The company or service named, if any.")
    reference_number: str | None = Field(
        default=None, description="Order, transaction or account reference, if mentioned."
    )
    amount_involved: str | None = Field(
        default=None, description="The rupee amount in dispute as a bare number, no currency symbol."
    )
    when_it_happened: str | None = Field(
        default=None,
        description="Date of the incident as YYYY-MM-DD if determinable from the text, else null.",
    )
    desired_resolution: DesiredResolution = Field(
        description="The closest matching desired outcome. Infer the most likely one if not stated."
    )
    prior_contact: PriorContact = Field(
        description="Whether and how the user says they already contacted the company."
    )
    prior_contact_detail: str | None = Field(
        default=None, description="What the company said, if the user mentioned it."
    )


SYSTEM_PROMPT = """You turn a consumer's free-text description of a dispute into structured \
intake fields for Hakk, a consumer-complaint drafting tool.

Extract only what the user actually said. Where a fact is missing, leave that field null or \
choose the closest defensible option — do not invent order numbers, amounts, dates or company \
names that were not mentioned.

what_happened, desired_resolution and prior_contact are closed categories: pick the single \
closest match from the options given, even if imperfect. Use "Something else" for \
what_happened only when nothing else is close.

If the text is not describing a dispute with a company at all — it's empty, gibberish, a \
greeting, or unrelated to a complaint — set understood to false and leave the other fields as \
reasonable defaults. A complaint about something outside e-commerce, banking, telecom, \
insurance or airlines (a landlord, an employer, a hospital, a school) is still understood; \
Hakk decides sector coverage in a separate step, not here."""


def _build_prompt(text: str) -> str:
    today = dt.date.today().isoformat()
    return (
        f"Today's date is {today}. Resolve relative dates ('last week', 'in March', "
        f"'three days ago') against it, and prefer the most recent past occurrence for a "
        f"bare month/day with no year.\n\n"
        f"<complaint_in_own_words>\n{text.strip()}\n</complaint_in_own_words>\n\n"
        f"Extract the intake fields."
    )


def _extract_with_anthropic(text: str) -> ExtractedIntake | None:
    if not ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic
    except ImportError:
        log.info("anthropic SDK not installed")
        return None
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.parse(
            model=CLASSIFIER_MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_prompt(text)}],
            output_format=ExtractedIntake,
        )
        if response.stop_reason == "refusal":
            log.warning("Anthropic intake extraction refused; trying next fallback")
            return None
        return response.parsed_output
    except Exception as exc:
        log.warning("Anthropic intake extraction failed (%s); trying next fallback", exc)
        return None


_JSON_MODE_INSTRUCTIONS = f"""
Respond with ONLY a single JSON object, no other text, matching exactly this shape:
{{
  "understood": <true|false>,
  "clarifying_note": "<one sentence, or empty string>",
  "what_happened": {" | ".join(f'"{o}"' for o in WHAT_HAPPENED_OPTIONS)},
  "what_happened_detail": "<two or three sentences>",
  "company": "<string or null>",
  "reference_number": "<string or null>",
  "amount_involved": "<bare number as a string, or null>",
  "when_it_happened": "<YYYY-MM-DD or null>",
  "desired_resolution": {" | ".join(f'"{o}"' for o in DESIRED_RESOLUTION_OPTIONS)},
  "prior_contact": {" | ".join(f'"{o}"' for o in PRIOR_CONTACT_OPTIONS)},
  "prior_contact_detail": "<string or null>"
}}"""


def _extract_with_groq(text: str) -> ExtractedIntake | None:
    if not GROQ_API_KEY:
        return None
    try:
        import groq
    except ImportError:
        log.info("groq SDK not installed")
        return None
    try:
        client = groq.Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=GROQ_CLASSIFIER_MODEL,
            max_tokens=1200,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT + "\n" + _JSON_MODE_INSTRUCTIONS},
                {"role": "user", "content": _build_prompt(text)},
            ],
        )
        content = response.choices[0].message.content
        return ExtractedIntake.model_validate(json.loads(content))
    except Exception as exc:
        log.warning("Groq intake extraction failed (%s); extraction unavailable", exc)
        return None


def extract(text: str) -> dict[str, Any] | None:
    """Returns a candidate answers dict shaped like the guided form's, plus
    `understood` and `clarifying_note` for the confirmation screen. None means
    no extraction path is available (no API key) — the caller should fall back
    to the guided form rather than show an empty confirmation screen."""
    result = _extract_with_anthropic(text) or _extract_with_groq(text)
    if result is None:
        return None

    answers = {
        "what_happened": result.what_happened,
        "what_happened_detail": result.what_happened_detail,
        "desired_resolution": result.desired_resolution,
        "prior_contact": result.prior_contact,
    }
    for key, value in (
        ("company", result.company),
        ("reference_number", result.reference_number),
        ("amount_involved", result.amount_involved),
        ("when_it_happened", result.when_it_happened),
        ("prior_contact_detail", result.prior_contact_detail),
    ):
        if value:
            answers[key] = value

    return {
        "answers": answers,
        "understood": result.understood,
        "clarifying_note": result.clarifying_note,
    }


def extraction_available() -> bool:
    if ANTHROPIC_API_KEY:
        try:
            import anthropic  # noqa: F401

            return True
        except ImportError:
            pass
    if GROQ_API_KEY:
        try:
            import groq  # noqa: F401

            return True
        except ImportError:
            pass
    return False
