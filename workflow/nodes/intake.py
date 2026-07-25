"""Intake and PII redaction nodes."""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from services.redaction import redact


def intake(state: Dict[str, Any]) -> Dict[str, Any]:
    case_id = state.get("case_id") or f"CASE-{uuid.uuid4().hex[:8].upper()}"
    received = state.get("received_at") or datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "case_id": case_id,
        "received_at": received,
        "channel": state.get("channel", "email"),
        "status": "received",
        "audit": [{
            "ts": received,
            "node": "intake",
            "decision": f"Case {case_id} opened",
            "detail": f"channel={state.get('channel', 'email')}, {len(state.get('raw_text', ''))} chars",
        }],
    }


def redact_pii(state: Dict[str, Any]) -> Dict[str, Any]:
    redacted, pii_map, found = redact(state.get("raw_text", ""))
    return {
        "redacted_text": redacted,
        "pii_map": pii_map,
        "pii_found": found,
        "audit": state.get("audit", []) + [{
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "node": "redact_pii",
            "decision": f"{len(pii_map)} identifier(s) tokenised",
            "detail": f"kinds={', '.join(found) if found else 'none'}; raw PII not sent to model provider",
        }],
    }
