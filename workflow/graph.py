"""Graph assembly.

Flow: intake -> redact -> classify -> gate -> [one of four branches] -> finalize.
Branch selection is a conditional edge driven purely by the gate's output.
"""
from typing import Any, Dict

from langgraph.graph import END, START, StateGraph

from workflow.branches import complaint, dispute, enquiry, service_request
from workflow.nodes.classify import classify
from workflow.nodes.finalize import finalize
from workflow.nodes.intake import intake, redact_pii
from workflow.router import gate, select_branch
from workflow.state import TriageState

BRANCH_NODES = {
    "dispute": dispute.run,
    "enquiry": enquiry.run,
    "service_request": service_request.run,
    "complaint": complaint.run,
}


def build_graph():
    g = StateGraph(TriageState)

    g.add_node("intake", intake)
    g.add_node("redact", redact_pii)
    g.add_node("classify", classify)
    g.add_node("gate", gate)
    for name, fn in BRANCH_NODES.items():
        g.add_node(name, fn)
    g.add_node("finalize", finalize)

    g.add_edge(START, "intake")
    g.add_edge("intake", "redact")
    g.add_edge("redact", "classify")
    g.add_edge("classify", "gate")
    g.add_conditional_edges("gate", select_branch, {name: name for name in BRANCH_NODES})
    for name in BRANCH_NODES:
        g.add_edge(name, "finalize")
    g.add_edge("finalize", END)

    return g.compile()


_compiled = None


def process(raw_text: str, subject: str = "", channel: str = "email", case_id: str = "") -> Dict[str, Any]:
    """Run one request end to end and return the final state."""
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled.invoke({
        "raw_text": raw_text,
        "subject": subject,
        "channel": channel,
        "case_id": case_id,
        "actions": [],
        "audit": [],
    })
