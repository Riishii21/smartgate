"""Graph state. Every node returns a partial dict that LangGraph merges in."""
from typing import Any, Dict, List, Optional, TypedDict

from workflow.schemas import Action, Classification


class TriageState(TypedDict, total=False):
    case_id: str
    received_at: str
    channel: str
    subject: str
    raw_text: str

    redacted_text: str
    pii_map: Dict[str, str]
    pii_found: List[str]

    classification: Optional[Classification]
    classifier_source: str          # "llm" or "rules_fallback"

    hold_for_human: bool
    hold_reasons: List[str]
    branch: str

    actions: List[Action]
    draft_response: str
    routed_to: str
    sla_due_at: str
    status: str

    notification: Optional[Dict[str, str]]
    audit: List[Dict[str, Any]]