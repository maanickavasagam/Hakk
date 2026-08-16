"""Outbound email.

Two senders, same best-effort contract: never raise, always return
(delivered, reason).

- `send_otp` — sign-in codes. If SMTP is not configured, or the send fails,
  auth falls back to printing the code to the server console rather than
  locking the user out.
- `send_alert` — case notifications (deadline reminders, lapses,
  auto-escalations, handoffs). The in-app toast/banner from the same
  Notification row is always the notification of record; this is a
  reach-you-elsewhere channel on top of it, not a replacement, so a failed
  send here is logged and swallowed rather than surfaced anywhere.

Both block the calling thread (smtplib is synchronous). That's fine today: OTP
sends happen inside a FastAPI request, which already runs sync `def` handlers
in a threadpool, and alert sends happen inside the APScheduler background tick,
which isn't the request thread either — neither blocks request handling.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from ..config import (
    FRONTEND_URL,
    SMTP_FROM_NAME,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
    SMTP_TIMEOUT_SECONDS,
)

log = logging.getLogger("hakk.mailer")


def is_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def mask(address: str) -> str:
    """'maanickambala@gmail.com' -> 'maa***@gmail.com'. The UI tells the user
    which inbox to check without printing the whole address back at them."""
    local, _, domain = address.partition("@")
    if not domain:
        return "***"
    keep = local[:3] if len(local) > 4 else local[:1]
    return f"{keep}***@{domain}"


def _send(message: EmailMessage) -> None:
    # Port 465 is implicit TLS; 587 (the Gmail default here) is STARTTLS.
    context = ssl.create_default_context()
    if SMTP_PORT == 465:
        with smtplib.SMTP_SSL(
            SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS, context=context
        ) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)
        return

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(message)


def _otp_message(to_email: str, code: str, ttl_minutes: int) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = f"{code} is your Hakk sign-in code"
    message["From"] = formataddr((SMTP_FROM_NAME, SMTP_USER))
    message["To"] = to_email

    message.set_content(
        f"""Your Hakk sign-in code is {code}

It expires in {ttl_minutes} minutes and can be used once.

If you did not try to sign in to Hakk, you can ignore this email — no one can
access your account with this code alone.

Hakk prepares and tracks consumer complaints. It is not a law firm and does not
provide legal advice.
"""
    )
    message.add_alternative(
        f"""<!doctype html>
<html>
  <body style="margin:0;padding:32px 16px;background:#FAFAF8;
               font-family:Inter,-apple-system,Segoe UI,sans-serif;color:#24261F;">
    <div style="max-width:440px;margin:0 auto;background:#FFFFFF;border:1px solid #E9E8E0;
                border-radius:20px;padding:32px;">
      <p style="margin:0 0 4px;font-size:11px;letter-spacing:0.16em;text-transform:uppercase;
                color:#767B6C;font-weight:600;">Hakk</p>
      <h1 style="margin:0 0 20px;font-size:22px;font-weight:600;color:#24261F;">
        Your sign-in code
      </h1>
      <div style="background:#E6F1E7;border-radius:14px;padding:18px;text-align:center;
                  font-family:'JetBrains Mono',ui-monospace,monospace;font-size:32px;
                  letter-spacing:0.22em;font-weight:600;color:#345639;">{code}</div>
      <p style="margin:20px 0 0;font-size:14px;line-height:1.6;color:#494D42;">
        It expires in {ttl_minutes} minutes and can be used once.
      </p>
      <p style="margin:12px 0 0;font-size:14px;line-height:1.6;color:#767B6C;">
        If you did not try to sign in to Hakk, you can ignore this email — no one can
        access your account with this code alone.
      </p>
      <p style="margin:24px 0 0;padding-top:16px;border-top:1px solid #F1F0EA;
                font-size:12px;line-height:1.6;color:#A4A899;">
        Hakk prepares and tracks consumer complaints. It is not a law firm and does
        not provide legal advice.
      </p>
    </div>
  </body>
