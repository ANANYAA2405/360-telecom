from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.core.security import hash_password
from app.models.company import Company
from app.models.enums import UserRole
from app.models.plan import Plan
from app.models.sim import NumberSeries, SimRecord
from app.models.user import User


def generate_sims(company: Company, series: NumberSeries, count: int = 1000, start_offset: int = 0) -> list[SimRecord]:
    sims: list[SimRecord] = []
    prefix = series.prefix
    for offset in range(start_offset, start_offset + count):
        number_tail = str(offset).zfill(10 - len(prefix))
        sims.append(
            SimRecord(
                msisdn=f"{prefix}{number_tail}",
                iccid=f"8991{company.id:02d}{offset:014d}",
                imsi=f"404{company.id:02d}{offset:010d}",
                company_id=company.id,
                number_series_id=series.id,
            )
        )
    return sims


def get_or_create_company(db, name: str, code: str) -> Company:
    company = db.query(Company).filter(Company.code == code).one_or_none()
    if company is None:
        company = Company(name=name, code=code)
        db.add(company)
        db.flush()
    return company


def get_or_create_series(db, company: Company, prefix: str) -> NumberSeries:
    series = (
        db.query(NumberSeries)
        .filter(NumberSeries.company_id == company.id, NumberSeries.prefix == prefix)
        .one_or_none()
    )
    if series is None:
        series = NumberSeries(
            company_id=company.id,
            prefix=prefix,
            start_number=f"{prefix}00000",
            end_number=f"{prefix}00999",
        )
        db.add(series)
        db.flush()
    return series


def ensure_number_range(
    db,
    company: Company,
    prefix: str,
    start_number: str,
    end_number: str,
    count: int = 1000,
) -> NumberSeries:
    series = (
        db.query(NumberSeries)
        .filter(
            NumberSeries.company_id == company.id,
            NumberSeries.start_number == start_number,
            NumberSeries.end_number == end_number,
        )
        .one_or_none()
    )
    if series is not None:
        return series

    series = NumberSeries(
        company_id=company.id,
        prefix=prefix,
        start_number=start_number,
        end_number=end_number,
    )
    db.add(series)
    db.flush()

    start = int(start_number)
    for number in range(start, start + count):
        msisdn = str(number)
        exists = db.query(SimRecord.id).filter(SimRecord.msisdn == msisdn).one_or_none()
        if exists:
            continue
        iccid = f"8991{company.id:04d}{msisdn[-10:]}"
        imsi = f"404{company.id:04d}{msisdn[-10:]}"
        duplicate_identity = (
            db.query(SimRecord.id)
            .filter((SimRecord.iccid == iccid) | (SimRecord.imsi == imsi))
            .one_or_none()
        )
        if duplicate_identity:
            continue
        db.add(
            SimRecord(
                msisdn=msisdn,
                iccid=iccid,
                imsi=imsi,
                company_id=company.id,
                number_series_id=series.id,
            )
        )
    return series


def ensure_sim_inventory(db, company: Company, series: NumberSeries) -> None:
    existing_count = db.query(SimRecord).filter(SimRecord.company_id == company.id).count()
    if existing_count >= 1000:
        return
    db.add_all(generate_sims(company, series, count=1000 - existing_count, start_offset=existing_count))


def ensure_user(
    db,
    email: str,
    full_name: str,
    password: str,
    role: UserRole,
    company_id: int | None = None,
    company_role: str | None = None,
) -> User:
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is None:
        user = User(
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            role=role,
            company_id=company_id,
            company_role=company_role,
        )
        db.add(user)
        db.flush()
    elif company_id is not None and user.company_id != company_id:
        user.company_id = company_id
    if company_role is not None and user.company_role != company_role:
        user.company_role = company_role
    return user


def ensure_plan(db, company: Company, name: str, description: str, monthly_price: str) -> None:
    plan = (
        db.query(Plan)
        .filter(Plan.company_id == company.id, Plan.name == name)
        .one_or_none()
    )
    if plan is None:
        db.add(
            Plan(
                company_id=company.id,
                name=name,
                description=description,
                monthly_price=monthly_price,
            )
        )


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        legacy_companies = [
            ("Astra Telecom", "ASTRA", "90010"),
            ("Bharat Mobile", "BHARAT", "90020"),
            ("CoreWave Networks", "CORE", "90030"),
        ]
        for name, code, prefix in legacy_companies:
            company = get_or_create_company(db, name, code)
            series = get_or_create_series(db, company, prefix)
            ensure_sim_inventory(db, company, series)

        operator_ranges = [
            ("Airtel", "AIRTEL", "981", "9810000000", "9810000999"),
            ("Jio", "JIO", "701", "7011000000", "7011000999"),
            ("Vi", "VI", "887", "8879000000", "8879000999"),
            ("BSNL", "BSNL", "941", "9415000000", "9415000999"),
        ]
        operators = []
        for name, code, prefix, start_number, end_number in operator_ranges:
            company = get_or_create_company(db, name, code)
            ensure_number_range(db, company, prefix, start_number, end_number)
            ensure_plan(db, company, "Starter 199", "Voice, SMS and data starter bundle", "199.00")
            ensure_plan(db, company, "Unlimited 499", "Unlimited voice with high data allowance", "499.00")
            operators.append(company)

        ensure_user(db, "admin@telecom360.example.com", "Telecom360 Admin", "Admin@12345", UserRole.ADMIN)
        ensure_user(db, "customer@telecom360.example.com", "Demo Customer", "Password@12345", UserRole.CUSTOMER)
        ensure_user(
            db,
            "seller@telecom360.example.com",
            "Demo Seller",
            "Password@12345",
            UserRole.SELLER,
            operators[0].id,
        )
        ensure_user(
            db,
            "company@telecom360.example.com",
            "Demo Company Operator",
            "Password@12345",
            UserRole.COMPANY,
            operators[0].id,
            "COMPANY_ADMIN",
        )
        ensure_user(
            db,
            "company.plan@telecom360.example.com",
            "Demo Plan Manager",
            "Password@12345",
            UserRole.COMPANY,
            operators[0].id,
            "PLAN_MANAGER",
        )
        ensure_user(
            db,
            "company.inventory@telecom360.example.com",
            "Demo Inventory Manager",
            "Password@12345",
            UserRole.COMPANY,
            operators[0].id,
            "INVENTORY_MANAGER",
        )
        ensure_user(
            db,
            "company.analyst@telecom360.example.com",
            "Demo Company Analyst",
            "Password@12345",
            UserRole.COMPANY,
            operators[0].id,
            "ANALYST",
        )
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
