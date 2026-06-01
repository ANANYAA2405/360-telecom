from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.rbac import require_roles
from app.db.session import get_db
from app.models.enums import KycStatus, SimStatus, UserRole
from app.models.kyc import KycSubmission
from app.models.sim import SimRecord
from app.models.user import User
from app.realtime.manager import realtime_manager
from app.schemas.kyc import KycReviewRequest, KycSubmissionRead, KycSubmitRequest
from app.services.activation_serializer import activation_payload
from app.services.activation_service import run_activation_workflow
from app.services.audit_service import record_audit

router = APIRouter()


def kyc_read(submission: KycSubmission) -> KycSubmissionRead:
    return KycSubmissionRead(
        id=submission.id,
        customer_id=submission.customer_id,
        sim_record_id=submission.sim_record_id,
        full_name=submission.full_name,
        date_of_birth=submission.date_of_birth,
        document_type=submission.document_type,
        document_number=submission.document_number,
        address=submission.address,
        document_upload_placeholder=submission.document_upload_placeholder,
        selfie_placeholder=submission.selfie_placeholder,
        status=submission.status,
        reviewed_by_user_id=submission.reviewed_by_user_id,
        rejection_reason=submission.rejection_reason,
        correction_reason=submission.correction_reason,
        created_at=submission.created_at,
        reviewed_at=submission.reviewed_at,
        msisdn=submission.sim_record.msisdn if submission.sim_record else None,
        company_name=submission.sim_record.company.name if submission.sim_record and submission.sim_record.company else None,
        customer_email=submission.customer.email if submission.customer else None,
    )


@router.post("/submit", response_model=KycSubmissionRead)
async def submit_kyc(
    payload: KycSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.CUSTOMER])),
) -> KycSubmissionRead:
    sim = db.scalar(
        select(SimRecord)
        .options(selectinload(SimRecord.company))
        .where(SimRecord.id == payload.sim_record_id)
        .with_for_update()
    )
    if sim is None or sim.reserved_by_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Reserved SIM not found")
    if sim.status not in {SimStatus.RESERVED, SimStatus.KYC_REJECTED, SimStatus.KYC_CORRECTION_REQUESTED}:
        raise HTTPException(status_code=409, detail="SIM is not ready for KYC")
    existing = db.scalar(select(KycSubmission).where(KycSubmission.sim_record_id == sim.id))
    if existing and existing.status not in {KycStatus.REJECTED, KycStatus.CORRECTION_REQUESTED}:
        raise HTTPException(status_code=409, detail="KYC is already submitted")
    submission = existing or KycSubmission(customer_id=current_user.id, sim_record_id=sim.id)
    submission.full_name = payload.full_name
    submission.date_of_birth = payload.date_of_birth
    submission.document_type = payload.document_type
    submission.document_number = payload.document_number
    submission.address = payload.address
    submission.document_upload_placeholder = payload.document_upload_placeholder
    submission.selfie_placeholder = payload.selfie_placeholder
    submission.status = KycStatus.PENDING
    submission.reviewed_by_user_id = None
    submission.reviewed_at = None
    submission.rejection_reason = None
    submission.correction_reason = None
    if existing is None:
        db.add(submission)
    sim.status = SimStatus.KYC_PENDING
    db.flush()
    record_audit(db, "KYC_SUBMITTED", "KycSubmission", actor=current_user, entity_id=str(submission.id))
    db.commit()
    submission = db.scalar(
        select(KycSubmission)
        .options(selectinload(KycSubmission.sim_record).selectinload(SimRecord.company), selectinload(KycSubmission.customer))
        .where(KycSubmission.id == submission.id)
    )
    await realtime_manager.broadcast(
        f"user:{current_user.id}:kyc",
        {"type": "KYC_SUBMITTED", "kyc_id": submission.id, "status": submission.status, "sim_status": sim.status},
    )
    await realtime_manager.broadcast(
        f"company:{sim.company_id}:kyc",
        {"type": "KYC_PENDING", "kyc_id": submission.id, "msisdn": sim.msisdn},
    )
    return kyc_read(submission)


