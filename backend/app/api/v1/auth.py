from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rbac import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from pydantic import BaseModel, EmailStr

from app.api.v1.otp import create_otp, verify_otp_or_raise
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserRead
from app.services.audit_service import record_audit

router = APIRouter()


class LoginOtpVerifyRequest(BaseModel):
    email: EmailStr
    password: str
    otp_code: str


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if payload.role != UserRole.CUSTOMER and payload.company_id is None:
        raise HTTPException(status_code=400, detail="Non-customer roles require company assignment")
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        company_id=payload.company_id,
    )
    db.add(user)
    db.flush()
    record_audit(db, "USER_REGISTERED", "User", actor=user, entity_id=str(user.id))
    db.commit()
    return TokenResponse(access_token=create_access_token(str(user.id), user.role), role=user.role)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(str(user.id), user.role), role=user.role)


@router.post("/login/request-otp")
def login_request_otp(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    challenge = create_otp(db, user, "LOGIN", user.email)
    return {
        "status": "OTP_REQUIRED",
        "role": user.role,
        "expires_at": challenge.expires_at,
        "dev_otp": challenge.code,
        "message": "Dev OTP is returned for localhost demo only.",
    }


@router.post("/login/verify-otp", response_model=TokenResponse)
def login_verify_otp(payload: LoginOtpVerifyRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    verify_otp_or_raise(db, user, "LOGIN", payload.otp_code, user.email)
    db.commit()
    return TokenResponse(access_token=create_access_token(str(user.id), user.role), role=user.role)


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user
