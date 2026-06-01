from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    monthly_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    data_gb: Mapped[int] = mapped_column(Integer, default=28)
    voice_minutes: Mapped[int] = mapped_column(Integer, default=1000)
    sms_count: Mapped[int] = mapped_column(Integer, default=100)
    validity_days: Mapped[int] = mapped_column(Integer, default=28)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
