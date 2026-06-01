from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rbac import require_roles
from app.core.security import hash_password
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.plan import Plan
from app.models.sim import NumberSeries
from app.models.user import User
from app.realtime.manager import realtime_manager
from app.schemas.plan import PlanCreate, PlanRead, PlanUpdate
from app.schemas.seller import CompanyUserCreate, CompanyUserRead, SellerCreate, SellerRead
from app.schemas.sim import (
    GeneratedInventoryResponse,
    GenerateSimInventoryRequest,
    InventorySummary,
    NumberSeriesRead,
    SimRead,
)
from app.services.audit_service import record_audit
from app.services.inventory_service import (
    generate_company_inventory,
    inventory_summary,
    resolve_company_id,
    validate_company,
)

router = APIRouter()

COMPANY_ADMIN = "COMPANY_ADMIN"
PLAN_MANAGER = "PLAN_MANAGER"
INVENTORY_MANAGER = "INVENTORY_MANAGER"
SELLER_MANAGER = "SELLER_MANAGER"
ANALYST = "ANALYST"
SUPPORT_MANAGER = "SUPPORT_MANAGER"
COMPANY_ROLES = {
    COMPANY_ADMIN,
    PLAN_MANAGER,
    INVENTORY_MANAGER,
    SELLER_MANAGER,
    ANALYST,
    SUPPORT_MANAGER,
}


def effective_company_role(user: User) -> str:
    return user.company_role or COMPANY_ADMIN


def require_company_permission(current_user: User, allowed_roles: set[str]) -> None:
    if current_user.role in {UserRole.ADMIN, UserRole.SUB_ADMIN}:
        return
    if current_user.role != UserRole.COMPANY:
        raise HTTPException(status_code=403, detail="Company permission required")
    company_role = effective_company_role(current_user)
    if company_role != COMPANY_ADMIN and company_role not in allowed_roles:
        raise HTTPException(status_code=403, detail=f"{company_role} cannot perform this action")


def validate_company_role(company_role: str) -> str:
    normalized = company_role.strip().upper()
    if normalized not in COMPANY_ROLES:
        raise HTTPException(status_code=400, detail=f"company_role must be one of {', '.join(sorted(COMPANY_ROLES))}")
    return normalized


@router.get("/summary", response_model=InventorySummary)
def read_inventory_summary(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUB_ADMIN, UserRole.COMPANY])),
) -> dict[str, int]:
    scoped_company_id = company_id if current_user.role in {UserRole.ADMIN, UserRole.SUB_ADMIN} else current_user.company_id
    return inventory_summary(db, scoped_company_id)


@router.post("/sellers", response_model=SellerRead)
def create_seller(
    payload: SellerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUB_ADMIN, UserRole.COMPANY])),
) -> User:
    require_company_permission(current_user, {SELLER_MANAGER})
    company_id = resolve_company_id(current_user, payload.company_id)
    validate_company(db, company_id)
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    seller = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=UserRole.SELLER,
        company_id=company_id,
    )
    db.add(seller)
    db.flush()
    record_audit(db, "SELLER_CREATED", "User", actor=current_user, entity_id=str(seller.id))
    db.commit()
    db.refresh(seller)
    return seller


@router.post("/company-users", response_model=CompanyUserRead)
def create_company_user(
    payload: CompanyUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUB_ADMIN, UserRole.COMPANY])),
) -> User:
    require_company_permission(current_user, {SELLER_MANAGER})
    company_id = resolve_company_id(current_user, payload.company_id)
    validate_company(db, company_id)
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    staff = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=UserRole.COMPANY,
        company_id=company_id,
        company_role=validate_company_role(payload.company_role),
    )
    db.add(staff)
    db.flush()
    record_audit(db, "COMPANY_USER_CREATED", "User", actor=current_user, entity_id=str(staff.id))
    db.commit()
    db.refresh(staff)
    return staff


@router.get("/company-users", response_model=list[CompanyUserRead])
def list_company_users(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUB_ADMIN, UserRole.COMPANY])),
) -> list[User]:
    require_company_permission(current_user, {SELLER_MANAGER})
    scoped_company_id = company_id if current_user.role in {UserRole.ADMIN, UserRole.SUB_ADMIN} else current_user.company_id
    query = select(User).where(User.role == UserRole.COMPANY).order_by(User.full_name)
    if scoped_company_id is not None:
        query = query.where(User.company_id == scoped_company_id)
    return list(db.scalars(query))


@router.get("/sellers", response_model=list[SellerRead])
def list_sellers(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUB_ADMIN, UserRole.COMPANY])),
) -> list[User]:
    require_company_permission(current_user, {SELLER_MANAGER, ANALYST})
    scoped_company_id = company_id if current_user.role in {UserRole.ADMIN, UserRole.SUB_ADMIN} else current_user.company_id
    query = select(User).where(User.role == UserRole.SELLER).order_by(User.full_name)
    if scoped_company_id is not None:
        query = query.where(User.company_id == scoped_company_id)
    return list(db.scalars(query))


