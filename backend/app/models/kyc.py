from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import KycStatus


class KycSubmission(Base):
    __tablename__ = "kyc_submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    sim_record_id: Mapped[int] = mapped_column(ForeignKey("sim_records.id"), unique=True)
    full_name: Mapped[str] = mapped_column(String(160), default="")
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    document_type: Mapped[str] = mapped_column(String(60))
    document_number: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(Text)
    document_upload_placeholder: Mapped[str | None] = mapped_column(Text, nullable=True)
    selfie_placeholder: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[KycStatus] = mapped_column(Enum(KycStatus), default=KycStatus.PENDING, index=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    customer = relationship("User", foreign_keys=[customer_id], back_populates="kyc_submissions")
    reviewer = relationship("User", foreign_keys=[reviewed_by_user_id])
    sim_record = relationship("SimRecord", back_populates="kyc_submission")
