from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rbac import require_roles
from app.db.session import get_db
from app.models.complaint import Complaint
from app.models.enums import ActivationStatus, ComplaintStatus, ReplacementStatus, SimStatus, UserRole
from app.models.replacement import ReplacementRequest
from app.models.sim import SimRecord
from app.models.user import User
from app.realtime.manager import realtime_manager
from app.services.activation_service import create_activation_attempt, run_activation_workflow
from app.services.audit_service import record_audit

router = APIRouter()


class ComplaintStatusUpdate(BaseModel):
    status: ComplaintStatus


class ReplacementReview(BaseModel):
    approved: bool = True


def ensure_company_scope(sim: SimRecord, user: User) -> None:
    if user.role in {UserRole.SELLER, UserRole.COMPANY} and sim.company_id != user.company_id:
        raise HTTPException(status_code=403, detail="Cannot manage another company's lifecycle item")


@router.post("/complaints/{complaint_id}/status")
async def update_complaint_status(
    complaint_id: int,
    payload: ComplaintStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.SELLER, UserRole.COMPANY])),
) -> dict:
    complaint = db.get(Complaint, complaint_id)
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    sim = db.get(SimRecord, complaint.sim_record_id)
    ensure_company_scope(sim, current_user)
    complaint.status = payload.status
    if payload.status == ComplaintStatus.ASSIGNED and complaint.assigned_to_user_id is None and current_user.role == UserRole.SELLER:
        complaint.assigned_to_user_id = current_user.id
    record_audit(db, f"COMPLAINT_{payload.status}", "Complaint", actor=current_user, entity_id=str(complaint.id))
    db.commit()
    await realtime_manager.broadcast(
        f"user:{complaint.customer_id}:complaints",
        {
            "type": "COMPLAINT_UPDATED",
            "complaint": {
                "id": complaint.id,
                "customer_id": complaint.customer_id,
                "sim_record_id": complaint.sim_record_id,
                "title": complaint.title,
                "description": complaint.description,
                "status": complaint.status,
                "assigned_to_user_id": complaint.assigned_to_user_id,
                "created_at": complaint.created_at.isoformat() if complaint.created_at else None,
            },
        },
    )
    return {"id": complaint.id, "status": complaint.status}


@router.post("/replacements/{replacement_id}/verify")
def verify_replacement(
    replacement_id: int,
    payload: ReplacementReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.SELLER, UserRole.COMPANY])),
) -> dict:
    replacement = db.scalar(
        select(ReplacementRequest)
        .where(ReplacementRequest.id == replacement_id)
        .with_for_update()
    )
    if replacement is None:
        raise HTTPException(status_code=404, detail="Replacement request not found")
    old_sim = db.scalar(select(SimRecord).where(SimRecord.id == replacement.old_sim_record_id).with_for_update())
    if old_sim is None:
        raise HTTPException(status_code=404, detail="Original SIM not found")
    ensure_company_scope(old_sim, current_user)
    if replacement.status not in {ReplacementStatus.REQUESTED, ReplacementStatus.VERIFIED}:
        raise HTTPException(status_code=409, detail="Replacement request is already processed")
    if not payload.approved:
        replacement.status = ReplacementStatus.REJECTED
        replacement.verified_by_user_id = current_user.id
        replacement.verified_at = datetime.now(UTC)
        record_audit(db, "REPLACEMENT_REJECTED", "ReplacementRequest", actor=current_user, entity_id=str(replacement.id))
        db.commit()
        return {"id": replacement.id, "status": replacement.status}

    donor_sim = db.scalar(
        select(SimRecord)
        .where(
            SimRecord.company_id == old_sim.company_id,
            SimRecord.status == SimStatus.AVAILABLE,
            SimRecord.id != old_sim.id,
        )
        .order_by(SimRecord.created_at)
        .with_for_update(skip_locked=True)
    )
    if donor_sim is None:
        raise HTTPException(status_code=409, detail="No available replacement ICCID/IMSI inventory")

    old_iccid = old_sim.iccid
    old_imsi = old_sim.imsi
    new_iccid = donor_sim.iccid
    new_imsi = donor_sim.imsi
    donor_original_msisdn = donor_sim.msisdn

    donor_sim.msisdn = f"RET{donor_sim.id}"
    donor_sim.iccid = f"OLD{donor_sim.id}{old_iccid}"[:32]
    donor_sim.imsi = f"OLD{donor_sim.id}{old_imsi}"[:32]
    donor_sim.status = SimStatus.REPLACED
    db.flush()

    old_sim.iccid = new_iccid
    old_sim.imsi = new_imsi
    old_sim.status = SimStatus.KYC_VERIFIED

    replacement.new_sim_record_id = old_sim.id
    replacement.old_iccid = old_iccid
    replacement.old_imsi = old_imsi
    replacement.new_iccid = new_iccid
    replacement.new_imsi = new_imsi
    replacement.status = ReplacementStatus.VERIFIED
    replacement.verified_by_user_id = current_user.id
    replacement.verified_at = datetime.now(UTC)

    attempt = create_activation_attempt(db, old_sim)
    attempt = run_activation_workflow(db, old_sim, attempt)
    if attempt.status == ActivationStatus.COMPLETE:
        replacement.status = ReplacementStatus.COMPLETED
        replacement.completed_at = datetime.now(UTC)
    else:
        replacement.status = ReplacementStatus.APPROVED

    record_audit(
        db,
        "REPLACEMENT_VERIFIED",
        "ReplacementRequest",
        actor=current_user,
        entity_id=str(replacement.id),
        metadata={
            "retained_msisdn": old_sim.msisdn,
            "old_iccid": old_iccid,
            "new_iccid": new_iccid,
            "donor_msisdn": donor_original_msisdn,
            "activation_attempt_id": attempt.id,
        },
    )
    db.commit()
    return {
        "id": replacement.id,
        "status": replacement.status,
        "retained_msisdn": old_sim.msisdn,
        "old_iccid": old_iccid,
        "new_iccid": new_iccid,
        "activation_status": attempt.status,
    }