@router.post("/plans", response_model=PlanRead)
async def create_plan(
    payload: PlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUB_ADMIN, UserRole.COMPANY])),
) -> Plan:
    require_company_permission(current_user, {PLAN_MANAGER})
    company_id = resolve_company_id(current_user, payload.company_id)
    validate_company(db, company_id)
    plan = Plan(
        company_id=company_id,
        name=payload.name,
        description=payload.description,
        monthly_price=payload.monthly_price,
        data_gb=payload.data_gb,
        voice_minutes=payload.voice_minutes,
        sms_count=payload.sms_count,
        validity_days=payload.validity_days,
    )
    db.add(plan)
    db.flush()
    record_audit(db, "PLAN_CREATED", "Plan", actor=current_user, entity_id=str(plan.id))
    db.commit()
    db.refresh(plan)
    await realtime_manager.broadcast(
        f"company:{company_id}:plans",
        {
            "type": "PLAN_CREATED",
            "plan": {
                "id": plan.id,
                "company_id": plan.company_id,
                "name": plan.name,
                "description": plan.description,
                "monthly_price": str(plan.monthly_price),
                "data_gb": plan.data_gb,
                "voice_minutes": plan.voice_minutes,
                "sms_count": plan.sms_count,
                "validity_days": plan.validity_days,
                "is_active": plan.is_active,
            },
        },
    )
    return plan


@router.get("/plans", response_model=list[PlanRead])
def list_plans(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUB_ADMIN, UserRole.COMPANY, UserRole.SELLER])),
) -> list[Plan]:
    if current_user.role == UserRole.COMPANY:
        require_company_permission(current_user, {PLAN_MANAGER, ANALYST})
    scoped_company_id = company_id if current_user.role in {UserRole.ADMIN, UserRole.SUB_ADMIN} else current_user.company_id
    query = select(Plan).order_by(Plan.name)
    if scoped_company_id is not None:
        query = query.where(Plan.company_id == scoped_company_id)
    return list(db.scalars(query))


@router.patch("/plans/{plan_id}", response_model=PlanRead)
async def update_plan(
    plan_id: int,
    payload: PlanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUB_ADMIN, UserRole.COMPANY])),
) -> Plan:
    require_company_permission(current_user, {PLAN_MANAGER})
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    if current_user.role == UserRole.COMPANY and plan.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(plan, field, value)
    record_audit(db, "PLAN_UPDATED", "Plan", actor=current_user, entity_id=str(plan.id))
    db.commit()
    db.refresh(plan)
    await realtime_manager.broadcast(
        f"company:{plan.company_id}:plans",
        {
            "type": "PLAN_UPDATED",
            "plan": {
                "id": plan.id,
                "company_id": plan.company_id,
                "name": plan.name,
                "description": plan.description,
                "monthly_price": str(plan.monthly_price),
                "data_gb": plan.data_gb,
                "voice_minutes": plan.voice_minutes,
                "sms_count": plan.sms_count,
                "validity_days": plan.validity_days,
                "is_active": plan.is_active,
            },
        },
    )
    return plan


@router.delete("/plans/{plan_id}", response_model=PlanRead)
async def deactivate_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUB_ADMIN, UserRole.COMPANY])),
) -> Plan:
    require_company_permission(current_user, {PLAN_MANAGER})
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    if current_user.role == UserRole.COMPANY and plan.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan.is_active = False
    record_audit(db, "PLAN_DEACTIVATED", "Plan", actor=current_user, entity_id=str(plan.id))
    db.commit()
    db.refresh(plan)
    await realtime_manager.broadcast(f"company:{plan.company_id}:plans", {"type": "PLAN_DEACTIVATED", "plan_id": plan.id})
    return plan


@router.post("/inventory/generate", response_model=GeneratedInventoryResponse)
def generate_inventory(
    payload: GenerateSimInventoryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUB_ADMIN, UserRole.COMPANY])),
) -> GeneratedInventoryResponse:
    require_company_permission(current_user, {INVENTORY_MANAGER})
    company_id = resolve_company_id(current_user, payload.company_id)
    series, sims = generate_company_inventory(
        db,
        company_id=company_id,
        start_msisdn=payload.start_msisdn,
        end_msisdn=payload.end_msisdn,
        count=payload.count,
        seller_id=payload.seller_id,
    )
    record_audit(
        db,
        "SIM_INVENTORY_GENERATED",
        "NumberSeries",
        actor=current_user,
        entity_id=str(series.id),
        metadata={"company_id": company_id, "created": len(sims)},
    )
    db.commit()
    return GeneratedInventoryResponse(
        company_id=company_id,
        series_id=series.id,
        start_msisdn=series.start_number,
        end_msisdn=series.end_number,
        created=len(sims),
    )


@router.get("/series", response_model=list[NumberSeriesRead])
def list_number_series(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUB_ADMIN, UserRole.COMPANY])),
) -> list[NumberSeries]:
    require_company_permission(current_user, {INVENTORY_MANAGER, ANALYST})
    scoped_company_id = company_id if current_user.role in {UserRole.ADMIN, UserRole.SUB_ADMIN} else current_user.company_id
    query = select(NumberSeries).order_by(NumberSeries.created_at.desc())
    if scoped_company_id is not None:
        query = query.where(NumberSeries.company_id == scoped_company_id)
    return list(db.scalars(query))


@router.get("/inventory", response_model=list[SimRead])
def list_inventory(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUB_ADMIN, UserRole.COMPANY])),
) -> list:
    require_company_permission(current_user, {INVENTORY_MANAGER, ANALYST})
    scoped_company_id = company_id if current_user.role in {UserRole.ADMIN, UserRole.SUB_ADMIN} else current_user.company_id
    from app.models.sim import SimRecord

    query = select(SimRecord).order_by(SimRecord.created_at.desc()).limit(200)
    if scoped_company_id is not None:
        query = query.where(SimRecord.company_id == scoped_company_id)
    return list(db.scalars(query))
