from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.core.rbac import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.services.audit_service import record_audit

router = APIRouter()


class SubAdminCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


@router.get("/home")
def admin_home(current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUB_ADMIN]))) -> dict[str, str]:
    return {"message": "Admin control center", "role": current_user.role}


@router.post("/sub-admins")
def create_sub_admin(
    payload: SubAdminCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN])),
) -> dict:
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=UserRole.SUB_ADMIN,
    )
    db.add(user)
    db.flush()
    record_audit(db, "SUB_ADMIN_CREATED", "User", actor=current_user, entity_id=str(user.id))
    db.commit()
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role}
