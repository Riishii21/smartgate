"""Deterministic routing. No LLM call happens here, by design.

The model produces a classification; this module alone decides what the system
does with it. That keeps branch selection testable, reproducible, and auditable.
"""
from datetime import datetime, timezone
from typing import Any, Dict

import config
from workflow.schemas import RequestType

BRANCH_BY_TYPE = {
    RequestType.BILLING_DISPUTE: "dispute",
    RequestType.GENERAL_ENQUIRY: "enquiry",
    RequestType.SERVICE_REQUEST: "service_request",
    RequestType.COMPLAINT: "complaint",
}


def gate(state: Dict[str, Any]) -> Dict[str, Any]:
    """Decide the branch and whether outputs may be sent without a human."""
    cls = state["classification"]
    reasons = []

    if cls.confidence < config.CONFIDENCE_THRESHOLD:
        reasons.append(f"Classifier confidence {cls.confidence:.2f} below threshold {config.CONFIDENCE_THRESHOLD}")
    if cls.is_vulnerable:
        signals = ", ".join(s.value for s in cls.vulnerability_signals if s.value != "none")
        reasons.append(f"Vulnerability signal detected ({signals}) - requires trained handler")
    if cls.request_type == RequestType.COMPLAINT:
        # Held by request type, not by urgency. A complaint carries a regulatory
        # clock and must be seen by a handler regardless of how the model scored it.
        reasons.append("Complaint - regulated handling, requires handler sign-off")
    if cls.urgency.value == "critical":
        reasons.append("Critical urgency - supervisor sign-off required before send")

    branch = BRANCH_BY_TYPE[cls.request_type]
    return {
        "branch": branch,
        "hold_for_human": bool(reasons),
        "hold_reasons": reasons,
        "audit": state.get("audit", []) + [{
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "node": "router_gate",
            "decision": f"branch={branch}, auto_send={'no' if reasons else 'yes'}",
            "detail": "; ".join(reasons) if reasons else "All gate checks passed",
        }],
    }


def select_branch(state: Dict[str, Any]) -> str:
    """Conditional edge function consumed by LangGraph."""
    return state["branch"]