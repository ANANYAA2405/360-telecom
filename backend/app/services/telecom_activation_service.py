import json
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.activation import ActivationAttempt
from app.models.enums import ActivationStatus, SimStatus
from app.models.sim import SimRecord
from app.models.telecom_activation import (
    ActivationLayerLog,
    ActivationMaster,
    ActivationTimeline,
    ManualActionLog,
    NetworkLayerStatus,
    ResourceMapping,
)
from app.models.user import User

TELECOM_LAYERS = [
    ("CRM", "Customer order captured", "/simulator/crm/orders"),
    ("TIBCO", "Middleware orchestration", "/simulator/tibco/route"),
    ("OM", "Order Management validation", "/simulator/om/orders"),
    ("RNUM", "Resource Number Management", "/simulator/rnum/resources"),
    ("JCA", "Activation and provisioning adapter", "/simulator/jca/provision"),
    ("HSS_HLR", "Subscriber profile creation", "/simulator/core/hss-hlr"),
    ("PCRF_PCF", "Policy and charging rule creation", "/simulator/core/pcrf-pcf"),
    ("OCS_BILLING", "Billing account provisioning", "/simulator/billing/ocs"),
    ("NOTIFICATION", "Customer activation notification", "/simulator/notification/sms"),
]

LAYER_SEQUENCE = {layer: index for index, (layer, _name, _endpoint) in enumerate(TELECOM_LAYERS, start=1)}

REQUIRED_FIELDS = {
    "CRM": ["customer_id", "msisdn", "plan_id"],
    "TIBCO": ["correlation_id", "order_id"],
    "OM": ["order_id", "customer_id", "company_id"],
    "RNUM": ["msisdn", "iccid", "imsi"],
    "JCA": ["msisdn", "iccid", "imsi", "company_id"],
    "HSS_HLR": ["msisdn", "imsi", "company_id"],
    "PCRF_PCF": ["msisdn", "imsi", "plan_id"],
    "OCS_BILLING": ["msisdn", "customer_id", "plan_id"],
    "NOTIFICATION": ["msisdn", "customer_id"],
}


def now() -> datetime:
    return datetime.now(UTC)


def json_dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, default=str)


def next_id(db: Session, table, column) -> int:
    return (db.scalar(select(func.coalesce(func.max(column), 0)).select_from(table)) or 0) + 1


def generate_correlation_id(db: Session) -> str:
    return f"CORR-{now().year}-{next_id(db, ActivationMaster, ActivationMaster.activation_id):06d}"


def generate_order_id(db: Session) -> str:
    return f"ORD-{now().year}-{next_id(db, ActivationMaster, ActivationMaster.activation_id):06d}"


def generate_transaction_id(layer: str, activation_id: int, retry: int) -> str:
    return f"TXN-{layer}-{activation_id:06d}-{retry + 1:02d}"


def timeline(db: Session, master: ActivationMaster, event_type: str, description: str, layer: str | None, status: str) -> None:
    db.add(
        ActivationTimeline(
            activation_id=master.activation_id,
            event_type=event_type,
            event_description=description,
            layer=layer,
            status=status,
        )
    )


def build_layer_request(master: ActivationMaster, layer: str) -> dict[str, Any]:
    return {
        "correlation_id": master.correlation_id,
        "order_id": master.order_id,
        "activation_id": master.activation_id,
        "layer": layer,
        "customer_id": master.customer_id,
        "seller_id": master.seller_id,
        "company_id": master.company_id,
        "msisdn": master.msisdn,
        "iccid": master.iccid,
        "imsi": master.imsi,
        "plan_id": master.plan_id,
    }


def simulate_layer(layer: str, request_payload: dict[str, Any]) -> tuple[bool, dict[str, Any], str | None, str | None]:
    missing = [field for field in REQUIRED_FIELDS[layer] if request_payload.get(field) in {None, ""}]
    if missing:
        return False, {"status": "FAILED", "layer": layer, "missing_fields": missing}, "VAL-001", f"Missing required fields: {', '.join(missing)}"
    return True, {
        "status": "SUCCESS",
        "layer": layer,
        "reference_id": f"{layer}-{request_payload['msisdn']}",
        "processed_at": now().isoformat(),
    }, None, None


