from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rbac import require_roles
from app.db.session import get_db
from app.models.company import Company
from app.models.enums import UserRole
from app.models.plan import Plan
from app.models.user import User
from app.schemas.company import CompanyCreate, CompanyRead
from app.schemas.plan import PlanRead
from app.services.audit_service import record_audit

router = APIRouter()


@router.get("", response_model=list[CompanyRead])
def list_companies(db: Session = Depends(get_db)) -> list[Company]:
    return list(db.scalars(select(Company).where(Company.is_active.is_(True)).order_by(Company.name)))


@router.get("/{company_id}/plans", response_model=list[PlanRead])
def list_company_plans(company_id: int, db: Session = Depends(get_db)) -> list[Plan]:
    company = db.scalar(select(Company).where(Company.id == company_id, Company.is_active.is_(True)))
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return list(db.scalars(select(Plan).where(Plan.company_id == company_id, Plan.is_active.is_(True)).order_by(Plan.monthly_price)))


@router.post("", response_model=CompanyRead)
def create_company(
    payload: CompanyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN])),
) -> Company:
    code = payload.code.upper()
    existing = db.scalar(select(Company).where((Company.code == code) | (Company.name == payload.name)))
    if existing:
        raise HTTPException(status_code=409, detail="Company already exists")
    company = Company(name=payload.name, code=code)
    db.add(company)
    db.flush()
    record_audit(db, "COMPANY_CREATED", "Company", actor=current_user, entity_id=str(company.id))
    db.commit()
    db.refresh(company)
    return company
