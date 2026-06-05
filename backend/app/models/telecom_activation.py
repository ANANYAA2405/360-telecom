from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ActivationMaster(Base):
    __tablename__ = "activation_master"

    activation_id: Mapped[int] = mapped_column(primary_key=True)
    activation_attempt_id: Mapped[int | None] = mapped_column(ForeignKey("activation_attempts.id"), index=True, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    order_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    seller_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    msisdn: Mapped[str] = mapped_column(String(16), index=True)
    iccid: Mapped[str] = mapped_column(String(32), index=True)
    imsi: Mapped[str] = mapped_column(String(32), index=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id"), index=True, nullable=True)
    activation_status: Mapped[str] = mapped_column(String(40), default="RUNNING", index=True)
    current_layer: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_successful_layer: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_failed_layer: Mapped[str | None] = mapped_column(String(80), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    fallout_status: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    fallout_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    fallout_layer: Mapped[str | None] = mapped_column(String(80), nullable=True)
    fallout_created_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fallout_resolved_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    sla_end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_activation_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class ActivationLayerLog(Base):
    __tablename__ = "activation_layer_logs"

    log_id: Mapped[int] = mapped_column(primary_key=True)
    activation_id: Mapped[int] = mapped_column(ForeignKey("activation_master.activation_id"), index=True)
    correlation_id: Mapped[str] = mapped_column(String(40), index=True)
    order_id: Mapped[str] = mapped_column(String(40), index=True)
    transaction_id: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    seller_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    msisdn: Mapped[str] = mapped_column(String(16), index=True)
    iccid: Mapped[str] = mapped_column(String(32), index=True)
    imsi: Mapped[str] = mapped_column(String(32), index=True)
    layer_sequence: Mapped[int] = mapped_column(Integer)
    layer_name: Mapped[str] = mapped_column(String(80), index=True)
    sub_layer_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    api_name: Mapped[str] = mapped_column(String(120))
    api_endpoint: Mapped[str] = mapped_column(String(160))
    request_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_headers: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    response_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_headers: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    retry_attempt_no: Mapped[int] = mapped_column(Integer, default=0)
    resumed_from_layer: Mapped[str | None] = mapped_column(String(80), nullable=True)
    manual_intervention_required: Mapped[bool] = mapped_column(Boolean, default=False)
    manual_intervention_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    manual_intervention_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    manual_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    fallout_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    fallout_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    fallout_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class ActivationTimeline(Base):
    __tablename__ = "activation_timeline"

    event_id: Mapped[int] = mapped_column(primary_key=True)
    activation_id: Mapped[int] = mapped_column(ForeignKey("activation_master.activation_id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    event_type: Mapped[str] = mapped_column(String(80))
    event_description: Mapped[str] = mapped_column(Text)
    layer: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(40), index=True)


class ResourceMapping(Base):
    __tablename__ = "resource_mapping"

    mapping_id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(24), nullable=True)
    msisdn: Mapped[str] = mapped_column(String(16), index=True)
    iccid: Mapped[str] = mapped_column(String(32), index=True)
    imsi: Mapped[str] = mapped_column(String(32), index=True)
    order_id: Mapped[str] = mapped_column(String(40), index=True)
    activation_id: Mapped[int] = mapped_column(ForeignKey("activation_master.activation_id"), index=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id"), nullable=True)
    operator: Mapped[str | None] = mapped_column(String(120), nullable=True)
    current_status: Mapped[str] = mapped_column(String(40), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class NetworkLayerStatus(Base):
    __tablename__ = "network_layer_status"

    status_id: Mapped[int] = mapped_column(primary_key=True)
    activation_id: Mapped[int] = mapped_column(ForeignKey("activation_master.activation_id"), index=True)
    layer_name: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latency: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ManualActionLog(Base):
    __tablename__ = "manual_action_logs"

    action_id: Mapped[int] = mapped_column(primary_key=True)
    activation_id: Mapped[int] = mapped_column(ForeignKey("activation_master.activation_id"), index=True)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    corrected_layer: Mapped[str] = mapped_column(String(80))
    old_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    new_status: Mapped[str] = mapped_column(String(40))
    correction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
