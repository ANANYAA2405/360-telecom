from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import SimStatus
from app.models.plan import Plan
from app.models.sim import SimRecord
from app.models.user import User
from app.services.audit_service import record_audit


def get_redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def reserve_number(db: Session, redis: Redis, customer: User, sim_record_id: int, plan_id: int) -> SimRecord:
    lock_key = f"sim-lock:{sim_record_id}"
    locked = redis.set(lock_key, str(customer.id), nx=True, ex=settings.number_lock_ttl_seconds)
    if not locked:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Number is being reserved")

    sim = db.scalar(select(SimRecord).where(SimRecord.id == sim_record_id).with_for_update())
    if sim is None:
        redis.delete(lock_key)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SIM record not found")
    if sim.status != SimStatus.AVAILABLE:
        redis.delete(lock_key)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Number is not available")
    plan = db.scalar(select(Plan).where(Plan.id == plan_id, Plan.company_id == sim.company_id, Plan.is_active.is_(True)))
    if plan is None:
        redis.delete(lock_key)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active plan not found for selected operator")
    active_count = db.scalar(
        select(func.count())
        .select_from(SimRecord)
        .where(
            SimRecord.reserved_by_user_id == customer.id,
            SimRecord.status.in_([
                SimStatus.RESERVED,
                SimStatus.KYC_PENDING,
                SimStatus.KYC_VERIFIED,
                SimStatus.ACTIVATING,
                SimStatus.ACTIVE,
                SimStatus.MANUAL_REVIEW_REQUIRED,
            ]),
        )
    )
    if active_count and active_count >= 5:
        redis.delete(lock_key)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Maximum 5 SIMs allowed. Deactivate one SIM before issuing another.")

    sim.status = SimStatus.RESERVED
    sim.reserved_by_user_id = customer.id
    sim.plan_id = plan.id
    sim.reserved_until = datetime.now(UTC) + timedelta(seconds=settings.number_lock_ttl_seconds)
    record_audit(db, "SIM_RESERVED", "SimRecord", actor=customer, entity_id=str(sim.id))
    return sim


def release_expired_reservations(db: Session, redis: Redis | None = None) -> list[SimRecord]:
    now = datetime.now(UTC)
    expired_sims = list(
        db.scalars(
            select(SimRecord)
            .where(
                SimRecord.status == SimStatus.RESERVED,
                SimRecord.reserved_until.is_not(None),
                SimRecord.reserved_until <= now,
            )
            .with_for_update(skip_locked=True)
        )
    )
    for sim in expired_sims:
        sim.status = SimStatus.AVAILABLE
        sim.reserved_by_user_id = None
        sim.reserved_until = None
        if redis is not None:
            redis.delete(f"sim-lock:{sim.id}")
        record_audit(
            db,
            "SIM_RESERVATION_EXPIRED",
            "SimRecord",
            entity_id=str(sim.id),
            metadata={"msisdn": sim.msisdn, "company_id": sim.company_id},
        )
    return expired_sims
