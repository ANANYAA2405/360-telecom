from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.enums import SimStatus, UserRole
from app.models.plan import Plan
from app.models.sim import NumberSeries, SimRecord
from app.models.user import User


def resolve_company_id(current_user: User, requested_company_id: int | None) -> int:
    if current_user.role in {UserRole.ADMIN, UserRole.SUB_ADMIN}:
        if requested_company_id is None:
            raise HTTPException(status_code=400, detail="company_id is required")
        return requested_company_id
    if current_user.role == UserRole.COMPANY and current_user.company_id is not None:
        if requested_company_id is not None and requested_company_id != current_user.company_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot manage another company")
        return current_user.company_id
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Company assignment required")


def validate_company(db: Session, company_id: int) -> Company:
    company = db.get(Company, company_id)
    if company is None or not company.is_active:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def validate_seller(db: Session, seller_id: int | None, company_id: int) -> User | None:
    if seller_id is None:
        return None
    seller = db.get(User, seller_id)
    if seller is None or seller.role != UserRole.SELLER or seller.company_id != company_id:
        raise HTTPException(status_code=400, detail="seller_id must belong to the selected company")
    return seller


def generate_company_inventory(
    db: Session,
    company_id: int,
    start_msisdn: str,
    count: int = 1000,
    end_msisdn: str | None = None,
    seller_id: int | None = None,
) -> tuple[NumberSeries, list[SimRecord]]:
    validate_company(db, company_id)
    validate_seller(db, seller_id, company_id)

    start_number = int(start_msisdn)
    expected_end = start_number + count - 1
    if end_msisdn is not None and int(end_msisdn) != expected_end:
        raise HTTPException(status_code=400, detail="end_msisdn must match start_msisdn plus count minus one")
    computed_end = str(expected_end).zfill(10)
    prefix = start_msisdn[:5]

    existing_msisdn = db.scalar(
        select(SimRecord.msisdn).where(
            SimRecord.msisdn >= start_msisdn,
            SimRecord.msisdn <= computed_end,
        )
    )
    if existing_msisdn:
        raise HTTPException(status_code=409, detail=f"MSISDN range overlaps existing number {existing_msisdn}")

    series = NumberSeries(
        company_id=company_id,
        prefix=prefix,
        start_number=start_msisdn,
        end_number=computed_end,
    )
    db.add(series)
    db.flush()

    sims: list[SimRecord] = []
    for offset in range(count):
        msisdn = str(start_number + offset).zfill(10)
        sims.append(
            SimRecord(
                msisdn=msisdn,
                iccid=f"8991{company_id:04d}{msisdn}",
                imsi=f"404{company_id:04d}{msisdn[-9:]}",
                company_id=company_id,
                seller_id=seller_id,
                number_series_id=series.id,
                status=SimStatus.AVAILABLE,
            )
        )
    db.add_all(sims)
    return series, sims


def inventory_summary(db: Session, company_id: int | None = None) -> dict[str, int]:
    user_filters = []
    plan_filters = []
    sim_filters = []
    series_filters = []
    if company_id is not None:
        user_filters.append(User.company_id == company_id)
        plan_filters.append(Plan.company_id == company_id)
        sim_filters.append(SimRecord.company_id == company_id)
        series_filters.append(NumberSeries.company_id == company_id)

    return {
        "companies": db.scalar(select(func.count()).select_from(Company).where(Company.is_active.is_(True))) or 0,
        "sellers": db.scalar(select(func.count()).select_from(User).where(User.role == UserRole.SELLER, *user_filters)) or 0,
        "plans": db.scalar(select(func.count()).select_from(Plan).where(*plan_filters)) or 0,
        "sim_records": db.scalar(select(func.count()).select_from(SimRecord).where(*sim_filters)) or 0,
        "available_sims": db.scalar(
            select(func.count()).select_from(SimRecord).where(SimRecord.status == SimStatus.AVAILABLE, *sim_filters)
        ) or 0,
        "series": db.scalar(select(func.count()).select_from(NumberSeries).where(*series_filters)) or 0,
    }