</html>""",
        subtype="html",
    )
    return message


def send_otp(to_email: str, code: str, ttl_minutes: int) -> tuple[bool, str]:
    """Returns (delivered, reason). `reason` is empty on success and carries the
    failure for the log and the console fallback message otherwise."""
    if not is_configured():
        return False, "SMTP is not configured"
    try:
        _send(_otp_message(to_email, code, ttl_minutes))
        log.info("OTP email sent to %s", mask(to_email))
        return True, ""
    except Exception as exc:
        # Deliberately broad: an auth failure, a DNS failure and a TLS failure
        # should all degrade to the console code rather than a 500 at sign-in.
        log.warning("OTP email to %s failed: %s", mask(to_email), exc)
        return False, str(exc)


# Severity -> (badge bg, badge text, accent bar) lifted straight from the
# pill-green / pill-clay / pill-rust classes in the frontend design system, so
# an emailed alert reads as the same product as the in-app toast it mirrors.
_ALERT_THEME = {
    "urgent": {"badge_bg": "#F8EAE6", "badge_text": "#823424", "accent": "#B4553F", "label": "Urgent"},
    "warn": {"badge_bg": "#F7EDE4", "badge_text": "#8C6122", "accent": "#C08A3E", "label": "Attention"},
    "info": {"badge_bg": "#E6F1E7", "badge_text": "#263F2A", "accent": "#6BAE70", "label": "Update"},
}


def _alert_message(
    to_email: str,
    *,
    title: str,
    body: str,
    severity: str,
    case_reference: str,
    case_url: str,
) -> EmailMessage:
    theme = _ALERT_THEME.get(severity, _ALERT_THEME["info"])

    message = EmailMessage()
    message["Subject"] = f"[{case_reference}] {title}"
    message["From"] = formataddr((SMTP_FROM_NAME, SMTP_USER))
    message["To"] = to_email

    message.set_content(
        f"""{title}

{body}

Case {case_reference}: {case_url}

Hakk prepares and tracks consumer complaints. It is not a law firm and does not
provide legal advice.
"""
    )
    message.add_alternative(
        f"""<!doctype html>
<html>
  <body style="margin:0;padding:32px 16px;background:#FAFAF8;
               font-family:Inter,-apple-system,Segoe UI,sans-serif;color:#24261F;">
    <div style="max-width:480px;margin:0 auto;background:#FFFFFF;border:1px solid #E9E8E0;
                border-radius:20px;overflow:hidden;">
      <div style="height:4px;background:{theme['accent']};"></div>
      <div style="padding:32px;">
        <p style="margin:0 0 16px;font-size:11px;letter-spacing:0.16em;text-transform:uppercase;
                  color:#767B6C;font-weight:600;">Hakk &middot; {case_reference}</p>
        <span style="display:inline-block;padding:4px 12px;border-radius:99px;font-size:11px;
                     font-weight:600;text-transform:uppercase;letter-spacing:0.06em;
                     background:{theme['badge_bg']};color:{theme['badge_text']};margin-bottom:16px;">
          {theme['label']}
        </span>
        <h1 style="margin:0 0 14px;font-size:20px;font-weight:600;color:#24261F;line-height:1.35;">
          {title}
        </h1>
        <p style="margin:0 0 24px;font-size:14px;line-height:1.65;color:#494D42;">
          {body}
        </p>
        <a href="{case_url}" style="display:inline-block;padding:11px 22px;border-radius:99px;
           background:#427047;color:#FAFAF8;text-decoration:none;font-size:14px;font-weight:600;">
          Open this case
        </a>
        <p style="margin:28px 0 0;padding-top:16px;border-top:1px solid #F1F0EA;
                  font-size:12px;line-height:1.6;color:#A4A899;">
          Hakk prepares and tracks consumer complaints. It is not a law firm and does
          not provide legal advice.
        </p>
      </div>
    </div>
  </body>
</html>""",
        subtype="html",
    )
    return message


def send_alert(
    to_email: str,
    *,
    title: str,
    body: str,
    severity: str,
    case_id: int,
    case_reference: str,
) -> tuple[bool, str]:
    """Emails a case notification — deadline reminders, lapses, auto-escalations,
    handoffs. Same best-effort contract as send_otp: never raises, always
    returns (delivered, reason). The in-app toast/banner is the notification of
    record regardless of whether this succeeds; email is a reach-you-elsewhere
    channel layered on top, not a replacement for it."""
    if not is_configured():
        return False, "SMTP is not configured"
    case_url = f"{FRONTEND_URL}/cases/{case_id}"
    try:
        _send(
            _alert_message(
                to_email,
                title=title,
                body=body or title,
                severity=severity,
                case_reference=case_reference,
                case_url=case_url,
            )
        )
        log.info("Alert email sent to %s: %s", mask(to_email), title)
        return True, ""
    except Exception as exc:
        log.warning("Alert email to %s failed (%s): %s", mask(to_email), title, exc)
        return False, str(exc)