def get_or_create_master(db: Session, sim: SimRecord, attempt: ActivationAttempt) -> ActivationMaster:
    master = db.scalar(select(ActivationMaster).where(ActivationMaster.activation_attempt_id == attempt.id))
    if master:
        return master
    customer = sim.reserved_by
    master = ActivationMaster(
        activation_attempt_id=attempt.id,
        correlation_id=generate_correlation_id(db),
        order_id=generate_order_id(db),
        customer_id=sim.reserved_by_user_id,
        seller_id=sim.seller_id,
        company_id=sim.company_id,
        msisdn=sim.msisdn,
        iccid=sim.iccid,
        imsi=sim.imsi,
        plan_id=sim.plan_id,
        activation_status="RUNNING",
        current_layer="CRM",
        fallout_status=None,
    )
    db.add(master)
    db.flush()
    db.add(
        ResourceMapping(
            customer_id=sim.reserved_by_user_id,
            customer_name=customer.full_name if customer else None,
            customer_email=customer.email if customer else None,
            customer_phone=sim.msisdn,
            msisdn=sim.msisdn,
            iccid=sim.iccid,
            imsi=sim.imsi,
            order_id=master.order_id,
            activation_id=master.activation_id,
            plan_id=sim.plan_id,
            operator=sim.company.name if sim.company else None,
            current_status="RUNNING",
        )
    )
    timeline(db, master, "ORDER_CREATED", f"Activation order {master.order_id} created", "CRM", "RUNNING")
    return master


def sync_resource_mapping(db: Session, master: ActivationMaster) -> None:
    mapping = db.scalar(select(ResourceMapping).where(ResourceMapping.activation_id == master.activation_id))
    if mapping:
        mapping.current_status = master.activation_status
        mapping.plan_id = master.plan_id


def update_network_status(db: Session, master: ActivationMaster, layer: str, status: str, start: datetime, end: datetime, latency: int) -> None:
    row = db.scalar(select(NetworkLayerStatus).where(NetworkLayerStatus.activation_id == master.activation_id, NetworkLayerStatus.layer_name == layer))
    if row is None:
        row = NetworkLayerStatus(activation_id=master.activation_id, layer_name=layer)
        db.add(row)
    row.status = status
    row.start_time = start
    row.end_time = end
    row.latency = latency


def run_layer(db: Session, master: ActivationMaster, layer: str, resumed_from: str | None = None) -> bool:
    sequence = LAYER_SEQUENCE[layer]
    layer_name, api_name, endpoint = TELECOM_LAYERS[sequence - 1]
    request_timestamp = now()
    started = perf_counter()
    request_payload = build_layer_request(master, layer)
    succeeded, response_payload, error_code, error_message = simulate_layer(layer, request_payload)
    latency = max(int((perf_counter() - started) * 1000), 1)
    response_timestamp = now()
    status = "SUCCESS" if succeeded else "FAILED"
    retry_attempt_no = master.retry_count + 1 if resumed_from else 0
    log = ActivationLayerLog(
        activation_id=master.activation_id,
        correlation_id=master.correlation_id,
        order_id=master.order_id,
        transaction_id=generate_transaction_id(layer, master.activation_id, retry_attempt_no),
        customer_id=master.customer_id,
        seller_id=master.seller_id,
        company_id=master.company_id,
        msisdn=master.msisdn,
        iccid=master.iccid,
        imsi=master.imsi,
        layer_sequence=sequence,
        layer_name=layer_name,
        sub_layer_name=api_name,
        api_name=f"{layer_name}Service.process",
        api_endpoint=endpoint,
        request_payload=json_dump(request_payload),
        request_headers=json_dump({"X-Correlation-ID": master.correlation_id, "X-Order-ID": master.order_id}),
        request_timestamp=request_timestamp,
        response_payload=json_dump(response_payload),
        response_headers=json_dump({"X-Transaction-ID": generate_transaction_id(layer, master.activation_id, retry_attempt_no)}),
        response_timestamp=response_timestamp,
        latency_ms=latency,
        execution_time_ms=latency,
        status=status,
        error_code=error_code,
        error_message=error_message,
        retry_count=master.retry_count,
        retry_attempt_no=retry_attempt_no,
        resumed_from_layer=resumed_from,
        manual_intervention_required=not succeeded,
        fallout_generated=not succeeded,
        fallout_reason=error_message,
    )
    db.add(log)
    update_network_status(db, master, layer_name, status, request_timestamp, response_timestamp, latency)
    if succeeded:
        master.last_successful_layer = layer
        master.current_layer = layer
        timeline(db, master, f"{layer}_SUCCESS", f"{api_name} completed", layer, "SUCCESS")
        return True
    master.activation_status = "FAILED"
    master.current_layer = layer
    master.last_failed_layer = layer
    master.fallout_status = "MANUAL_REVIEW"
    master.fallout_layer = layer
    master.fallout_reason = error_message
    master.fallout_created_time = now()
    timeline(db, master, f"{layer}_FAILED", error_message or f"{layer} failed", layer, "FAILED")
    return False


