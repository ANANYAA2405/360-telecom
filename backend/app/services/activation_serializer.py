from app.models.activation import ActivationAttempt


def activation_payload(attempt: ActivationAttempt) -> dict:
    return {
        "id": attempt.id,
        "sim_record_id": attempt.sim_record_id,
        "msisdn": attempt.sim_record.msisdn if attempt.sim_record else None,
        "status": attempt.status,
        "current_node": attempt.current_node,
        "failed_node": attempt.failed_node,
        "failure_reason": attempt.failure_reason,
        "nodes": [
            {
                "node": run.node,
                "status": run.status,
                "sequence": run.sequence,
                "error_message": run.error_message,
                "request_payload": run.request_payload,
                "response_payload": run.response_payload,
            }
            for run in sorted(attempt.node_runs, key=lambda item: item.sequence)
        ],
    }
