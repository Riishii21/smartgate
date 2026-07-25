"""Billing dispute: eligibility check -> provisional credit draft -> route -> follow-up."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from services.redaction import last_four
from workflow.branches.common import act, audit, draft, sla_due, status_for

DISPUTE_WINDOW_DAYS = 120


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    cls = state["classification"]
    entities = cls.entities or {}
    amount = entities.get("amount", "the disputed amount")
    merchant = entities.get("merchant", "the merchant")
    card = last_four(state.get("pii_map", {})) or "on file"

    actions = []

    # Step 1 - eligibility against the chargeback window.
    eligible = True
    txn_date = entities.get("transaction_date", "")
    note = f"No transaction date supplied; assuming within {DISPUTE_WINDOW_DAYS}-day window."
    if txn_date:
        try:
            parsed = datetime.fromisoformat(txn_date).replace(tzinfo=timezone.utc)
            eligible = (datetime.now(timezone.utc) - parsed) <= timedelta(days=DISPUTE_WINDOW_DAYS)
            note = f"Transaction dated {txn_date}; {'within' if eligible else 'outside'} {DISPUTE_WINDOW_DAYS}-day window."
        except ValueError:
            note = f"Unparseable transaction date '{txn_date}'; flagged for manual check."
    actions.append(act("Check dispute eligibility", note, "eligible" if eligible else "out_of_window"))

    # Step 2 - acknowledgement draft.
    body = draft(
        f"Acknowledge a disputed card transaction of {amount} at {merchant} on the card ending {card}. "
        f"Confirm the dispute has been raised and that the team will investigate. "
        f"{'Mention provisional credit may apply while investigated.' if eligible else 'Explain the claim is outside the usual dispute window and will need manual review.'}",
        state.get("redacted_text", ""),
        f"Thank you for contacting us about the {amount} transaction at {merchant} on your card ending {card}. "
        "We have raised a dispute and our team will investigate. We will be in touch with an update.\n\nCard Services",
    )
    actions.append(act("Draft acknowledgement", "Customer-facing reply generated", body[:160] + ("..." if len(body) > 160 else "")))

    # Step 3 - route.
    queue = "Disputes - Chargebacks" if eligible else "Disputes - Manual Review"
    actions.append(act("Route to team", f"Assigned to {queue}", queue))

    # Step 4 - follow-up task.
    due = sla_due("billing_dispute")
    actions.append(act("Set follow-up", f"Investigation update due by {due}", due))

    return {
        "actions": actions,
        "draft_response": body,
        "routed_to": queue,
        "sla_due_at": due,
        "status": status_for(state, "auto_actioned"),
        "audit": audit(state, "branch:dispute", f"4 steps executed, routed to {queue}", note),
    }
