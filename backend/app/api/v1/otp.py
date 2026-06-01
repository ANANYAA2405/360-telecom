import random
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rbac import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.otp import OtpChallenge
from app.models.sim import SimRecord
from app.models.user import User

router = APIRouter()


class OtpRequest(BaseModel):
    purpose: str
    reference_id: str | None = None


class OtpVerifyRequest(BaseModel):
    purpose: str
    code: str
    reference_id: str | None = None


def create_otp(db: Session, user: User, purpose: str, reference_id: str | None = None) -> OtpChallenge:
    code = f"{random.randint(0, 999999):06d}"
    challenge = OtpChallenge(
        user_id=user.id,
        purpose=purpose,
        reference_id=reference_id,
        code=code,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge


def verify_otp_or_raise(db: Session, user: User, purpose: str, code: str, reference_id: str | None = None) -> OtpChallenge:
    challenge = db.scalar(
        select(OtpChallenge)
        .where(
            OtpChallenge.user_id == user.id,
            OtpChallenge.purpose == purpose,
            OtpChallenge.reference_id == reference_id,
            OtpChallenge.consumed.is_(False),
        )
        .order_by(OtpChallenge.created_at.desc())
        .with_for_update()
    )
    if challenge is None or challenge.code != code:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    if challenge.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=400, detail="OTP expired")
    challenge.consumed = True
    return challenge


@router.post("/request")
def request_otp(
    payload: OtpRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.CUSTOMER, UserRole.SELLER, UserRole.COMPANY, UserRole.ADMIN])),
) -> dict:
    if payload.purpose in {"SIM_DEACTIVATION", "SIM_SUSPENSION"}:
        sim = db.get(SimRecord, int(payload.reference_id or 0))
        if sim is None or sim.reserved_by_user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Customer SIM not found")
    challenge = create_otp(db, current_user, payload.purpose, payload.reference_id)
    return {
        "status": "OTP_SENT",
        "expires_at": challenge.expires_at,
        "dev_otp": challenge.code,
        "message": "Dev OTP is returned for localhost demo only.",
    }


@router.post("/verify")
def verify_otp(
    payload: OtpVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.CUSTOMER, UserRole.SELLER, UserRole.COMPANY, UserRole.ADMIN])),
) -> dict:
    verify_otp_or_raise(db, current_user, payload.purpose, payload.code, payload.reference_id)
    db.commit()
    return {"status": "OTP_VERIFIED"}
