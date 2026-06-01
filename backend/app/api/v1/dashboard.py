from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.rbac import require_roles
from app.db.session import get_db
from app.models.activation import ActivationAttempt, ActivationNodeRun
from app.models.audit import AuditLog
from app.models.company import Company
from app.models.complaint import Complaint
from app.models.enums import ActivationStatus, ComplaintStatus, KycStatus, ReplacementStatus, SimStatus, UserRole, WorkflowNodeStatus
from app.models.kyc import KycSubmission
from app.models.replacement import ReplacementRequest
from app.models.sim import NumberSeries, SimRecord
from app.models.usage import Recharge, SimUsage
from app.models.user import User
from app.services.audit_service import record_audit
from app.services.profile_service import customer_profile, lifecycle_label, seller_profile, top_company_rankings

router = APIRouter()


class ComplaintCreate(BaseModel):
    sim_record_id: int
    title: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=5)


class ReplacementCreate(BaseModel):
    old_sim_record_id: int
    reason: str = Field(min_length=5)


def sim_card(sim: SimRecord) -> dict:
    usage = getattr(sim, "_profile_usage", None)
    return {
        "id": sim.id,
        "msisdn": sim.msisdn,
        "iccid": sim.iccid,
        "imsi": sim.imsi,
        "company_id": sim.company_id,
        "company_name": sim.company.name if sim.company else None,
        "plan_id": sim.plan_id,
        "plan_name": sim.plan.name if sim.plan else None,
        "status": sim.status,
        "lifecycle_label": lifecycle_label(sim, usage),
        "reserved_until": sim.reserved_until,
    }


def activation_card(attempt: ActivationAttempt) -> dict:
    return {
        "id": attempt.id,
        "sim_record_id": attempt.sim_record_id,
        "msisdn": attempt.sim_record.msisdn if attempt.sim_record else None,
        "status": attempt.status,
        "current_node": attempt.current_node,
        "failed_node": attempt.failed_node,
        "failure_reason": attempt.failure_reason,
        "nodes": [
            {
                "node": run.node,
                "status": run.status,
                "sequence": run.sequence,
                "error_message": run.error_message,
                "request_payload": run.request_payload,
                "response_payload": run.response_payload,
            }
            for run in sorted(attempt.node_runs, key=lambda item: item.sequence)
        ],
    }


def complaint_card(complaint: Complaint) -> dict:
    return {
        "id": complaint.id,
        "customer_id": complaint.customer_id,
        "sim_record_id": complaint.sim_record_id,
        "title": complaint.title,
        "description": complaint.description,
        "status": complaint.status,
        "assigned_to_user_id": complaint.assigned_to_user_id,
        "created_at": complaint.created_at,
    }


def replacement_card(request: ReplacementRequest) -> dict:
    return {
        "id": request.id,
        "customer_id": request.customer_id,
        "old_sim_record_id": request.old_sim_record_id,
        "new_sim_record_id": request.new_sim_record_id,
        "old_iccid": request.old_iccid,
        "old_imsi": request.old_imsi,
        "new_iccid": request.new_iccid,
        "new_imsi": request.new_imsi,
        "reason": request.reason,
        "status": request.status,
        "verified_by_user_id": request.verified_by_user_id,
        "created_at": request.created_at,
        "completed_at": request.completed_at,
    }


def user_card(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "company_id": user.company_id,
        "company_name": user.company.name if user.company else None,
        "company_role": user.company_role,
    }


def company_permissions(company_role: str | None) -> dict[str, bool]:
    role = company_role or "COMPANY_ADMIN"
    is_admin = role == "COMPANY_ADMIN"
    return {
        "can_manage_plans": is_admin or role == "PLAN_MANAGER",
        "can_manage_inventory": is_admin or role == "INVENTORY_MANAGER",
        "can_manage_sellers": is_admin or role == "SELLER_MANAGER",
        "can_view_analytics": is_admin or role == "ANALYST",
        "can_handle_support": is_admin or role == "SUPPORT_MANAGER",
        "can_view_customer_profiles": is_admin or role == "ANALYST",
        "can_view_seller_profiles": is_admin or role in {"SELLER_MANAGER", "ANALYST"},
        "can_view_operations": is_admin or role in {"INVENTORY_MANAGER", "ANALYST", "SUPPORT_MANAGER"},
    }