@router.get("/mine", response_model=list[KycSubmissionRead])
def list_my_kyc(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.CUSTOMER])),
) -> list[KycSubmissionRead]:
    submissions = list(
        db.scalars(
            select(KycSubmission)
            .options(selectinload(KycSubmission.sim_record).selectinload(SimRecord.company), selectinload(KycSubmission.customer))
            .where(KycSubmission.customer_id == current_user.id)
            .order_by(KycSubmission.created_at.desc())
        )
    )
    return [kyc_read(submission) for submission in submissions]


@router.get("/pending", response_model=list[KycSubmissionRead])
def list_pending_kyc(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.SELLER, UserRole.COMPANY])),
) -> list[KycSubmissionRead]:
    query = (
        select(KycSubmission)
        .options(selectinload(KycSubmission.sim_record).selectinload(SimRecord.company), selectinload(KycSubmission.customer))
        .where(KycSubmission.status == KycStatus.PENDING)
        .order_by(KycSubmission.created_at)
    )
    if current_user.role in {UserRole.SELLER, UserRole.COMPANY}:
        query = query.join(SimRecord).where(SimRecord.company_id == current_user.company_id)
    submissions = list(db.scalars(query))
    return [kyc_read(submission) for submission in submissions]


@router.post("/{kyc_id}/review")
async def review_kyc(
    kyc_id: int,
    payload: KycReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.SELLER, UserRole.COMPANY])),
) -> dict[str, str]:
    submission = db.scalar(
        select(KycSubmission)
        .options(selectinload(KycSubmission.sim_record), selectinload(KycSubmission.customer))
        .where(KycSubmission.id == kyc_id)
        .with_for_update()
    )
    if submission is None:
        raise HTTPException(status_code=404, detail="KYC submission not found")
    if payload.status == KycStatus.PENDING:
        raise HTTPException(status_code=400, detail="Review status must approve, reject, or request correction")
    if submission.sim_record.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Cannot review another company KYC")
    submission.status = payload.status
    submission.reviewed_by_user_id = current_user.id
    submission.reviewed_at = datetime.now(UTC)
    submission.rejection_reason = payload.rejection_reason
    submission.correction_reason = payload.correction_reason
    if payload.status == KycStatus.APPROVED:
        submission.sim_record.status = SimStatus.KYC_VERIFIED
        attempt = run_activation_workflow(db, submission.sim_record)
    elif payload.status == KycStatus.REJECTED:
        submission.sim_record.status = SimStatus.KYC_REJECTED
        attempt = None
    else:
        submission.sim_record.status = SimStatus.KYC_CORRECTION_REQUESTED
        attempt = None
    record_audit(db, f"KYC_{payload.status}", "KycSubmission", actor=current_user, entity_id=str(kyc_id))
    db.commit()
    await realtime_manager.broadcast(
        f"user:{submission.customer_id}:kyc",
        {
            "type": "KYC_REVIEWED",
            "kyc_id": submission.id,
            "status": submission.status,
            "sim_status": submission.sim_record.status,
            "activation_attempt_id": attempt.id if attempt else None,
            "activation_status": attempt.status if attempt else None,
            "failed_node": attempt.failed_node if attempt else None,
            "failure_reason": attempt.failure_reason if attempt else None,
            "rejection_reason": submission.rejection_reason,
            "correction_reason": submission.correction_reason,
        },
    )
    if attempt:
        await realtime_manager.broadcast(
            f"user:{submission.customer_id}:activation",
            {"type": "ACTIVATION_UPDATED", "attempt": activation_payload(attempt), "sim_status": submission.sim_record.status},
        )
    await realtime_manager.broadcast(
        f"company:{submission.sim_record.company_id}:kyc",
        {"type": "KYC_REVIEWED", "kyc_id": submission.id, "status": submission.status},
    )
    return {"status": payload.status}
