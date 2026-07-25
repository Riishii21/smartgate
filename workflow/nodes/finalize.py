"""Terminal node: rehydrate the draft for the agent and persist the case."""
from datetime import datetime, timezone
from typing import Any, Dict

from services import notify, store
from services.redaction import rehydrate, strip_unresolved


def finalize(state: Dict[str, Any]) -> Dict[str, Any]:
    draft = strip_unresolved(rehydrate(state.get("draft_response", ""), state.get("pii_map", {})))
    status = state.get("status", "processed")

    audit = state.get("audit", []) + [{
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "node": "finalize",
        "decision": f"Case closed to status '{status}'",
        "detail": f"{len(state.get('actions', []))} remediation steps recorded",
    }]

    notification = None
    if state.get("hold_for_human"):
        notification = notify.compose({**state, "draft_response": draft})
        audit.append({
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "node": "notify",
            "decision": f"{notification.channel} notification raised to {notification.to}",
            "detail": notification.subject,
        })

    persisted = {**state, "draft_response": draft, "status": status, "audit": audit}
    try:
        store.init_db()
        store.save_case(persisted)
    except Exception as exc:
        audit.append({
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "node": "finalize",
            "decision": "persistence_failed",
            "detail": str(exc)[:120],
        })

    return {"draft_response": draft, "status": status, "audit": audit,
            "notification": notification.as_dict() if notification else None}