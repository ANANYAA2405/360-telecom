from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.rbac import require_roles
from app.db.session import get_db
from app.models.activation import ActivationAttempt
from app.models.enums import ActivationStatus, SimStatus, UserRole
from app.models.sim import SimRecord
from app.realtime.manager import realtime_manager
from app.models.user import User
from app.schemas.workflow import ActivationAttemptRead, ManualActivationCaseRead
from app.services.activation_serializer import activation_payload
from app.services.activation_service import prepare_failed_node_for_resubmission, run_activation_workflow
from app.services.audit_service import record_audit
from app.services.telecom_activation_service import record_manual_action, run_telecom_activation
from app.models.telecom_activation import ActivationMaster

router = APIRouter()


def manual_case_read(attempt: ActivationAttempt) -> ManualActivationCaseRead:
    sim = attempt.sim_record
    customer = sim.reserved_by
    return ManualActivationCaseRead(
        id=attempt.id,
        sim_record_id=attempt.sim_record_id,
        status=attempt.status,
        current_node=attempt.current_node,
        failed_node=attempt.failed_node,
        failure_reason=attempt.failure_reason,
        node_runs=attempt.node_runs,
        customer_id=sim.reserved_by_user_id,
        customer_name=customer.full_name if customer else None,
        customer_email=customer.email if customer else None,
        msisdn=sim.msisdn,
        iccid=sim.iccid,
        imsi=sim.imsi,
        company_id=sim.company_id,
    )


@router.get("/manual-inbox", response_model=list[ManualActivationCaseRead])
def manual_review_inbox(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.SELLER, UserRole.COMPANY])),
) -> list[ActivationAttempt]:
    query = (
        select(ActivationAttempt)
        .join(SimRecord)
        .options(
            selectinload(ActivationAttempt.node_runs),
            selectinload(ActivationAttempt.sim_record).selectinload(SimRecord.reserved_by),
        )
        .where(
            ActivationAttempt.status == ActivationStatus.MANUAL_REVIEW_REQUIRED,
            SimRecord.company_id == current_user.company_id,
            SimRecord.reserved_by_user_id.is_not(None),
        )
        .order_by(ActivationAttempt.created_at.desc())
    )
    return [manual_case_read(attempt) for attempt in db.scalars(query)]


@router.get("/{attempt_id}", response_model=ActivationAttemptRead)
def get_activation_attempt(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.CUSTOMER, UserRole.SELLER, UserRole.COMPANY, UserRole.ADMIN])),
) -> ActivationAttempt:
    attempt = db.scalar(
        select(ActivationAttempt)
        .options(selectinload(ActivationAttempt.node_runs), selectinload(ActivationAttempt.sim_record))
        .where(ActivationAttempt.id == attempt_id)
    )
    if attempt is None:
        raise HTTPException(status_code=404, detail="Activation attempt not found")
    if current_user.role == UserRole.CUSTOMER and attempt.sim_record.reserved_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot view another customer's activation")
    if current_user.role in {UserRole.SELLER, UserRole.COMPANY} and attempt.sim_record.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Cannot view another company's activation")
    return attempt


@router.post("/{attempt_id}/resume")
async def resume_activation_attempt(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.SELLER, UserRole.COMPANY])),
) -> dict[str, str]:
    attempt = db.scalar(
        select(ActivationAttempt)
        .options(selectinload(ActivationAttempt.node_runs), selectinload(ActivationAttempt.sim_record))
        .where(ActivationAttempt.id == attempt_id)
        .with_for_update()
    )
    if attempt is None:
        raise HTTPException(status_code=404, detail="Activation attempt not found")
    if attempt.sim_record.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Cannot resume another company's activation")
    if attempt.status != ActivationStatus.MANUAL_REVIEW_REQUIRED:
        raise HTTPException(status_code=409, detail="Activation attempt is not in manual review")
    resume_node = attempt.failed_node
    telecom_master = db.scalar(select(ActivationMaster).where(ActivationMaster.activation_attempt_id == attempt.id).with_for_update())
    telecom_resume_layer = telecom_master.last_failed_layer if telecom_master and telecom_master.last_failed_layer else None
    if telecom_master and telecom_resume_layer:
        record_manual_action(db, telecom_master, current_user, "RESUMED", f"Manual correction applied for {telecom_resume_layer}")
        attempt.status = ActivationStatus.RUNNING
        attempt.sim_record.status = SimStatus.ACTIVATING
        telecom_master = run_telecom_activation(db, attempt.sim_record, attempt, resume_from=telecom_resume_layer)
        if telecom_master.activation_status == "COMPLETE":
            attempt.status = ActivationStatus.COMPLETE
            attempt.failure_reason = None
            attempt.failed_node = None
            attempt.sim_record.status = SimStatus.ACTIVE
        else:
            attempt.status = ActivationStatus.MANUAL_REVIEW_REQUIRED
            attempt.failure_reason = telecom_master.fallout_reason
            attempt.sim_record.status = SimStatus.MANUAL_REVIEW_REQUIRED
        record_audit(db, "TELECOM_ACTIVATION_RESUMED", "ActivationMaster", actor=current_user, entity_id=str(telecom_master.activation_id))
        db.commit()
        await realtime_manager.broadcast(
            f"user:{attempt.sim_record.reserved_by_user_id}:activation",
            {"type": "ACTIVATION_UPDATED", "attempt": activation_payload(attempt), "sim_status": attempt.sim_record.status},
        )
        return {
            "status": attempt.status,
            "resumed_from": telecom_resume_layer,
            "current_node": str(attempt.current_node) if attempt.current_node else "",
            "failed_node": telecom_master.last_failed_layer or "",
            "failure_reason": telecom_master.fallout_reason or "",
        }
    prepare_failed_node_for_resubmission(attempt)
    attempt = run_activation_workflow(db, attempt.sim_record, attempt)
    db.commit()
    await realtime_manager.broadcast(
        f"user:{attempt.sim_record.reserved_by_user_id}:activation",
        {"type": "ACTIVATION_UPDATED", "attempt": activation_payload(attempt), "sim_status": attempt.sim_record.status},
    )
    return {
        "status": attempt.status,
        "resumed_from": str(resume_node) if resume_node else "",
        "current_node": str(attempt.current_node) if attempt.current_node else "",
        "failed_node": str(attempt.failed_node) if attempt.failed_node else "",
        "failure_reason": attempt.failure_reason or "",
    }
