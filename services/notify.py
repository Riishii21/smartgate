"""Internal notifications for cases that need a person.

Delivery is deliberately simulated: the notification is composed, recorded
against the case, and shown in the console. In deployment the same payload
would be handed to SMTP, Slack, or a ticketing API without the branches
changing, because they only ever ask for a notification to be raised.

Two channels, chosen by how quickly someone must look:
  queue  — the case waits to be picked up. Correct for most held cases.
  alert  — someone is told now. Reserved for vulnerability disclosures,
           suspected fraud, and regulated complaints.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class Notification:
    channel: str          # "queue" or "alert"
    to: str               # team or role
    subject: str
    body: str
    raised_at: str

    def as_dict(self) -> Dict[str, str]:
        return {"channel": self.channel, "to": self.to, "subject": self.subject,
                "body": self.body, "raised_at": self.raised_at}


ALERT_TRIGGERS = ("vulnerability", "regulated handling", "critical urgency")


def _needs_alert(hold_reasons: List[str]) -> bool:
    joined = " ".join(hold_reasons).lower()
    return any(trigger in joined for trigger in ALERT_TRIGGERS)


def compose(state: Dict[str, Any]) -> Notification:
    """Build the internal notification for a case that stopped."""
    cls = state["classification"]
    reasons = state.get("hold_reasons", [])
    alert = _needs_alert(reasons)
    case_id = state.get("case_id", "")
    team = state.get("routed_to", "Customer Service - Tier 1")

    lines = [
        f"Case {case_id} is waiting for a person.",
        "",
        f"Type      {cls.request_type.value.replace('_', ' ')}",
        f"Priority  {cls.urgency.value}",
        f"Subject   {state.get('subject') or '(none)'}",
        f"Received  {state.get('received_at', '')[:16].replace('T', ' ')}",
        f"Due by    {state.get('sla_due_at', '')[:16].replace('T', ' ')}",
        "",
        "Why it stopped:",
    ]
    lines += [f"  - {r}" for r in reasons] or ["  - held by policy"]

    vulns = [v.value.replace("_", " ") for v in cls.vulnerability_signals if v.value != "none"]
    if vulns:
        lines += [
            "",
            f"The customer has disclosed {', '.join(vulns)}.",
            "Handle personally. Do not send a standard reply. Automatic responses are disabled",
            "on this case and a draft is waiting in the console for you to review.",
        ]
    else:
        lines += ["", "A draft reply is waiting in the console for review before anything is sent."]

    lines += ["", "Nothing has been sent to the customer."]

    prefix = "ACTION NEEDED" if alert else "For review"
    subject = f"[{prefix}] {cls.request_type.value.replace('_', ' ').title()} — {case_id}"

    return Notification(
        channel="alert" if alert else "queue",
        to=team,
        subject=subject,
        body="\n".join(lines),
        raised_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )