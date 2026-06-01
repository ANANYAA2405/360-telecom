from pydantic import BaseModel

from app.models.enums import ActivationNode, ActivationStatus, WorkflowNodeStatus


class ActivationNodeRead(BaseModel):
    node: ActivationNode
    status: WorkflowNodeStatus
    sequence: int
    request_payload: str | None = None
    response_payload: str | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}


class ActivationAttemptRead(BaseModel):
    id: int
    sim_record_id: int
    status: ActivationStatus
    current_node: ActivationNode | None
    failed_node: ActivationNode | None
    failure_reason: str | None
    node_runs: list[ActivationNodeRead] = []

    model_config = {"from_attributes": True}


class ManualActivationCaseRead(ActivationAttemptRead):
    customer_id: int | None = None
    customer_name: str | None = None
    customer_email: str | None = None
    msisdn: str
    iccid: str
    imsi: str
    company_id: int
