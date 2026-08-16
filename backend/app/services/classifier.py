"""Sector classification.

Three paths, tried in order, all returning the same validated shape:
  1. Anthropic  — Claude with server-side schema enforcement (messages.parse)
  2. Groq       — OpenAI-compatible JSON mode; schema is enforced client-side by
                  validating the returned JSON against the same pydantic model
  3. Keywords   — a transparent scorer, so the product works with no API key at all

Whichever runs, low confidence routes the user to the "we couldn't confidently
classify this" screen rather than a dead end, and `classified_by` tells the UI
which path actually produced the answer.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..config import (
    ANTHROPIC_API_KEY,
    CLASSIFIER_MODEL,
    CONFIDENCE_THRESHOLD,
    GROQ_API_KEY,
    GROQ_CLASSIFIER_MODEL,
)
from . import rules

log = logging.getLogger("hakk.classifier")

# Both the schema the model is held to and the prompt describing the options are
# derived from the sector rule files, so adding a sector stays a matter of adding
# one JSON file. Literal accepts a tuple, which is what makes this possible.
SECTOR_KEYS: tuple[str, ...] = tuple(sorted(rules.load_all())) + ("unknown",)
SectorName = Literal[SECTOR_KEYS]  # type: ignore[valid-type]


class Classification(BaseModel):
    sector: SectorName = Field(
        description=(
            "The regulatory sector this dispute belongs to. Use 'unknown' if the "
            "complaint does not clearly fall in any of the listed sectors."
        )
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="How confident you are, from 0.0 to 1.0."
    )
    reasoning: str = Field(
        description="Two or three sentences explaining the classification, for the user to read."
    )
    key_facts: list[str] = Field(
        default_factory=list,
        description="Up to 5 short factual bullets extracted from the complaint.",
    )


def sector_list() -> str:
    """'e-commerce, banking & UPI, insurance, telecom or airlines' — the covered
    sectors as prose, for user-facing copy that would otherwise go stale every
    time a sector is added."""
    labels = [rule["label"].lower() for rule in rules.load_all().values()]
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + f" or {labels[-1]}"


def _sector_menu() -> str:
    """The list of sectors the model may choose from, rendered from the rule
    files so a new JSON drop-in appears here without touching this module."""
    lines = []
    for key, rule in sorted(rules.load_all().items()):
        lines.append(f"- {key}: {rule['blurb']} Governed by the {rule['primary_statute']}.")
    lines.append("- unknown: anything else, or a complaint too vague to place with confidence.")
    return "\n".join(lines)


SYSTEM_PROMPT = f"""You classify Indian consumer complaints into the regulatory sector \
whose grievance ladder applies, so the correct statute can be cited.

Sectors:
{_sector_menu()}

Judge by which regulator would actually hear the complaint, not by which brand is \
named. A payment made on a shopping site that was never refunded is an e-commerce \
dispute; money debited by the bank for a transaction the customer never authorised \
is a banking dispute; a flight cancelled by the airline is an airlines dispute even \
when the ticket was bought through a travel marketplace.