@router.get("/customer")
def customer_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.CUSTOMER])),
) -> dict:
    sims = list(
        db.scalars(
            select(SimRecord)
            .options(selectinload(SimRecord.company), selectinload(SimRecord.plan))
            .where(SimRecord.reserved_by_user_id == current_user.id)
            .order_by(SimRecord.updated_at.desc())
        )
    )
    kyc = list(
        db.scalars(
            select(KycSubmission)
            .where(KycSubmission.customer_id == current_user.id)
            .order_by(KycSubmission.created_at.desc())
        )
    )
    attempts = list(
        db.scalars(
            select(ActivationAttempt)
            .join(SimRecord)
            .options(selectinload(ActivationAttempt.node_runs), selectinload(ActivationAttempt.sim_record))
            .where(SimRecord.reserved_by_user_id == current_user.id)
            .order_by(ActivationAttempt.created_at.desc())
        )
    )
    complaints = list(db.scalars(select(Complaint).where(Complaint.customer_id == current_user.id).order_by(Complaint.created_at.desc())))
    replacements = list(
        db.scalars(select(ReplacementRequest).where(ReplacementRequest.customer_id == current_user.id).order_by(ReplacementRequest.created_at.desc()))
    )
    selected_sim = sims[0] if sims else None
    profile = customer_profile(db, current_user)
    return {
        "selected_operator": selected_sim.company.name if selected_sim and selected_sim.company else None,
        "selected_number": selected_sim.msisdn if selected_sim else None,
        "selected_sim": sim_card(selected_sim) if selected_sim else None,
        "kyc_status": kyc[0].status if kyc else None,
        "sim_status": selected_sim.status if selected_sim else None,
        "activation_timeline": [activation_card(attempt) for attempt in attempts],
        "complaints": [complaint_card(item) for item in complaints],
        "replacements": [replacement_card(item) for item in replacements],
        "profile": profile,
    }


@router.post("/complaints")
def create_complaint(
    payload: ComplaintCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.CUSTOMER])),
) -> dict:
    sim = db.get(SimRecord, payload.sim_record_id)
    if sim is None or sim.reserved_by_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Customer SIM not found")
    complaint = Complaint(
        customer_id=current_user.id,
        sim_record_id=sim.id,
        title=payload.title,
        description=payload.description,
        status=ComplaintStatus.ASSIGNED if sim.seller_id else ComplaintStatus.OPEN,
        assigned_to_user_id=sim.seller_id,
    )
    db.add(complaint)
    db.flush()
    record_audit(db, "COMPLAINT_CREATED", "Complaint", actor=current_user, entity_id=str(complaint.id))
    db.commit()
    return complaint_card(complaint)


@router.post("/replacements")
def create_replacement(
    payload: ReplacementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.CUSTOMER])),
) -> dict:
    sim = db.get(SimRecord, payload.old_sim_record_id)
    if sim is None or sim.reserved_by_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Customer SIM not found")
    replacement = ReplacementRequest(
        customer_id=current_user.id,
        old_sim_record_id=sim.id,
        old_iccid=sim.iccid,
        old_imsi=sim.imsi,
        reason=payload.reason,
        status=ReplacementStatus.REQUESTED,
    )
    db.add(replacement)
    db.flush()
    record_audit(db, "REPLACEMENT_REQUESTED", "ReplacementRequest", actor=current_user, entity_id=str(replacement.id))
    db.commit()
    return replacement_card(replacement)


