"""Shared helpers for remediation branches."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import config
from services import llm
from workflow.schemas import Action

DRAFT_SYSTEM = """You draft customer replies for a UK retail bank's card servicing team.
Write in plain British English, warm but concise, maximum 120 words.
Never promise an outcome, refund, or timescale that was not given to you.
Never invent reference numbers, amounts, or policy. Identifiers appear as tokens
like [CARD_1]; reproduce them exactly as written. Sign off as 'Card Services'."""


def draft(instruction: str, context: str, fallback: str) -> str:
    """Generate a reply, degrading to a fixed template if the LLM is unavailable."""
    try:
        text = llm.complete(DRAFT_SYSTEM, f"{instruction}\n\nCustomer message:\n{context}", temperature=0.3, max_tokens=350)
        return text.strip() or fallback
    except Exception:
        return fallback


def audit(state: Dict[str, Any], node: str, decision: str, detail: str = "") -> List[Dict[str, Any]]:
    return state.get("audit", []) + [{
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "node": node,
        "decision": decision,
        "detail": detail,
    }]


def sla_due(request_type: str) -> str:
    minutes = config.SLA_MINUTES.get(request_type, 24 * 60)
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat(timespec="seconds")


def status_for(state: Dict[str, Any], auto_status: str) -> str:
    return "pending_human_approval" if state.get("hold_for_human") else auto_status


def act(step: str, detail: str, output: str = "") -> Action:
    return Action(step=step, detail=detail, output=output)
