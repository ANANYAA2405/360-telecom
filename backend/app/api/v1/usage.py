from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.rbac import require_roles
from app.db.session import get_db
from app.models.enums import SimStatus, UserRole
from app.models.plan import Plan
from app.models.sim import SimRecord
from app.models.usage import Recharge, SellerTarget, SimUsage
from app.models.user import User
from app.services.audit_service import record_audit

router = APIRouter()


def require_company_role(current_user: User, allowed_roles: set[str]) -> None:
    if current_user.role != UserRole.COMPANY:
        return
    company_role = current_user.company_role or "COMPANY_ADMIN"
    if company_role != "COMPANY_ADMIN" and company_role not in allowed_roles:
        raise HTTPException(status_code=403, detail=f"{company_role} cannot perform this action")


class RechargeRequest(BaseModel):
    sim_record_id: int
    plan_id: int


class TargetRequest(BaseModel):
    seller_id: int
    month: str
    activation_target: int = 0
    recharge_target: int = 0
    kyc_target: int = 0


def usage_card(sim: SimRecord, usage: SimUsage | None = None) -> dict:
    plan = sim.plan
    usage = usage or SimUsage(sim_record_id=sim.id)
    data_used = usage.data_used_gb or 0
    voice_used = usage.voice_used_minutes or 0
    sms_used = usage.sms_used_count or 0
    return {
        "sim_record_id": sim.id,
        "msisdn": sim.msisdn,
        "plan": {
            "id": plan.id,
            "name": plan.name,
            "data_gb": plan.data_gb,
            "voice_minutes": plan.voice_minutes,
            "sms_count": plan.sms_count,
            "validity_days": plan.validity_days,
        } if plan else None,
        "data_used_gb": data_used,
        "data_left_gb": max((plan.data_gb if plan else 0) - data_used, 0),
        "voice_used_minutes": voice_used,
        "voice_left_minutes": max((plan.voice_minutes if plan else 0) - voice_used, 0),
        "sms_used_count": sms_used,
        "sms_left_count": max((plan.sms_count if plan else 0) - sms_used, 0),
        "valid_until": usage.valid_until,
    }


@router.get("/mine")
def my_usage(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.CUSTOMER])),
) -> list[dict]:
    sims = list(
        db.scalars(
            select(SimRecord)
            .options(selectinload(SimRecord.plan))
            .where(SimRecord.reserved_by_user_id == current_user.id, SimRecord.status.in_([SimStatus.ACTIVE, SimStatus.KYC_PENDING, SimStatus.RESERVED]))
            .order_by(SimRecord.updated_at.desc())
        )
    )
    usage_by_sim = {
        item.sim_record_id: item
        for item in db.scalars(select(SimUsage).where(SimUsage.sim_record_id.in_([sim.id for sim in sims] or [0])))
    }
    return [usage_card(sim, usage_by_sim.get(sim.id)) for sim in sims]


@router.post("/recharge")
def recharge(
    payload: RechargeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.CUSTOMER])),
) -> dict:
    sim = db.scalar(
        select(SimRecord)
        .options(selectinload(SimRecord.plan))
        .where(SimRecord.id == payload.sim_record_id, SimRecord.reserved_by_user_id == current_user.id)
        .with_for_update()
    )
    if sim is None:
        raise HTTPException(status_code=404, detail="Customer SIM not found")
    plan = db.scalar(select(Plan).where(Plan.id == payload.plan_id, Plan.company_id == sim.company_id, Plan.is_active.is_(True)))
    if plan is None:
        raise HTTPException(status_code=404, detail="Active plan not found")
    sim.plan_id = plan.id
    usage = db.scalar(select(SimUsage).where(SimUsage.sim_record_id == sim.id).with_for_update())
    if usage is None:
        usage = SimUsage(sim_record_id=sim.id)
        db.add(usage)
    usage.data_used_gb = 0
    usage.voice_used_minutes = 0
    usage.sms_used_count = 0
    usage.valid_until = datetime.now(UTC) + timedelta(days=plan.validity_days)
    recharge_row = Recharge(customer_id=current_user.id, sim_record_id=sim.id, plan_id=plan.id, amount=plan.monthly_price)
    db.add(recharge_row)
    record_audit(db, "RECHARGE_SUCCESS", "Recharge", actor=current_user, metadata={"sim_record_id": sim.id, "plan_id": plan.id})
    db.commit()
    return {"status": "SUCCESS", "usage": usage_card(sim, usage)}


@router.get("/recharges")
def recharge_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.CUSTOMER])),
) -> list[dict]:
    rows = list(
        db.scalars(
            select(Recharge)
            .options(selectinload(Recharge.plan), selectinload(Recharge.sim_record))
            .where(Recharge.customer_id == current_user.id)
            .order_by(Recharge.created_at.desc())
        )
    )
    return [
        {
            "id": row.id,
            "msisdn": row.sim_record.msisdn if row.sim_record else None,
            "plan_name": row.plan.name if row.plan else None,
            "amount": row.amount,
            "status": row.status,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.post("/targets")
def set_target(
    payload: TargetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.COMPANY])),
) -> dict:
    require_company_role(current_user, {"SELLER_MANAGER"})
    seller = db.get(User, payload.seller_id)
    if seller is None or seller.company_id != current_user.company_id or seller.role != UserRole.SELLER:
        raise HTTPException(status_code=404, detail="Seller not found")
    target = db.scalar(select(SellerTarget).where(SellerTarget.seller_id == seller.id, SellerTarget.month == payload.month))
    if target is None:
        target = SellerTarget(seller_id=seller.id, company_id=current_user.company_id, month=payload.month)
        db.add(target)
    target.activation_target = payload.activation_target
    target.recharge_target = payload.recharge_target
    target.kyc_target = payload.kyc_target
    db.commit()
    return {"status": "TARGET_SET", "seller_id": seller.id, "month": payload.month}


@router.get("/targets")
def target_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.SELLER, UserRole.COMPANY])),
) -> list[dict]:
    require_company_role(current_user, {"SELLER_MANAGER", "ANALYST"})
    company_id = current_user.company_id
    query = select(SellerTarget).options(selectinload(SellerTarget.seller)).where(SellerTarget.company_id == company_id)
    if current_user.role == UserRole.SELLER:
        query = query.where(SellerTarget.seller_id == current_user.id)
    targets = list(db.scalars(query.order_by(SellerTarget.month.desc())))
    result = []
    for target in targets:
        active_count = db.scalar(
            select(func.count()).select_from(SimRecord).where(SimRecord.seller_id == target.seller_id, SimRecord.status == SimStatus.ACTIVE)
        ) or 0
        result.append(
            {
                "id": target.id,
                "seller_id": target.seller_id,
                "seller_name": target.seller.full_name if target.seller else None,
                "month": target.month,
                "activation_target": target.activation_target,
                "activation_achieved": active_count,
                "activation_remaining": max(target.activation_target - active_count, 0),
            }
        )
    return result