@router.get("/seller")
def seller_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.SELLER])),
) -> dict:
    assigned_stock = list(
        db.scalars(select(SimRecord).options(selectinload(SimRecord.company)).where(SimRecord.seller_id == current_user.id).limit(100))
    )
    pending_kyc = list(
        db.scalars(
            select(KycSubmission)
            .join(SimRecord)
            .where(SimRecord.company_id == current_user.company_id, KycSubmission.status == KycStatus.PENDING)
            .order_by(KycSubmission.created_at)
        )
    )
    failed_attempts = list(
        db.scalars(
            select(ActivationAttempt)
            .join(SimRecord)
            .options(selectinload(ActivationAttempt.node_runs), selectinload(ActivationAttempt.sim_record).selectinload(SimRecord.reserved_by))
            .where(
                SimRecord.company_id == current_user.company_id,
                ActivationAttempt.status == ActivationStatus.MANUAL_REVIEW_REQUIRED,
                SimRecord.reserved_by_user_id.is_not(None),
            )
        )
    )
    complaints = list(
        db.scalars(
            select(Complaint)
            .join(SimRecord, Complaint.sim_record_id == SimRecord.id)
            .where(SimRecord.company_id == current_user.company_id)
            .order_by(Complaint.created_at.desc())
        )
    )
    replacements = list(
        db.scalars(
            select(ReplacementRequest)
            .join(SimRecord, ReplacementRequest.old_sim_record_id == SimRecord.id)
            .where(SimRecord.company_id == current_user.company_id)
            .order_by(ReplacementRequest.created_at.desc())
        )
    )
    customer_ids = {item.customer_id for item in pending_kyc if item.customer_id}
    customer_profiles = [
        {**user_card(customer), "profile": customer_profile(db, customer)}
        for customer in db.scalars(select(User).where(User.id.in_(customer_ids or {0})))
    ]
    return {
        "assigned_sim_stock": [sim_card(sim) for sim in assigned_stock],
        "pending_kyc_count": len(pending_kyc),
        "failed_activation_inbox": [activation_card(attempt) for attempt in failed_attempts],
        "complaints_assigned": [complaint_card(item) for item in complaints],
        "replacement_requests": [replacement_card(item) for item in replacements],
        "profile": seller_profile(db, current_user),
        "customer_usage_watchlist": customer_profiles,
    }


@router.get("/company")
def company_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.COMPANY])),
) -> dict:
    company_id = current_user.company_id
    company_role = current_user.company_role or "COMPANY_ADMIN"
    permissions = company_permissions(current_user.company_role)
    status_counts = dict(
        db.execute(
            select(SimRecord.status, func.count()).where(SimRecord.company_id == company_id).group_by(SimRecord.status)
        ).all()
    )
    failed_attempts = list(
        db.scalars(
            select(ActivationAttempt)
            .join(SimRecord)
            .options(selectinload(ActivationAttempt.node_runs), selectinload(ActivationAttempt.sim_record))
            .where(
                SimRecord.company_id == company_id,
                ActivationAttempt.status == ActivationStatus.MANUAL_REVIEW_REQUIRED,
                SimRecord.reserved_by_user_id.is_not(None),
            )
        )
    )
    failed_runs = list(
        db.scalars(
            select(ActivationNodeRun)
            .join(ActivationAttempt)
            .join(SimRecord)
            .where(SimRecord.company_id == company_id, ActivationNodeRun.status == WorkflowNodeStatus.FAILED)
        )
    )
    seller_rows = db.execute(
        select(User.id, User.full_name, SimRecord.status, func.count())
        .join(SimRecord, SimRecord.seller_id == User.id)
        .where(User.company_id == company_id, User.role == UserRole.SELLER)
        .group_by(User.id, User.full_name, SimRecord.status)
    ).all()
    seller_performance: dict[int, dict] = {}
    for seller_id, full_name, status, count in seller_rows:
        seller_performance.setdefault(seller_id, {"seller_id": seller_id, "seller_name": full_name, "status_counts": {}})
        seller_performance[seller_id]["status_counts"][status] = count
    complaints = list(
        db.scalars(
            select(Complaint)
            .join(SimRecord, Complaint.sim_record_id == SimRecord.id)
            .where(SimRecord.company_id == company_id)
            .order_by(Complaint.created_at.desc())
        )
    )
    replacements = list(
        db.scalars(
            select(ReplacementRequest)
            .join(SimRecord, ReplacementRequest.old_sim_record_id == SimRecord.id)
            .where(SimRecord.company_id == company_id)
            .order_by(ReplacementRequest.created_at.desc())
        )
    )
    sellers = list(db.scalars(select(User).where(User.company_id == company_id, User.role == UserRole.SELLER)))
    seller_profiles = [seller_profile(db, seller) for seller in sellers]
    best_seller = max(seller_profiles, key=lambda item: item["score"], default=None)
    company_customers = list(
        db.scalars(
            select(User)
            .join(SimRecord, SimRecord.reserved_by_user_id == User.id)
            .where(SimRecord.company_id == company_id, User.role == UserRole.CUSTOMER)
            .distinct()
        )
    )
    customer_profiles = [customer_profile(db, customer) for customer in company_customers]
    segment_counts = dict(Counter(item["segment"] for item in customer_profiles))
    tier_counts = dict(Counter(item["tier"] for item in customer_profiles))
    return {
        "company_role": company_role,
        "permissions": permissions,
        "total_sims_issued": status_counts.get(SimStatus.ACTIVE, 0),
        "available_sims": status_counts.get(SimStatus.AVAILABLE, 0),
        "reserved_sims": status_counts.get(SimStatus.RESERVED, 0),
        "active_sims": status_counts.get(SimStatus.ACTIVE, 0),
        "failed_activations": [activation_card(attempt) for attempt in failed_attempts] if permissions["can_handle_support"] or permissions["can_view_analytics"] else [],
        "node_wise_failure_analytics": dict(Counter(run.node for run in failed_runs)) if permissions["can_view_operations"] or permissions["can_view_analytics"] else {},
        "seller_wise_performance": list(seller_performance.values()) if permissions["can_view_seller_profiles"] else [],
        "complaints": [complaint_card(item) for item in complaints] if permissions["can_handle_support"] or permissions["can_view_analytics"] else [],
        "replacements": [replacement_card(item) for item in replacements] if permissions["can_handle_support"] or permissions["can_view_analytics"] else [],
        "best_seller": best_seller if permissions["can_view_seller_profiles"] else None,
        "seller_profiles": seller_profiles if permissions["can_view_seller_profiles"] else [],
        "customer_segment_counts": segment_counts if permissions["can_view_customer_profiles"] else {},
        "customer_tier_counts": tier_counts if permissions["can_view_customer_profiles"] else {},
    }