def run_telecom_activation(db: Session, sim: SimRecord, attempt: ActivationAttempt, resume_from: str | None = None) -> ActivationMaster:
    master = get_or_create_master(db, sim, attempt)
    start_index = LAYER_SEQUENCE.get(resume_from, 1) - 1 if resume_from else 0
    master.activation_status = "RUNNING"
    master.fallout_status = "RESUMED" if resume_from else master.fallout_status
    master.current_layer = TELECOM_LAYERS[start_index][0]
    if resume_from:
        master.retry_count += 1
        timeline(db, master, "RESUME_REQUESTED", f"Workflow resumed from {resume_from}", resume_from, "RESUMED")
    for layer, _label, _endpoint in TELECOM_LAYERS[start_index:]:
        ok = run_layer(db, master, layer, resumed_from=resume_from)
        db.flush()
        if not ok:
            attempt.status = ActivationStatus.MANUAL_REVIEW_REQUIRED
            attempt.failure_reason = master.fallout_reason
            sim.status = SimStatus.MANUAL_REVIEW_REQUIRED
            sync_resource_mapping(db, master)
            return master
    completed = now()
    master.activation_status = "COMPLETE"
    master.current_layer = None
    master.last_failed_layer = None
    master.fallout_status = "RESOLVED"
    master.fallout_resolved_time = completed
    master.sla_end_time = completed
    master.total_activation_time = int((completed - master.sla_start_time).total_seconds())
    timeline(db, master, "ACTIVATION_COMPLETE", "Service Activated", "NOTIFICATION", "COMPLETE")
    sync_resource_mapping(db, master)
    return master


def record_manual_action(db: Session, master: ActivationMaster, actor: User, new_status: str, reason: str | None = None) -> None:
    db.add(
        ManualActionLog(
            activation_id=master.activation_id,
            admin_id=actor.id,
            corrected_layer=master.last_failed_layer or master.current_layer or "UNKNOWN",
            old_status=master.activation_status,
            new_status=new_status,
            correction_reason=reason,
        )
    )
    master.fallout_status = "RESOLVED"
    master.fallout_resolved_time = now()
    timeline(db, master, "MANUAL_ACTION", reason or "Manual correction applied", master.last_failed_layer, new_status)


