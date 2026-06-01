from sqlalchemy import inspect, text

from app.db.base import Base
from app.db.session import engine


def main() -> None:
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    with engine.begin() as connection:
        if "company_role" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN company_role VARCHAR(64) NULL"))

    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("sim_records")}
    with engine.begin() as connection:
        if "seller_id" not in columns:
            connection.execute(text("ALTER TABLE sim_records ADD COLUMN seller_id INTEGER NULL"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_sim_records_seller_id ON sim_records (seller_id)"))
        if "plan_id" not in columns:
            connection.execute(text("ALTER TABLE sim_records ADD COLUMN plan_id INTEGER NULL"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_sim_records_plan_id ON sim_records (plan_id)"))
        enum_values = [row[0] for row in connection.execute(text("SELECT unnest(enum_range(NULL::simstatus))::text"))]
        for value in [
            "KYC_VERIFIED",
            "KYC_CORRECTION_REQUESTED",
            "MANUAL_REVIEW_REQUIRED",
            "ACTIVE_IN_USE",
            "ACTIVE_IDLE",
            "DORMANT",
            "DEACTIVATION_REQUESTED",
            "DEACTIVATED",
            "EXPIRED",
            "PORT_OUT_REQUESTED",
            "PORTED_OUT",
        ]:
            if value not in enum_values:
                connection.execute(text(f"ALTER TYPE simstatus ADD VALUE IF NOT EXISTS '{value}'"))
        role_values = [row[0] for row in connection.execute(text("SELECT unnest(enum_range(NULL::userrole))::text"))]
        if "SUB_ADMIN" not in role_values:
            connection.execute(text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'SUB_ADMIN'"))
        activation_status_values = [row[0] for row in connection.execute(text("SELECT unnest(enum_range(NULL::activationstatus))::text"))]
        if "MANUAL_REVIEW_REQUIRED" not in activation_status_values:
            connection.execute(text("ALTER TYPE activationstatus ADD VALUE IF NOT EXISTS 'MANUAL_REVIEW_REQUIRED'"))

    inspector = inspect(engine)
    kyc_columns = {column["name"] for column in inspector.get_columns("kyc_submissions")}
    with engine.begin() as connection:
        kyc_status_values = [row[0] for row in connection.execute(text("SELECT unnest(enum_range(NULL::kycstatus))::text"))]
        if "CORRECTION_REQUESTED" not in kyc_status_values:
            connection.execute(text("ALTER TYPE kycstatus ADD VALUE IF NOT EXISTS 'CORRECTION_REQUESTED'"))
        if "full_name" not in kyc_columns:
            connection.execute(text("ALTER TABLE kyc_submissions ADD COLUMN full_name VARCHAR(160) NOT NULL DEFAULT ''"))
        if "date_of_birth" not in kyc_columns:
            connection.execute(text("ALTER TABLE kyc_submissions ADD COLUMN date_of_birth DATE NULL"))
        if "document_upload_placeholder" not in kyc_columns:
            connection.execute(text("ALTER TABLE kyc_submissions ADD COLUMN document_upload_placeholder TEXT NULL"))
        else:
            connection.execute(text("ALTER TABLE kyc_submissions ALTER COLUMN document_upload_placeholder TYPE TEXT"))
        if "selfie_placeholder" not in kyc_columns:
            connection.execute(text("ALTER TABLE kyc_submissions ADD COLUMN selfie_placeholder TEXT NULL"))
        else:
            connection.execute(text("ALTER TABLE kyc_submissions ALTER COLUMN selfie_placeholder TYPE TEXT"))
        if "correction_reason" not in kyc_columns:
            connection.execute(text("ALTER TABLE kyc_submissions ADD COLUMN correction_reason TEXT NULL"))

    inspector = inspect(engine)
    with engine.begin() as connection:
        complaint_status_values = [row[0] for row in connection.execute(text("SELECT unnest(enum_range(NULL::complaintstatus))::text"))]
        if "ASSIGNED" not in complaint_status_values:
            connection.execute(text("ALTER TYPE complaintstatus ADD VALUE IF NOT EXISTS 'ASSIGNED'"))
        replacement_status_values = [row[0] for row in connection.execute(text("SELECT unnest(enum_range(NULL::replacementstatus))::text"))]
        if "VERIFIED" not in replacement_status_values:
            connection.execute(text("ALTER TYPE replacementstatus ADD VALUE IF NOT EXISTS 'VERIFIED'"))

    inspector = inspect(engine)
    activation_columns = {column["name"] for column in inspector.get_columns("activation_attempts")}
    with engine.begin() as connection:
        if "failed_node" not in activation_columns:
            connection.execute(text("ALTER TABLE activation_attempts ADD COLUMN failed_node activationnode NULL"))
        if "failure_reason" not in activation_columns:
            connection.execute(text("ALTER TABLE activation_attempts ADD COLUMN failure_reason TEXT NULL"))

    inspector = inspect(engine)
    replacement_columns = {column["name"] for column in inspector.get_columns("replacement_requests")}
    with engine.begin() as connection:
        for column in ["old_iccid", "old_imsi", "new_iccid", "new_imsi"]:
            if column not in replacement_columns:
                connection.execute(text(f"ALTER TABLE replacement_requests ADD COLUMN {column} VARCHAR(32) NULL"))
        if "verified_by_user_id" not in replacement_columns:
            connection.execute(text("ALTER TABLE replacement_requests ADD COLUMN verified_by_user_id INTEGER NULL"))
        if "verified_at" not in replacement_columns:
            connection.execute(text("ALTER TABLE replacement_requests ADD COLUMN verified_at TIMESTAMP WITH TIME ZONE NULL"))

    inspector = inspect(engine)
    plan_columns = {column["name"] for column in inspector.get_columns("plans")}
    with engine.begin() as connection:
        for column, ddl in {
            "data_gb": "ALTER TABLE plans ADD COLUMN data_gb INTEGER NOT NULL DEFAULT 28",
            "voice_minutes": "ALTER TABLE plans ADD COLUMN voice_minutes INTEGER NOT NULL DEFAULT 1000",
            "sms_count": "ALTER TABLE plans ADD COLUMN sms_count INTEGER NOT NULL DEFAULT 100",
            "validity_days": "ALTER TABLE plans ADD COLUMN validity_days INTEGER NOT NULL DEFAULT 28",
            "is_active": "ALTER TABLE plans ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE",
        }.items():
            if column not in plan_columns:
                connection.execute(text(ddl))

    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    main()
