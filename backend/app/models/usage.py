from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class SimUsage(Base):
    __tablename__ = "sim_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    sim_record_id: Mapped[int] = mapped_column(ForeignKey("sim_records.id"), unique=True, index=True)
    data_used_gb: Mapped[int] = mapped_column(Integer, default=0)
    voice_used_minutes: Mapped[int] = mapped_column(Integer, default=0)
    sms_used_count: Mapped[int] = mapped_column(Integer, default=0)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    sim_record = relationship("SimRecord")


class Recharge(Base):
    __tablename__ = "recharges"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    sim_record_id: Mapped[int] = mapped_column(ForeignKey("sim_records.id"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(32), default="SUCCESS")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    sim_record = relationship("SimRecord")
    plan = relationship("Plan")


class SellerTarget(Base):
    __tablename__ = "seller_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    month: Mapped[str] = mapped_column(String(7), index=True)
    activation_target: Mapped[int] = mapped_column(Integer, default=0)
    recharge_target: Mapped[int] = mapped_column(Integer, default=0)
    kyc_target: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    seller = relationship("User")