def activation_details(db: Session, master: ActivationMaster) -> dict[str, Any]:
    logs = list(db.scalars(select(ActivationLayerLog).where(ActivationLayerLog.activation_id == master.activation_id).order_by(ActivationLayerLog.log_id.desc()).limit(30)))
    events = list(db.scalars(select(ActivationTimeline).where(ActivationTimeline.activation_id == master.activation_id).order_by(ActivationTimeline.timestamp)))
    network = list(db.scalars(select(NetworkLayerStatus).where(NetworkLayerStatus.activation_id == master.activation_id).order_by(NetworkLayerStatus.status_id)))
    return {
        "activation_id": master.activation_id,
        "correlation_id": master.correlation_id,
        "order_id": master.order_id,
        "customer_id": master.customer_id,
        "seller_id": master.seller_id,
        "company_id": master.company_id,
        "msisdn": master.msisdn,
        "iccid": master.iccid,
        "imsi": master.imsi,
        "plan_id": master.plan_id,
        "activation_status": master.activation_status,
        "current_layer": master.current_layer,
        "last_successful_layer": master.last_successful_layer,
        "last_failed_layer": master.last_failed_layer,
        "retry_count": master.retry_count,
        "fallout_status": master.fallout_status,
        "fallout_reason": master.fallout_reason,
        "fallout_layer": master.fallout_layer,
        "total_activation_time": master.total_activation_time,
        "timeline": [{"event_id": e.event_id, "timestamp": e.timestamp, "event_type": e.event_type, "event_description": e.event_description, "layer": e.layer, "status": e.status} for e in events],
        "logs": [
            {
                "log_id": log.log_id,
                "transaction_id": log.transaction_id,
                "layer_name": log.layer_name,
                "api_name": log.api_name,
                "api_endpoint": log.api_endpoint,
                "request_payload": log.request_payload,
                "response_payload": log.response_payload,
                "latency_ms": log.latency_ms,
                "status": log.status,
                "error_code": log.error_code,
                "error_message": log.error_message,
                "retry_count": log.retry_count,
                "resumed_from_layer": log.resumed_from_layer,
                "fallout_generated": log.fallout_generated,
                "fallout_reason": log.fallout_reason,
            }
            for log in logs
        ],
        "network_layers": [
            {"layer_name": item.layer_name, "status": item.status, "start_time": item.start_time, "end_time": item.end_time, "latency": item.latency}
            for item in network
        ],
    }


def find_activation_by_search(db: Session, query: str, company_id: int | None = None) -> ActivationMaster | None:
    filters = [
        ActivationMaster.msisdn == query,
        ActivationMaster.iccid == query,
        ActivationMaster.imsi == query,
        ActivationMaster.order_id == query,
        ActivationMaster.correlation_id == query,
    ]
    if query.isdigit():
        filters.append(ActivationMaster.customer_id == int(query))
    stmt = select(ActivationMaster).where(func.bool_or(False) if False else filters[0])
    condition = filters[0]
    for item in filters[1:]:
        condition = condition | item
    stmt = select(ActivationMaster).where(condition).order_by(ActivationMaster.created_at.desc())
    if company_id is not None:
        stmt = stmt.where(ActivationMaster.company_id == company_id)
    return db.scalar(stmt)


def telecom_metrics(db: Session, company_id: int | None = None) -> dict[str, Any]:
    filters = []
    if company_id is not None:
        filters.append(ActivationMaster.company_id == company_id)
    total = db.scalar(select(func.count()).select_from(ActivationMaster).where(*filters)) or 0
    complete = db.scalar(select(func.count()).select_from(ActivationMaster).where(ActivationMaster.activation_status == "COMPLETE", *filters)) or 0
    failed = db.scalar(select(func.count()).select_from(ActivationMaster).where(ActivationMaster.activation_status == "FAILED", *filters)) or 0
    fallout = db.scalar(select(func.count()).select_from(ActivationMaster).where(ActivationMaster.fallout_status.in_(["MANUAL_REVIEW", "PENDING", "FAILED"]), *filters)) or 0
    avg_time = db.scalar(select(func.coalesce(func.avg(ActivationMaster.total_activation_time), 0)).where(*filters)) or 0
    layer_rows = db.execute(
        select(ActivationMaster.last_failed_layer, func.count())
        .where(ActivationMaster.last_failed_layer.is_not(None), *filters)
        .group_by(ActivationMaster.last_failed_layer)
        .order_by(func.count().desc())
    ).all()
    return {
        "activation_success_rate": round((complete / total) * 100, 2) if total else 0,
        "activation_failure_rate": round((failed / total) * 100, 2) if total else 0,
        "average_activation_time": round(float(avg_time), 2),
        "most_failed_layer": layer_rows[0][0] if layer_rows else None,
        "fallout_count": fallout,
        "resume_count": db.scalar(select(func.coalesce(func.sum(ActivationMaster.retry_count), 0)).where(*filters)) or 0,
    }