@router.get("/admin")
def admin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUB_ADMIN])),
) -> dict:
    companies = list(db.scalars(select(Company).order_by(Company.name)))
    sellers = list(db.scalars(select(User).options(selectinload(User.company)).where(User.role == UserRole.SELLER).order_by(User.full_name)))
    customers = list(db.scalars(select(User).where(User.role == UserRole.CUSTOMER).order_by(User.created_at.desc()).limit(200)))
    inventory = list(
        db.scalars(
            select(SimRecord)
            .options(selectinload(SimRecord.company))
            .order_by(SimRecord.created_at.desc())
            .limit(300)
        )
    )
    activation_logs = list(
        db.scalars(
            select(ActivationAttempt)
            .options(selectinload(ActivationAttempt.node_runs), selectinload(ActivationAttempt.sim_record))
            .order_by(ActivationAttempt.created_at.desc())
            .limit(100)
        )
    )
    audit_logs = list(db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100)))
    customer_profiles = [{**user_card(item), "profile": customer_profile(db, item)} for item in customers]
    sorted_customers = sorted(
        customer_profiles,
        key=lambda item: (float(item["profile"]["total_recharge"] or 0), item["profile"]["sim_count"]),
        reverse=True,
    )
    company_rankings = top_company_rankings(db)
    seller_profiles = [seller_profile(db, item) for item in sellers]
    top_seller = max(seller_profiles, key=lambda item: item["score"], default=None)
    total_revenue = db.scalar(select(func.coalesce(func.sum(Recharge.amount), 0))) or 0
    return {
        "all_companies": [{"id": item.id, "name": item.name, "code": item.code, "is_active": item.is_active} for item in companies],
        "all_sellers": [user_card(item) for item in sellers],
        "all_customers": customer_profiles,
        "sorted_customers": sorted_customers,
        "all_sim_inventory": [sim_card(item) for item in inventory],
        "all_activation_logs": [activation_card(item) for item in activation_logs],
        "audit_logs": [
            {
                "id": item.id,
                "actor_user_id": item.actor_user_id,
                "action": item.action,
                "entity_type": item.entity_type,
                "entity_id": item.entity_id,
                "metadata_json": item.metadata_json,
                "created_at": item.created_at,
            }
            for item in audit_logs
        ],
        "metrics": {
            "total_revenue": total_revenue,
            "top_company": company_rankings[0] if company_rankings else None,
            "top_seller": top_seller,
            "company_rankings": company_rankings,
            "seller_profiles": seller_profiles,
            "profile_tier_counts": dict(Counter(item["profile"]["tier"] for item in customer_profiles)),
            "customer_segment_counts": dict(Counter(item["profile"]["segment"] for item in customer_profiles)),
        },
    }
