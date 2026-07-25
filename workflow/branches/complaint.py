"""Complaint: pause automation -> acknowledge -> notify supervisor -> open regulated log.

This branch never auto-sends. A complaint carries a regulatory clock and, where a
vulnerability signal is present, must be handled by a trained agent. The system's
job is to prepare the case well, not to resolve it.
"""
from typing import Any, Dict

from workflow.branches.common import act, audit, draft, sla_due
from workflow.schemas import VulnerabilitySignal

REGULATORY_ACK_HOURS = 24
FINAL_RESPONSE_DAYS = 56


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    cls = state["classification"]
    signals = [s.value for s in cls.vulnerability_signals if s != VulnerabilitySignal.NONE]

    # Step 1 - hard stop on automated sending.
    actions = [act(
        "Pause auto-resolution",
        "Complaint branch never auto-sends; output held for agent review",
        "auto_send_disabled",
    )]

    # Step 2 - vulnerability handling.
    if signals:
        actions.append(act(
            "Apply vulnerable customer handling",
            f"Signals: {', '.join(signals)}. Assigned to trained handler; standard scripts suppressed.",
            "specialist_handling",
        ))
        handler = "Vulnerable Customer Team"
    else:
        handler = "Complaints - Senior Handler"

    # Step 3 - empathetic acknowledgement, drafted but not sent.
    body = draft(
        "Draft an acknowledgement of a complaint. Acknowledge the customer's experience and "
        "confirm the complaint has been logged and will be reviewed by a senior handler. "
        "Do not apportion blame, admit liability, promise compensation, or give a resolution date."
        + (" The customer has disclosed difficult personal circumstances; be especially considerate "
           "and do not reference the disclosure in detail." if signals else ""),
        state.get("redacted_text", ""),
        "Thank you for contacting us. We are sorry to hear about your experience. Your complaint "
        "has been logged and a senior handler will review it and be in touch.\n\nCard Services",
    )
    actions.append(act("Draft acknowledgement", "Held as draft pending agent approval", body[:160] + ("..." if len(body) > 160 else "")))

    # Step 4 - supervisor notification.
    actions.append(act("Notify supervisor", f"Alert raised to {handler}", handler))

    # Step 5 - regulated complaint log.
    due = sla_due("complaint")
    actions.append(act(
        "Open complaint record",
        f"Logged with {REGULATORY_ACK_HOURS}h acknowledgement target and {FINAL_RESPONSE_DAYS}-day final response clock",
        due,
    ))

    return {
        "actions": actions,
        "draft_response": body,
        "routed_to": handler,
        "sla_due_at": due,
        "status": "pending_human_approval",
        "hold_for_human": True,
        "hold_reasons": state.get("hold_reasons", []) or ["Complaint branch always requires human approval"],
        "audit": audit(state, "branch:complaint", f"5 steps executed, held for {handler}",
                       f"Vulnerability signals: {', '.join(signals)}" if signals else "No vulnerability signals"),
    }
