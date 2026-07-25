"""General enquiry: knowledge-base lookup -> grounded answer -> auto-resolve."""
from typing import Any, Dict

from services.kb import search
from workflow.branches.common import act, audit, draft, sla_due, status_for


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    cls = state["classification"]
    query = f"{cls.sub_topic} {state.get('subject', '')}".strip()

    # Step 1 - retrieve grounding material.
    hits = search(query or state.get("redacted_text", ""), top_k=2)
    if hits:
        grounding = "\n\n".join(f"{h['title']}: {h['body']}" for h in hits)
        detail = f"Matched {len(hits)} article(s): " + ", ".join(h["title"] for h in hits)
    else:
        grounding = ""
        detail = "No knowledge-base match found"
    actions = [act("Knowledge-base lookup", detail, hits[0]["title"] if hits else "no_match")]

    # Step 2 - grounded draft. No match means no auto-resolution.
    if not hits:
        body = ("Thank you for your message. We are looking into your question and will reply shortly.\n\nCard Services")
        actions.append(act("Draft response", "No grounding available; holding for agent", "held"))
        queue, status_key = "Customer Service - Tier 1", "pending_human_approval"
    else:
        body = draft(
            "Answer the customer's question using only the reference material below. "
            "If the material does not cover it, say the query has been passed to an adviser.\n\n"
            f"Reference material:\n{grounding}",
            state.get("redacted_text", ""),
            f"{hits[0]['body']}\n\nCard Services",
        )
        actions.append(act("Draft response", "Answer grounded in knowledge base", body[:160] + ("..." if len(body) > 160 else "")))
        queue, status_key = "Auto-resolved", "auto_resolved"

    # Step 3 - log outcome.
    actions.append(act("Log outcome", f"Case marked {status_key}", status_key))

    due = sla_due("general_enquiry")
    return {
        "actions": actions,
        "draft_response": body,
        "routed_to": queue,
        "sla_due_at": due,
        "status": status_for(state, status_key),
        "audit": audit(state, "branch:enquiry", f"3 steps executed, outcome {status_key}", detail),
    }
