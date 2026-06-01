from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import SimStatus


class NumberSeries(Base):
    __tablename__ = "number_series"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    prefix: Mapped[str] = mapped_column(String(16), index=True)
    start_number: Mapped[str] = mapped_column(String(20))
    end_number: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    company = relationship("Company", back_populates="number_series")


class SimRecord(Base):
    __tablename__ = "sim_records"
    __table_args__ = (
        UniqueConstraint("msisdn", name="uq_sim_records_msisdn"),
        UniqueConstraint("iccid", name="uq_sim_records_iccid"),
        UniqueConstraint("imsi", name="uq_sim_records_imsi"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    msisdn: Mapped[str] = mapped_column(String(20), index=True)
    iccid: Mapped[str] = mapped_column(String(32), index=True)
    imsi: Mapped[str] = mapped_column(String(32), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    seller_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id"), nullable=True, index=True)
    number_series_id: Mapped[int | None] = mapped_column(ForeignKey("number_series.id"), nullable=True)
    status: Mapped[SimStatus] = mapped_column(Enum(SimStatus), default=SimStatus.AVAILABLE, index=True)
    reserved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reserved_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    company = relationship("Company", back_populates="sim_records")
    seller = relationship("User", foreign_keys=[seller_id])
    plan = relationship("Plan")
    number_series = relationship("NumberSeries")
    reserved_by = relationship("User", foreign_keys=[reserved_by_user_id], back_populates="reservations")
    kyc_submission = relationship("KycSubmission", back_populates="sim_record", uselist=False)
    activation_attempts = relationship("ActivationAttempt", back_populates="sim_record")

    @property
    def company_name(self) -> str | None:
        return self.company.name if self.company else None
