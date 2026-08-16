"""Single source of truth for the guided intake's closed option lists.

Both the guided form (cases.py's INTAKE_QUESTIONS) and the free-text extractor
(intake_extractor.py) need the exact same option strings — the guided form to
render buttons, the extractor to constrain what the model is allowed to pick as
`what_happened` / `desired_resolution` / `prior_contact`. Defining them twice
would let them drift apart silently; a new option added to one and not the
other breaks whichever path was missed.
"""

from __future__ import annotations

WHAT_HAPPENED_OPTIONS: list[str] = [
    "Paid but never received the product or service",
    "Refund promised but not credited",
    "Money debited but the transaction failed",
    "Unauthorised or unrecognised charge",
    "Product damaged, defective or not as described",
    "Wrongly billed or overcharged",
    "Service not working or repeatedly interrupted",
    "Cancellation or return request refused",
    "Something else",
]

DESIRED_RESOLUTION_OPTIONS: list[str] = [
    "A full refund of the amount paid",
    "A replacement or re-delivery",
    "Reversal of the wrongful charge",
    "The service restored and working",
    "A corrected bill",
    "Refund plus compensation for the inconvenience",
    "A written apology and confirmation of correction",
]

PRIOR_CONTACT_OPTIONS: list[str] = [
    "No, not yet",
    "Yes, by phone to customer care",
    "Yes, by email",
    "Yes, through their app or website chat",
    "Yes, multiple times through several channels",
]
