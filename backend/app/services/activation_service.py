import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.activation import ActivationAttempt, ActivationNodeRun
from app.models.enums import ActivationNode, ActivationStatus, SimStatus, WorkflowNodeStatus
from app.models.sim import SimRecord
from app.models.usage import SimUsage

ACTIVATION_SEQUENCE = [
    ActivationNode.HSS_HLR,
    ActivationNode.PCRF_PCF,
    ActivationNode.OCS_BILLING,
    ActivationNode.SIM_PROVISIONING,
    ActivationNode.NOTIFICATION,
]

NODE_REQUIRED_FIELDS = {
    ActivationNode.HSS_HLR: ["msisdn", "imsi", "company_id"],
    ActivationNode.PCRF_PCF: ["msisdn", "imsi", "plan_code"],
    ActivationNode.OCS_BILLING: ["msisdn", "customer_id", "billing_account"],
    ActivationNode.SIM_PROVISIONING: ["msisdn", "iccid", "imsi"],
    ActivationNode.NOTIFICATION: ["msisdn", "customer_id", "notification_channel"],
}


def create_activation_attempt(db: Session, sim: SimRecord) -> ActivationAttempt:
    attempt = ActivationAttempt(
        sim_record_id=sim.id,
        status=ActivationStatus.RUNNING,
        current_node=ACTIVATION_SEQUENCE[0],
    )
    db.add(attempt)
    db.flush()
    for index, node in enumerate(ACTIVATION_SEQUENCE, start=1):
        db.add(ActivationNodeRun(activation_attempt_id=attempt.id, node=node, sequence=index))
    sim.status = SimStatus.ACTIVATING
    return attempt


def build_node_request(sim: SimRecord, node: ActivationNode) -> dict[str, Any]:
    base = {
        "node": node,
        "sim_record_id": sim.id,
        "msisdn": sim.msisdn,
        "iccid": sim.iccid,
        "imsi": sim.imsi,
        "company_id": sim.company_id,
        "customer_id": sim.reserved_by_user_id,
        "plan_code": f"DEFAULT-{sim.company_id}",
        "billing_account": f"BILL-{sim.msisdn}",
        "notification_channel": "SMS",
    }
    return {field: base[field] for field in ["node", *NODE_REQUIRED_FIELDS[node], "sim_record_id"]}


def validate_node_request(node: ActivationNode, request_payload: dict[str, Any]) -> list[str]:
    return [
        field
        for field in NODE_REQUIRED_FIELDS[node]
        if request_payload.get(field) in {None, ""}
    ]


def simulate_node(node: ActivationNode, request_payload: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    missing = validate_node_request(node, request_payload)
    if missing:
        return False, {
            "node": node,
            "status": "FAILED",
            "failure_reason": f"Missing required fields: {', '.join(missing)}",
        }
    return True, {
        "node": node,
        "status": "SUCCESS",
        "reference_id": f"{node}-{request_payload['msisdn']}",
        "processed_at": datetime.now(UTC).isoformat(),
    }


def run_activation_workflow(db: Session, sim: SimRecord, attempt: ActivationAttempt | None = None) -> ActivationAttempt:
    if attempt is None:
        attempt = create_activation_attempt(db, sim)
    db.flush()
    attempt = db.scalar(
        select(ActivationAttempt)
        .options(
            selectinload(ActivationAttempt.node_runs),
            selectinload(ActivationAttempt.sim_record).selectinload(SimRecord.plan),
            selectinload(ActivationAttempt.sim_record).selectinload(SimRecord.company),
            selectinload(ActivationAttempt.sim_record).selectinload(SimRecord.reserved_by),
        )
        .where(ActivationAttempt.id == attempt.id)
    )
    sim = attempt.sim_record
    sim.status = SimStatus.ACTIVATING
    attempt.status = ActivationStatus.RUNNING
    attempt.failed_node = None
    attempt.failure_reason = None

    node_runs = sorted(attempt.node_runs, key=lambda run: run.sequence)
    for node_run in node_runs:
        if node_run.status == WorkflowNodeStatus.SUCCESS:
            continue
        attempt.current_node = node_run.node
        node_run.status = WorkflowNodeStatus.RUNNING
        node_run.started_at = datetime.now(UTC)
        request_payload = build_node_request(sim, node_run.node)
        node_run.request_payload = json.dumps(request_payload)
        succeeded, response_payload = simulate_node(node_run.node, request_payload)
        node_run.response_payload = json.dumps(response_payload)
        node_run.finished_at = datetime.now(UTC)
        if not succeeded:
            failure_reason = response_payload["failure_reason"]
            node_run.status = WorkflowNodeStatus.FAILED
            node_run.error_message = failure_reason
            attempt.status = ActivationStatus.MANUAL_REVIEW_REQUIRED
            attempt.failed_node = node_run.node
            attempt.failure_reason = failure_reason
            attempt.current_node = node_run.node
            sim.status = SimStatus.MANUAL_REVIEW_REQUIRED
            db.flush()
            return attempt
        node_run.status = WorkflowNodeStatus.SUCCESS
        node_run.error_message = None

    attempt.status = ActivationStatus.COMPLETE
    attempt.current_node = None
    attempt.failed_node = None
    attempt.failure_reason = None
    attempt.completed_at = datetime.now(UTC)
    sim.status = SimStatus.ACTIVE
    from app.services.telecom_activation_service import run_telecom_activation

    telecom_master = run_telecom_activation(db, sim, attempt)
    if telecom_master.activation_status == "FAILED":
        attempt.status = ActivationStatus.MANUAL_REVIEW_REQUIRED
        attempt.failed_node = None
        attempt.failure_reason = telecom_master.fallout_reason
        attempt.current_node = None
        sim.status = SimStatus.MANUAL_REVIEW_REQUIRED
        db.flush()
        return attempt
    if sim.plan_id:
        usage = db.scalar(select(SimUsage).where(SimUsage.sim_record_id == sim.id))
        if usage is None:
            usage = SimUsage(sim_record_id=sim.id)
            db.add(usage)
        if sim.plan:
            usage.valid_until = datetime.now(UTC) + timedelta(days=sim.plan.validity_days)
    db.flush()
    return attempt


def prepare_failed_node_for_resubmission(attempt: ActivationAttempt) -> None:
    if attempt.failed_node is None:
        return
    for node_run in attempt.node_runs:
        if node_run.node == attempt.failed_node and node_run.status == WorkflowNodeStatus.FAILED:
            node_run.status = WorkflowNodeStatus.PENDING
            node_run.error_message = None
            break


def mark_node_result(
    db: Session,
    attempt: ActivationAttempt,
    node_run: ActivationNodeRun,
    succeeded: bool,
    response_payload: str | None = None,
    error_message: str | None = None,
) -> None:
    node_run.status = WorkflowNodeStatus.SUCCESS if succeeded else WorkflowNodeStatus.FAILED
    node_run.response_payload = response_payload
    node_run.error_message = error_message
    node_run.finished_at = datetime.now(UTC)
    if not succeeded:
        attempt.status = ActivationStatus.MANUAL_REVIEW_REQUIRED
        attempt.failed_node = node_run.node
        attempt.failure_reason = error_message
        attempt.current_node = node_run.node
        attempt.sim_record.status = SimStatus.MANUAL_REVIEW_REQUIRED
    db.flush()