Be honest about confidence. Report below {CONFIDENCE_THRESHOLD} when the complaint \
is vague, mixes sectors, or names no identifiable service — a low score routes the \
user to a human, which is the correct outcome. Do not inflate confidence to seem \
decisive."""


def _build_prompt(answers: dict[str, Any], documents: list[dict[str, Any]]) -> str:
    lines = ["<complaint>"]
    for key, value in answers.items():
        if value in (None, "", [], {}):
            continue
        label = key.replace("_", " ").title()
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        lines.append(f"{label}: {value}")
    lines.append("</complaint>")

    if documents:
        lines.append("\n<extracted_document_data>")
        for doc in documents:
            fields = doc.get("fields") or []
            rendered = "; ".join(f"{f['label']}={f['value']}" for f in fields) or "no fields read"
            lines.append(f"- {doc.get('filename', 'document')}: {rendered}")
        lines.append("</extracted_document_data>")

    lines.append("\nClassify this complaint into its regulatory sector.")
    return "\n".join(lines)


# Groq's JSON mode (like most OpenAI-compatible APIs) needs the schema spelled
# out in the prompt itself — unlike Claude's messages.parse, there's no
# server-side schema enforcement, so the model has to be told the exact shape.
_JSON_MODE_INSTRUCTIONS = f"""
Respond with ONLY a single JSON object, no other text, matching exactly this shape:
{{
  "sector": {" | ".join(f'"{k}"' for k in SECTOR_KEYS)},
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<two or three sentences>",
  "key_facts": ["<short bullet>", ...]
}}"""


def _classify_with_anthropic(
    answers: dict[str, Any], documents: list[dict[str, Any]]
) -> Classification | None:
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
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_prompt(answers, documents)}],
            output_format=Classification,
        )
        if response.stop_reason == "refusal":
            log.warning("Anthropic classifier refused; trying next fallback")
            return None
        return response.parsed_output
    except Exception as exc:
        log.warning("Anthropic classification failed (%s); trying next fallback", exc)
        return None


def _classify_with_groq(
    answers: dict[str, Any], documents: list[dict[str, Any]]
) -> Classification | None:
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
            max_tokens=1000,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT + "\n" + _JSON_MODE_INSTRUCTIONS},
                {"role": "user", "content": _build_prompt(answers, documents)},
            ],
        )
        content = response.choices[0].message.content
        return Classification.model_validate(json.loads(content))
    except Exception as exc:
        log.warning("Groq classification failed (%s); using keyword classifier", exc)
        return None


def _classify_with_keywords(
    answers: dict[str, Any], documents: list[dict[str, Any]]
) -> Classification:
    haystack_parts = [str(v) for v in answers.values() if v]
    for doc in documents:
        haystack_parts.append(doc.get("filename", ""))
        for field in doc.get("fields") or []:
            haystack_parts.append(str(field.get("value", "")))
    haystack = " ".join(haystack_parts).lower()

    scores: dict[str, float] = {}
    hits: dict[str, list[str]] = {}
    for sector, rule in rules.load_all().items():
        matched = [kw for kw in rule["keywords"] if kw in haystack]
        # Multi-word keywords are far more specific than single tokens.
        score = sum(2.0 if " " in kw else 1.0 for kw in matched)
        scores[sector] = score
        hits[sector] = matched

    if not scores or max(scores.values()) == 0:
        return Classification(
            sector="unknown",
            confidence=0.0,
            reasoning=(
                f"No recognisable {sector_list()} service was mentioned in the complaint, "
                f"so the matching regulatory ladder could not be determined."
            ),
            key_facts=[],
        )

    best = max(scores, key=lambda s: scores[s])
    total = sum(scores.values()) or 1.0
    share = scores[best] / total
    # Confidence needs both a decisive winner and enough absolute signal.
    volume = min(scores[best] / 5.0, 1.0)
    confidence = round(min(0.94, 0.35 + 0.4 * share + 0.25 * volume), 2)

    label = rules.get(best)["label"]
    return Classification(
        sector=best,  # type: ignore[arg-type]
        confidence=confidence,
        reasoning=(
            f"Matched the {label} ladder on the terms: "
            f"{', '.join(hits[best][:6])}. Classified without a model call using "
            f"Hakk's keyword rules."
        ),
        key_facts=[f"Matched term: {kw}" for kw in hits[best][:5]],
    )


def classify(answers: dict[str, Any], documents: list[dict[str, Any]]) -> dict[str, Any]:
    result = _classify_with_anthropic(answers, documents)
    source = "anthropic"
    if result is None:
        result = _classify_with_groq(answers, documents)
        source = "groq"
    if result is None:
        result = _classify_with_keywords(answers, documents)
        source = "keywords"

    sector = result.sector
    confidence = result.confidence
    reasoning = result.reasoning

    # Deterministic backstop: an LLM will still latch onto generic words like
    # "bill" or "plan" as if they were sector-specific, even when told to be
    # honest about confidence (verified live — Groq/Llama classified a
    # company-less billing complaint as telecom @ 80%). Without a named
    # company/service AND without any uploaded document, there is nothing
    # sector-specific to go on, so cap confidence below the threshold instead
    # of trusting the model's self-reported score.
    company = str(answers.get("company") or "").strip()
    if sector != "unknown" and not company and not documents and confidence >= CONFIDENCE_THRESHOLD:
        confidence = round(min(confidence, CONFIDENCE_THRESHOLD - 0.05), 2)
        reasoning = (
            f"{reasoning.rstrip('.')}. No company or service name was given and no "
            "supporting document was uploaded, so Hakk capped its confidence below "
            "the threshold rather than guess the sector from generic language alone."
        )

    confident = sector != "unknown" and confidence >= CONFIDENCE_THRESHOLD
    rule = rules.get(sector) if sector != "unknown" else None

    return {
        "sector": sector if confident else None,
        "sector_label": rule["label"] if (rule and confident) else None,
        "confidence": confidence,
        "reasoning": reasoning,
        "key_facts": result.key_facts,
        "confident": confident,
        "threshold": CONFIDENCE_THRESHOLD,
        "classified_by": source,
    }


def llm_available() -> bool:
    return llm_provider() is not None


def llm_provider() -> str | None:
    """Which provider will actually serve a call right now, or None if the app
    is running on the keyword/template fallbacks."""
    if ANTHROPIC_API_KEY:
        try:
            import anthropic  # noqa: F401

            return "anthropic"
        except ImportError:
            pass
    if GROQ_API_KEY:
        try:
            import groq  # noqa: F401

            return "groq"
        except ImportError:
            pass
    return None
