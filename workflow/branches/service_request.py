"""Service request: extract details -> route to department -> confirm -> start SLA."""
from typing import Any, Dict

from workflow.branches.common import act, audit, draft, sla_due, status_for

DEPARTMENT_ROUTING = {
    "card replacement": "Cards Operations",
    "lost card": "Cards Operations",
    "address change": "KYC - Account Maintenance",
    "personal details": "KYC - Account Maintenance",
    "statement": "Statements & Servicing",
    "credit limit": "Credit Risk - Limits",
    "account closure": "Retentions & Closures",
    "direct debit": "Payments Operations",
}
DEFAULT_DEPARTMENT = "Customer Service - Tier 1"

# What a department actually needs before it can action the request. Demanding a
# card number for an address change would strand solvable cases in a generalist queue.
REQUIRED_BY_TOPIC = {
    "Cards Operations": ["card_last_four"],
    "KYC - Account Maintenance": ["new_address"],
    "Credit Risk - Limits": ["requested_limit"],
    "Statements & Servicing": ["statement_period"],
}
DEFAULT_REQUIRED = ["requested_action"]


def _department(sub_topic: str) -> str:
    lowered = (sub_topic or "").lower()
    for key, dept in DEPARTMENT_ROUTING.items():
        if key in lowered or any(word in lowered for word in key.split()):
            return dept
    return DEFAULT_DEPARTMENT


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    cls = state["classification"]
    entities = dict(cls.entities or {})
    if not entities.get("card_last_four"):
        from services.redaction import last_four, stated_last_four
        found = last_four(state.get("pii_map", {})) or stated_last_four(state.get("raw_text", ""))
        if found:
            entities["card_last_four"] = found
    entities.setdefault("requested_action", cls.sub_topic or "")

    # Step 1 - completeness check against what the receiving department needs.
    dept = _department(cls.sub_topic)
    required = REQUIRED_BY_TOPIC.get(dept, DEFAULT_REQUIRED)
    missing = [f for f in required if not entities.get(f)]
    actions = [act(
        "Extract required details",
        f"Needs {', '.join(required)} for {dept}. "
        f"Captured: {', '.join(f'{k}={v}' for k, v in entities.items() if v) or 'none'}"
        + (f" | Missing: {', '.join(missing)}" if missing else ""),
        "incomplete" if missing else "complete",
    )]

    # Step 2 - department routing.
    if missing:
        dept = DEFAULT_DEPARTMENT  # incomplete cases cannot be actioned by a specialist queue
    actions.append(act("Route to department", f"Assigned to {dept}", dept))

    # Step 3 - confirmation to the requester.
    body = draft(
        f"Confirm receipt of a service request: {cls.sub_topic or 'account servicing request'}. "
        f"State that it has been passed to the relevant team. "
        + (f"Politely ask the customer to supply: {', '.join(missing)}." if missing else "Do not ask for further information."),
        state.get("redacted_text", ""),
        f"Thank you for your request regarding {cls.sub_topic or 'your account'}. "
        f"We have passed this to our {dept} team, who will action it shortly.\n\nCard Services",
    )
    actions.append(act("Generate confirmation", "Confirmation drafted for requester", body[:160] + ("..." if len(body) > 160 else "")))

    # Step 4 - SLA clock.
    due = sla_due("service_request")
    actions.append(act("Start SLA timer", f"Action due by {due}", due))

    return {
        "actions": actions,
        "draft_response": body,
        "routed_to": dept,
        "sla_due_at": due,
        "status": status_for(state, "routed"),
        "audit": audit(state, "branch:service_request", f"4 steps executed, routed to {dept}",
                       f"Missing details: {', '.join(missing)}" if missing else "All required details present"),
    }
