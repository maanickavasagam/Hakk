"""Runtime configuration for Hakk.

The demo clock lives here. Statutory deadlines are stored in the sector rules as
*real* days (30 days, 15 days, ...) and are always displayed that way. For a live
demo we compress them onto a wall-clock timescale via SECONDS_PER_DAY so a 30-day
grievance-officer window lapses in a minute instead of a month.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Use the OS certificate store rather than certifi's bundled list.
#
# Machines running TLS-inspecting antivirus/proxies (AVG, Zscaler, corporate
# MITM appliances) re-sign HTTPS with a private root that lives in the OS trust
# store. certifi doesn't know about it, so every outbound Python HTTPS call dies
# with CERTIFICATE_VERIFY_FAILED even though curl and browsers work fine. This
# must run before any SSL context is created, hence its position here — config
# is imported first by everything.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:  # pragma: no cover - optional dependency
    logging.getLogger("hakk.config").debug(
        "truststore not installed; falling back to certifi's CA bundle"
    )

BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR.parent

load_dotenv(BACKEND_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'hakk.db'}")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BACKEND_DIR / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

JWT_SECRET = os.getenv("JWT_SECRET", "hakk-dev-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "72"))

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
CLASSIFIER_MODEL = os.getenv("CLASSIFIER_MODEL", "claude-opus-5")
DRAFTER_MODEL = os.getenv("DRAFTER_MODEL", "claude-opus-5")

# Groq (OpenAI-compatible) fallback/alternate LLM provider. If ANTHROPIC_API_KEY
# is unset but GROQ_API_KEY is present, classifier.py and drafter.py use Groq
# instead. Both providers produce the same output shape to the rest of the app.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_CLASSIFIER_MODEL = os.getenv("GROQ_CLASSIFIER_MODEL", "llama-3.3-70b-versatile")
GROQ_DRAFTER_MODEL = os.getenv("GROQ_DRAFTER_MODEL", "llama-3.3-70b-versatile")

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
# Google shows app passwords as four space-separated groups and users paste them
# that way; the SMTP AUTH exchange wants the 16 characters with no spaces.
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").replace(" ", "").strip()
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Hakk")
SMTP_TIMEOUT_SECONDS = int(os.getenv("SMTP_TIMEOUT_SECONDS", "12"))

# Anything at or below this drops the user onto the "couldn't confidently
# classify" screen instead of generating a draft.
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.55"))

CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "help@hakk.legal")
CONTACT_PHONE = os.getenv("CONTACT_PHONE", "+91 80 4718 2200")

# Where email alerts link back to. The Vite dev default; override in
# production so "Open this case" in an emailed alert doesn't point at
# localhost.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")

SCHEDULER_INTERVAL_SECONDS = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "5"))


class DemoClock:
    """Mutable so the walkthrough can speed the timescale up mid-demo."""

    def __init__(self) -> None:
        self.enabled = os.getenv("DEMO_MODE", "true").lower() != "false"
        # 1 statutory day -> this many real seconds. 2.0 puts a 30-day window at
        # 60s and a 15-day window at 30s, preserving relative proportions.
        self.seconds_per_day = float(os.getenv("DEMO_SECONDS_PER_DAY", "2.0"))

    def to_seconds(self, statutory_days: float) -> float:
        if not self.enabled:
            return statutory_days * 86400.0
        return statutory_days * self.seconds_per_day

    def as_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "seconds_per_day": self.seconds_per_day,
            "description": (
                f"1 statutory day = {self.seconds_per_day:g}s"
                if self.enabled
                else "real time (1 day = 24h)"
            ),
        }


demo_clock = DemoClock()
