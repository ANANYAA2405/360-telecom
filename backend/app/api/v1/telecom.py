from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rbac import require_roles
from app.db.session import get_db
from app.models.activation import ActivationAttempt
from app.models.enums import ActivationStatus, SimStatus, UserRole
from app.models.telecom_activation import ActivationMaster
from app.models.user import User
from app.services.audit_service import record_audit
from app.services.telecom_activation_service import (
    activation_details,
    find_activation_by_search,
    record_manual_action,
    run_telecom_activation,
    telecom_metrics,
)

router = APIRouter()


class SearchRequest(BaseModel):
    query: str


class ManualFixRequest(BaseModel):
    reason: str = "Manual correction completed"


def scoped_company_id(current_user: User) -> int | None:
    if current_user.role in {UserRole.ADMIN, UserRole.SUB_ADMIN}:
        return None
    if current_user.role in {UserRole.COMPANY, UserRole.SELLER}:
        return current_user.company_id
    return None


def authorize_master(master: ActivationMaster, current_user: User) -> None:
    if current_user.role == UserRole.CUSTOMER and master.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot view another customer's activation")
    if current_user.role in {UserRole.SELLER, UserRole.COMPANY} and master.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Cannot view another company's activation")


@router.get("/metrics")
def operations_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUB_ADMIN, UserRole.COMPANY, UserRole.SELLER])),
) -> dict:
    return telecom_metrics(db, scoped_company_id(current_user))


@router.post("/search")
def universal_search(
    payload: SearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUB_ADMIN, UserRole.COMPANY, UserRole.SELLER, UserRole.CUSTOMER])),
) -> dict:
    master = find_activation_by_search(db, payload.query.strip(), scoped_company_id(current_user))
    if master is None:
        raise HTTPException(status_code=404, detail="No telecom resource found")
    authorize_master(master, current_user)
    return activation_details(db, master)


@router.get("/activations/{activation_id}")
def read_activation(
    activation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUB_ADMIN, UserRole.COMPANY, UserRole.SELLER, UserRole.CUSTOMER])),
) -> dict:
    master = db.get(ActivationMaster, activation_id)
    if master is None:
        raise HTTPException(status_code=404, detail="Activation not found")
    authorize_master(master, current_user)
    return activation_details(db, master)


@router.get("/fallout")
def fallout_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUB_ADMIN, UserRole.COMPANY, UserRole.SELLER])),
) -> list[dict]:
    query = select(ActivationMaster).where(ActivationMaster.fallout_status.in_(["PENDING", "FAILED", "MANUAL_REVIEW"]))
    company_id = scoped_company_id(current_user)
    if company_id is not None:
        query = query.where(ActivationMaster.company_id == company_id)
    rows = list(db.scalars(query.order_by(ActivationMaster.updated_at.desc()).limit(100)))
    return [activation_details(db, row) for row in rows]


@router.post("/activations/{activation_id}/resume")
def resume_master_activation(
    activation_id: int,
    payload: ManualFixRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUB_ADMIN, UserRole.COMPANY, UserRole.SELLER])),
) -> dict:
    master = db.scalar(select(ActivationMaster).where(ActivationMaster.activation_id == activation_id).with_for_update())
    if master is None:
        raise HTTPException(status_code=404, detail="Activation not found")
    authorize_master(master, current_user)
    if not master.last_failed_layer:
        raise HTTPException(status_code=409, detail="Activation has no failed layer to resume")
    attempt = db.get(ActivationAttempt, master.activation_attempt_id) if master.activation_attempt_id else None
    if attempt is None:
        raise HTTPException(status_code=404, detail="Linked activation attempt not found")
    record_manual_action(db, master, current_user, "RESUMED", payload.reason)
    attempt.status = ActivationStatus.RUNNING
    attempt.sim_record.status = SimStatus.ACTIVATING
    run_telecom_activation(db, attempt.sim_record, attempt, resume_from=master.last_failed_layer)
    if master.activation_status == "COMPLETE":
        attempt.status = ActivationStatus.COMPLETE
        attempt.failure_reason = None
        attempt.sim_record.status = SimStatus.ACTIVE
    else:
        attempt.status = ActivationStatus.MANUAL_REVIEW_REQUIRED
        attempt.failure_reason = master.fallout_reason
        attempt.sim_record.status = SimStatus.MANUAL_REVIEW_REQUIRED
    record_audit(db, "TELECOM_MASTER_RESUMED", "ActivationMaster", actor=current_user, entity_id=str(master.activation_id))
    db.commit()
    return activation_details(db, master)
