from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import ActivationNode, ActivationStatus, WorkflowNodeStatus


class ActivationAttempt(Base):
    __tablename__ = "activation_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    sim_record_id: Mapped[int] = mapped_column(ForeignKey("sim_records.id"), index=True)
    status: Mapped[ActivationStatus] = mapped_column(Enum(ActivationStatus), default=ActivationStatus.NOT_STARTED)
    current_node: Mapped[ActivationNode | None] = mapped_column(Enum(ActivationNode), nullable=True)
    failed_node: Mapped[ActivationNode | None] = mapped_column(Enum(ActivationNode), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sim_record = relationship("SimRecord", back_populates="activation_attempts")
    node_runs = relationship("ActivationNodeRun", back_populates="activation_attempt")


class ActivationNodeRun(Base):
    __tablename__ = "activation_node_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    activation_attempt_id: Mapped[int] = mapped_column(ForeignKey("activation_attempts.id"), index=True)
    node: Mapped[ActivationNode] = mapped_column(Enum(ActivationNode), index=True)
    status: Mapped[WorkflowNodeStatus] = mapped_column(Enum(WorkflowNodeStatus), default=WorkflowNodeStatus.PENDING)
    sequence: Mapped[int] = mapped_column(Integer)
    request_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    activation_attempt = relationship("ActivationAttempt", back_populates="node_runs")
