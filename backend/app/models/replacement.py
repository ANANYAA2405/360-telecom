from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import ReplacementStatus


class ReplacementRequest(Base):
    __tablename__ = "replacement_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    old_sim_record_id: Mapped[int] = mapped_column(ForeignKey("sim_records.id"), index=True)
    new_sim_record_id: Mapped[int | None] = mapped_column(ForeignKey("sim_records.id"), nullable=True)
    old_iccid: Mapped[str | None] = mapped_column(String(32), nullable=True)
    old_imsi: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_iccid: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_imsi: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[ReplacementStatus] = mapped_column(Enum(ReplacementStatus), default=ReplacementStatus.REQUESTED)
    verified_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
