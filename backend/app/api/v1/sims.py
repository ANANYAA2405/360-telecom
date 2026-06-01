from fastapi import APIRouter, Depends, HTTPException
from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.rbac import require_roles
from app.core.security import verify_password
from app.db.session import get_db
from app.models.enums import SimStatus, UserRole
from app.models.sim import SimRecord
from app.models.user import User
from app.realtime.manager import realtime_manager
from pydantic import BaseModel

from app.api.v1.otp import verify_otp_or_raise
from app.schemas.sim import ReserveNumberRequest, ReservedSimRead, SimRead
from app.services.reservation_service import get_redis, release_expired_reservations, reserve_number

router = APIRouter()


class SecureSimActionRequest(BaseModel):
    password: str
    otp_code: str | None = None


@router.get("/available", response_model=list[SimRead])
async def list_available_numbers(
    company_id: int,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> list[SimRecord]:
    expired = release_expired_reservations(db, redis)
    if expired:
        db.commit()
        for sim in expired:
            await realtime_manager.broadcast(
                f"company:{sim.company_id}:numbers",
                {
                    "type": "NUMBER_RELEASED",
                    "sim_record_id": sim.id,
                    "msisdn": sim.msisdn,
                    "status": SimStatus.AVAILABLE,
                },
            )
    query = (
        select(SimRecord)
        .options(selectinload(SimRecord.company))
        .where(SimRecord.company_id == company_id, SimRecord.status == SimStatus.AVAILABLE)
        .order_by(SimRecord.msisdn)
        .limit(100)
    )
    return list(db.scalars(query))


@router.post("/reserve", response_model=ReservedSimRead)
async def reserve_available_number(
    payload: ReserveNumberRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(require_roles([UserRole.CUSTOMER])),
) -> SimRecord:
    sim = reserve_number(db, redis, current_user, payload.sim_record_id, payload.plan_id)
    db.commit()
    sim = db.scalar(
        select(SimRecord)
        .options(selectinload(SimRecord.company))
        .where(SimRecord.id == payload.sim_record_id)
    )
    await realtime_manager.broadcast(
        f"company:{sim.company_id}:numbers",
        {
            "type": "NUMBER_RESERVED",
            "sim_record_id": sim.id,
            "msisdn": sim.msisdn,
            "status": SimStatus.RESERVED,
            "reserved_until": sim.reserved_until.isoformat() if sim.reserved_until else None,
        },
    )
    return sim


def get_customer_sim_for_action(db: Session, sim_record_id: int, current_user: User) -> SimRecord:
    sim = db.scalar(
        select(SimRecord)
        .options(selectinload(SimRecord.company))
        .where(SimRecord.id == sim_record_id, SimRecord.reserved_by_user_id == current_user.id)
        .with_for_update()
    )
    if sim is None:
        raise HTTPException(status_code=404, detail="Customer SIM not found")
    return sim


@router.post("/{sim_record_id}/deactivate", response_model=ReservedSimRead)
def deactivate_sim(
    sim_record_id: int,
    payload: SecureSimActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.CUSTOMER])),
) -> SimRecord:
    if not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Password confirmation failed")
    verify_otp_or_raise(db, current_user, "SIM_DEACTIVATION", payload.otp_code or "", str(sim_record_id))
    sim = get_customer_sim_for_action(db, sim_record_id, current_user)
    sim.status = SimStatus.DEACTIVATED
    db.commit()
    db.refresh(sim)
    return sim


@router.post("/{sim_record_id}/suspend", response_model=ReservedSimRead)
def suspend_sim(
    sim_record_id: int,
    payload: SecureSimActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.CUSTOMER])),
) -> SimRecord:
    if not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Password confirmation failed")
    verify_otp_or_raise(db, current_user, "SIM_SUSPENSION", payload.otp_code or "", str(sim_record_id))
    sim = get_customer_sim_for_action(db, sim_record_id, current_user)
    sim.status = SimStatus.SUSPENDED
    db.commit()
    db.refresh(sim)
    return sim


@router.post("/{sim_record_id}/reactivate", response_model=ReservedSimRead)
def reactivate_sim(
    sim_record_id: int,
    payload: SecureSimActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.CUSTOMER])),
) -> SimRecord:
    if not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Password confirmation failed")
    sim = get_customer_sim_for_action(db, sim_record_id, current_user)
    if sim.status not in {SimStatus.SUSPENDED, SimStatus.ACTIVE_IDLE, SimStatus.DORMANT}:
        raise HTTPException(status_code=409, detail="Only suspended/idle/dormant SIMs can be reactivated")
    sim.status = SimStatus.ACTIVE
    db.commit()
    db.refresh(sim)
    return sim
