"""Phone + email signup, emailed OTP, and a fallback password for returning users.

Two delivery modes, decided by whether SMTP is configured:

- **email** — the code is mailed to the address given at sign-up and must be
  entered exactly. Single use, expires in OTP_TTL_MINUTES, and burned after
  MAX_ATTEMPTS wrong guesses.
- **console** — no SMTP configured (or the send failed), so the code is printed
  to the server console. When SMTP was never configured at all, any well-formed
  6-digit code is accepted so the product still demos with no mail account.

The response says which mode applied, so the UI can tell the user where to look
rather than leaving them staring at an empty inbox.
"""

from __future__ import annotations

import datetime as dt
import hmac
import random
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import OtpCode, User, utcnow
from ..security import create_token, current_user, hash_password, verify_password
from ..services import mailer

router = APIRouter(prefix="/api/auth", tags=["auth"])

OTP_TTL_MINUTES = 10
MAX_ATTEMPTS = 5
PHONE_RE = re.compile(r"^(?:\+91)?[6-9]\d{9}$")


class StartRequest(BaseModel):
    phone: str
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=120)

    @field_validator("phone")
    @classmethod
    def _normalise_phone(cls, v: str) -> str:
        cleaned = re.sub(r"[\s\-()]", "", v)
        if not PHONE_RE.match(cleaned):
            raise ValueError("Enter a valid 10-digit Indian mobile number")
        return cleaned[-10:]


class VerifyRequest(BaseModel):
    phone: str
    code: str

    @field_validator("phone")
    @classmethod
    def _normalise_phone(cls, v: str) -> str:
        return re.sub(r"[\s\-()]", "", v)[-10:]

    @field_validator("code")
    @classmethod
    def _check_code(cls, v: str) -> str:
        v = v.strip()
        if not (len(v) == 6 and v.isdigit()):
            raise ValueError("Enter the 6-digit code")
        return v


class PasswordRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class PasswordLoginRequest(BaseModel):
    phone: str
    password: str

    @field_validator("phone")
    @classmethod
    def _normalise_phone(cls, v: str) -> str:
        return re.sub(r"[\s\-()]", "", v)[-10:]


def _user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "phone": user.phone,
        "email": user.email,
        "full_name": user.full_name,
        "has_password": bool(user.password_hash),
    }


@router.post("/start")
def start(payload: StartRequest, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.phone == payload.phone))
    returning = user is not None

    if user is None:
        user = User(phone=payload.phone, email=payload.email, full_name=payload.full_name)
        db.add(user)
        db.flush()
    else:
        user.email = payload.email
        if payload.full_name:
            user.full_name = payload.full_name

    # Outstanding codes for this user are void the moment a new one is issued —
    # otherwise every code ever sent stays live until its own TTL runs out.
    for stale in db.scalars(
        select(OtpCode).where(OtpCode.user_id == user.id, OtpCode.consumed.is_(False))
    ).all():
        stale.consumed = True

    code = f"{random.randint(0, 999999):06d}"
    db.add(
        OtpCode(
            user_id=user.id,
            code=code,
            expires_at=utcnow() + dt.timedelta(minutes=OTP_TTL_MINUTES),
        )
    )
    db.commit()

    delivered, failure = mailer.send_otp(user.email, code, OTP_TTL_MINUTES)

    if delivered:
        return {
            "sent": True,
            "delivery": "email",
            "sent_to": mailer.mask(user.email),
            "returning_user": returning,
            "has_password": bool(user.password_hash),
            "hint": f"We emailed a 6-digit code to {mailer.mask(user.email)}.",
            "expires_in_minutes": OTP_TTL_MINUTES,
        }

    # Console fallback. `strict` distinguishes "SMTP is off, this is a demo, take
    # any code" from "SMTP is on but this send failed, so the real code still
    # applies and it's sitting in the console".
    strict = mailer.is_configured()
    print("\n" + "=" * 58)
    print(f"  HAKK OTP  ->  {user.phone}   CODE: {code}")
    print(f"  (email delivery unavailable: {failure})" if strict else "  (mock delivery: any 6-digit code is accepted)")
    print("=" * 58 + "\n", flush=True)

    return {
        "sent": True,
        "delivery": "console",
        "sent_to": None,
        "returning_user": returning,
        "has_password": bool(user.password_hash),
        "hint": (
            "We couldn't reach the mail server. Your code is printed in the backend console."
            if strict
            else "Email isn't configured, so any 6-digit code works. The generated code is "
            "in the backend console."
        ),
        "expires_in_minutes": OTP_TTL_MINUTES,
    }


@router.post("/verify")
def verify(payload: VerifyRequest, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.phone == payload.phone))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Start the sign-in flow first")

    otp = db.scalar(
        select(OtpCode)
        .where(OtpCode.user_id == user.id, OtpCode.consumed.is_(False))
        .order_by(OtpCode.id.desc())
    )

    if not mailer.is_configured():
        # No mail account wired up: any well-formed 6-digit code is accepted so
        # the product still demos. The outstanding row is still burned so the
        # flow behaves like the real thing.
        if otp is not None:
            otp.consumed = True
    else:
        if otp is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "That code has already been used. Request a new one."
            )

        expires = otp.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=dt.timezone.utc)
        if utcnow() > expires:
            otp.consumed = True
            db.commit()
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "That code has expired. Request a new one.")

        if not hmac.compare_digest(otp.code, payload.code):
            otp.attempts += 1
            remaining = MAX_ATTEMPTS - otp.attempts
            if remaining <= 0:
                otp.consumed = True
                db.commit()
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "Too many incorrect attempts. Request a new code.",
                )
            db.commit()
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Incorrect code. {remaining} attempt{'s' if remaining != 1 else ''} left.",
            )

        otp.consumed = True

    user.last_login_at = utcnow()
    db.commit()

    return {
        "token": create_token(user),
        "user": _user_payload(user),
        "needs_password_setup": not user.password_hash,
    }


@router.post("/password")
def set_password(
    payload: PasswordRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    user.password_hash = hash_password(payload.password)
    db.commit()
    return {"ok": True, "user": _user_payload(user)}


@router.post("/login")
def login(payload: PasswordLoginRequest, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.phone == payload.phone))
    if user is None or not user.password_hash:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "No password set for this number — sign in with an OTP instead",
        )
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect password")

    user.last_login_at = utcnow()
    db.commit()
    return {"token": create_token(user), "user": _user_payload(user), "needs_password_setup": False}


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return _user_payload(user)
