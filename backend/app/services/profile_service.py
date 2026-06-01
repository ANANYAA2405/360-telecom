from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.enums import ComplaintStatus, SimStatus, UserRole
from app.models.complaint import Complaint
from app.models.kyc import KycSubmission
from app.models.sim import SimRecord
from app.models.usage import Recharge, SimUsage
from app.models.user import User


def tier_from_value(total_recharge: Decimal | float | int, sim_count: int, usage_gb: int) -> str:
    value = float(total_recharge or 0)
    if value >= 5000 or sim_count >= 5:
        return "VVIP"
    if value >= 2500 or usage_gb >= 250:
        return "VIP"
    if value >= 1500 or usage_gb >= 120:
        return "PREMIUM"
    if value >= 800:
        return "GOLD"
    return "SILVER"


def customer_profile(db: Session, customer: User) -> dict:
    sims = list(db.scalars(select(SimRecord).where(SimRecord.reserved_by_user_id == customer.id)))
    sim_ids = [sim.id for sim in sims]
    usage_rows = list(db.scalars(select(SimUsage).where(SimUsage.sim_record_id.in_(sim_ids or [0]))))
    recharge_total = db.scalar(select(func.coalesce(func.sum(Recharge.amount), 0)).where(Recharge.customer_id == customer.id)) or 0
    complaint_count = db.scalar(select(func.count()).select_from(Complaint).where(Complaint.customer_id == customer.id)) or 0
    data_used = sum(row.data_used_gb or 0 for row in usage_rows)
    active_sims = sum(1 for sim in sims if sim.status in {SimStatus.ACTIVE, SimStatus.ACTIVE_IN_USE, SimStatus.ACTIVE_IDLE})
    segment = "ENTERPRISE" if len(sims) >= 3 or float(recharge_total) >= 2500 else "RETAIL"
    tier = tier_from_value(recharge_total, len(sims), data_used)
    risk_flags = []
    if len(sims) >= 5:
        risk_flags.append("MAX_SIM_LIMIT")
    if complaint_count >= 3:
        risk_flags.append("HIGH_COMPLAINT_VOLUME")
    churn_risk = "HIGH" if active_sims == 0 and len(sims) > 0 else "MEDIUM" if complaint_count >= 2 else "LOW"
    recommendation = "Offer unlimited/high-data retention pack" if tier in {"VIP", "VVIP", "PREMIUM"} else "Recommend Starter 199 or validity extension"
    return {
        "customer_id": customer.id,
        "segment": segment,
        "tier": tier,
        "sim_count": len(sims),
        "active_sims": active_sims,
        "total_recharge": recharge_total,
        "data_used_gb": data_used,
        "complaint_count": complaint_count,
        "risk_flags": risk_flags,
        "churn_risk": churn_risk,
        "recommendation": recommendation,
    }


def seller_profile(db: Session, seller: User) -> dict:
    active_count = db.scalar(select(func.count()).select_from(SimRecord).where(SimRecord.seller_id == seller.id, SimRecord.status == SimStatus.ACTIVE)) or 0
    kyc_count = db.scalar(select(func.count()).select_from(KycSubmission).where(KycSubmission.reviewed_by_user_id == seller.id)) or 0
    complaint_resolved = db.scalar(select(func.count()).select_from(Complaint).where(Complaint.assigned_to_user_id == seller.id, Complaint.status == ComplaintStatus.CLOSED)) or 0
    score = active_count * 4 + kyc_count * 2 + complaint_resolved * 3
    if score >= 100:
        profile = "STAR_PERFORMER"
    elif score >= 50:
        profile = "HIGH_PERFORMER"
    elif complaint_resolved > active_count:
        profile = "COMPLAINT_RESOLVER"
    elif kyc_count > active_count:
        profile = "KYC_SPECIALIST"
    else:
        profile = "GROWING_SELLER"
    return {
        "seller_id": seller.id,
        "seller_name": seller.full_name,
        "profile": profile,
        "score": score,
        "active_sims": active_count,
        "kyc_reviews": kyc_count,
        "complaints_closed": complaint_resolved,
        "prediction": "Likely to exceed target" if score >= 50 else "Needs more activation follow-up",
    }


def top_company_rankings(db: Session) -> list[dict]:
    rows = db.execute(
        select(Company.id, Company.name, func.count(SimRecord.id))
        .join(SimRecord, SimRecord.company_id == Company.id)
        .where(SimRecord.status.in_([SimStatus.ACTIVE, SimStatus.ACTIVE_IN_USE, SimStatus.ACTIVE_IDLE]))
        .group_by(Company.id, Company.name)
        .order_by(func.count(SimRecord.id).desc())
    ).all()
    return [{"company_id": row[0], "company_name": row[1], "active_sims": row[2]} for row in rows]


def lifecycle_label(sim: SimRecord, usage: SimUsage | None = None) -> str:
    if sim.status != SimStatus.ACTIVE:
        return sim.status
    if usage and usage.updated_at < datetime.now(UTC) - timedelta(days=120):
        return "DORMANT"
    if usage and usage.updated_at < datetime.now(UTC) - timedelta(days=30):
        return "ACTIVE_IDLE"
    return "ACTIVE_IN_USE" if usage else "ACTIVE_IDLE"
