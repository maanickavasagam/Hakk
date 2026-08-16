"""Complaint draft generation.

The legal basis is never invented and never hardcoded to one statute: it is read
off the Stage row, which was populated from that sector's JSON rule file. The
e-commerce ladder cites the E-Commerce Rules 2020, banking cites RB-IOS 2026,
telecom cites the TCCR 2012 — because the stage says so.

Same three paths as the classifier, tried in order: Anthropic, then Groq, then a
formal template that needs no API key at all. `generated_by` on the returned
draft names whichever one actually produced the letter, so the UI can say which
rather than implying every draft came from a model.

Every draft is returned for the user to review and edit. Nothing is ever sent
without an explicit approval action.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from ..config import (
    ANTHROPIC_API_KEY,
    DRAFTER_MODEL,
    GROQ_API_KEY,
    GROQ_DRAFTER_MODEL,
)

log = logging.getLogger("hakk.drafter")

SYSTEM_PROMPT = """You draft formal consumer grievance letters for Indian consumers.

Rules you must follow:
- Use the exact regulation supplied in <legal_basis>. Never cite a statute, rule, \
clause or scheme that was not given to you, and never substitute a different one.
- Formal, measured, legally-toned register. No emotional language, no threats, no \
rhetorical questions, no marketing tone.
- Ground every factual assertion in the supplied complaint details. Where a detail \
is missing, write a clearly bracketed placeholder such as [ORDER DATE] rather than \
inventing a fact.
- Structure: reference line, subject line, salutation, numbered factual paragraphs, \
a paragraph stating the legal basis and the redressal window it prescribes, a \
numbered list of the relief sought, a closing line stating the next escalation step \
if the deadline passes, and a signature block.
- State deadlines exactly as the regulation prescribes them. Do not invent penalties \
or compensation figures that the regulation does not provide for.
- Output the letter body only. No preamble, no commentary, no markdown code fences."""


def _format_date(value: Any) -> str:
    """Render an intake date as '14 March 2026' rather than a raw ISO string."""
    if not value:
        return "[DATE OF INCIDENT]"
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(text, fmt).strftime("%d %B %Y")
        except ValueError:
            continue
    return text


def _amount_summary(documents: list[dict[str, Any]]) -> str:
    for doc in documents:
        for field in doc.get("fields") or []:
            if field.get("key") in {"amount", "total"}:
                return field.get("display") or field.get("value") or ""
    return ""


def _doc_lines(documents: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for doc in documents:
        fields = doc.get("fields") or []
        if not fields:
            lines.append(f"{doc.get('filename', 'Document')} (no fields read)")
            continue
        rendered = ", ".join(f"{f['label']}: {f.get('display') or f['value']}" for f in fields)
        lines.append(f"{doc.get('filename', 'Document')} — {rendered}")
    return lines


def _history_block(history: list[dict[str, Any]]) -> str:
    if not history:
        return ""
    parts = ["\n<case_history>"]
    for item in history:
        parts.append(
            f"- Stage {item['index'] + 1} ({item['name']}, {item['authority']}): "
            f"{item['outcome']}"
        )
    parts.append("</case_history>")
    return "\n".join(parts)


def _build_prompt(ctx: dict[str, Any]) -> str:
    stage = ctx["stage"]
    answers = ctx["answers"]
    lines = [
        "<legal_basis>",
        f"Regulation: {stage['regulation']}",
        f"What it provides: {stage['regulation_note']}",
        f"Prescribed redressal window: {stage['deadline_days']:g} days",
    ]
    if stage.get("ack_hours"):
        lines.append(f"Prescribed acknowledgement window: {stage['ack_hours']:g} hours")
    lines.append("</legal_basis>")

    lines += [
        "\n<addressee>",
        f"{stage['authority']}, {ctx.get('company') or 'the service provider'}",
        "</addressee>",
        "\n<complainant>",
        f"Name: {ctx.get('user_name') or '[YOUR NAME]'}",
        f"Email: {ctx.get('user_email') or '[YOUR EMAIL]'}",
        f"Phone: {ctx.get('user_phone') or '[YOUR PHONE]'}",
        "</complainant>",
        "\n<complaint_details>",
    ]
    for key, value in answers.items():
        if value in (None, "", [], {}):
            continue
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        lines.append(f"{key.replace('_', ' ').title()}: {value}")
    lines.append("</complaint_details>")

    docs = _doc_lines(ctx.get("documents") or [])
    if docs:
        lines.append("\n<supporting_documents>")
        lines += [f"- {d}" for d in docs]
        lines.append("</supporting_documents>")

    lines.append(_history_block(ctx.get("history") or []))
    lines.append(
        f"\nDraft the letter for stage {stage['index'] + 1} of this ladder: "
        f"{stage['name']}, addressed to the {stage['authority']}."
    )
    if ctx.get("history"):
        lines.append(
            "This is an escalation. Open by referencing the earlier stages and the fact "
            "that the prescribed window lapsed without adequate redressal."
        )
    return "\n".join(lines)


def _draft_with_anthropic(ctx: dict[str, Any]) -> str | None:
    if not ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic
    except ImportError:
        log.info("anthropic SDK not installed")
        return None
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=DRAFTER_MODEL,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_prompt(ctx)}],
        )
        if response.stop_reason == "refusal":
            log.warning("Anthropic drafter refused; trying next fallback")
            return None
        text = "\n".join(b.text for b in response.content if b.type == "text").strip()
        return text or None
    except Exception as exc:
        log.warning("Anthropic drafting failed (%s); trying next fallback", exc)
        return None


def _draft_with_groq(ctx: dict[str, Any]) -> str | None:
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
            model=GROQ_DRAFTER_MODEL,
            max_tokens=4000,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_prompt(ctx)},
            ],
        )
        text = (response.choices[0].message.content or "").strip()
        return _strip_fences(text) or None
    except Exception as exc:
        log.warning("Groq drafting failed (%s); using template", exc)
        return None


def _strip_fences(text: str) -> str:
    """Open models wrap prose in ``` fences more often than Claude does, despite
    being told not to. Peel one off rather than printing it in a legal letter."""
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _template_draft(ctx: dict[str, Any]) -> str:
    stage = ctx["stage"]
    answers = ctx["answers"]
    company = ctx.get("company") or "[COMPANY NAME]"
    today = dt.date.today().strftime("%d %B %Y")
    amount = _amount_summary(ctx.get("documents") or [])

    what = str(
        answers.get("what_happened_detail") or answers.get("what_happened") or "[DESCRIBE THE ISSUE]"
    ).strip().rstrip(".")
    category = answers.get("what_happened") or ""
    when = _format_date(answers.get("when_it_happened"))
    resolution = answers.get("desired_resolution") or "a full refund of the amount paid"
    prior = answers.get("prior_contact") or "No prior contact attempt was recorded."

    escalation = ctx.get("next_stage_name")
    escalation_line = (
        f"Should the period prescribed above expire without satisfactory redressal, I shall "
        f"escalate this matter to the {escalation} without further notice."
        if escalation
        else "Should the period prescribed above expire without satisfactory redressal, I shall "
        "pursue such further remedies as are available to me in law."
    )

    history_para = ""
    if ctx.get("history"):
        # Never .lower() the outcome — it carries the regulation's proper name.
        prior_items = "; ".join(
            f"Stage {h['index'] + 1} ({h['name']}), on which {h['outcome']}"
            for h in ctx["history"]
        )
        history_para = (
            f"\n3. This representation follows earlier escalations in this matter, namely "
            f"{prior_items}. The redressal period prescribed at each of those stages expired "
            f"without the grievance being resolved.\n"
        )

    doc_block = ""
    docs = _doc_lines(ctx.get("documents") or [])
    if docs:
        listed = "\n".join(f"   ({chr(97 + i)}) {d}" for i, d in enumerate(docs))
        doc_block = f"\nThe following records are enclosed in support of this complaint:\n{listed}\n"

    amount_clause = f" The amount in dispute is {amount}." if amount else ""

    return f"""Date: {today}

To,
The {stage['authority']}
{company}

Ref: Consumer grievance — {category or 'service deficiency'}{' / ' + str(answers.get('reference_number')) if answers.get('reference_number') else ''}

Subject: Complaint under {stage['regulation']} seeking redressal of consumer grievance

Sir / Madam,

1. I, {ctx.get('user_name') or '[YOUR NAME]'}, a consumer of {company}, write to place on \
record a grievance arising out of a deficiency in the service rendered to me, and to seek \
redressal in accordance with the provisions cited below.

2. The facts are these. On or about {when}, {what}.{amount_clause}
{history_para}
{4 if history_para else 3}. Prior attempts at resolution: {prior}

{5 if history_para else 4}. The present complaint is made under {stage['regulation']}. \
{stage['regulation_note']} Accordingly, the prescribed period for redressal of this \
grievance is {stage['deadline_days']:g} days from the date of receipt of this \
communication{f", with acknowledgement due within {stage['ack_hours']:g} hours" if stage.get('ack_hours') else ""}.
{doc_block}
In the premises, I request that you be pleased to:

   (i)  {resolution};
   (ii) confirm in writing the action taken on this complaint, together with the \
complaint reference number allotted to it; and
   (iii) do so within the period prescribed under {stage['regulation']}.

{escalation_line}

Yours faithfully,

{ctx.get('user_name') or '[YOUR NAME]'}
{ctx.get('user_email') or '[YOUR EMAIL]'}
{ctx.get('user_phone') or '[YOUR PHONE]'}
"""


def generate(ctx: dict[str, Any]) -> dict[str, Any]:
    """ctx keys: stage, answers, documents, company, user_name/email/phone,
    history, next_stage_name."""
    body = _draft_with_anthropic(ctx)
    generated_by = "anthropic"
    if not body:
        body = _draft_with_groq(ctx)
        generated_by = "groq"
    if not body:
        body = _template_draft(ctx)
        generated_by = "template"

    stage = ctx["stage"]
    subject = (
        f"Complaint under {stage['regulation'].split('—')[0].strip()} — "
        f"{ctx.get('company') or 'service provider'}"
    )
    return {
        "subject": subject[:290],
        "body": body,
        "legal_basis": stage["regulation"],
        "generated_by": generated_by,
    }
