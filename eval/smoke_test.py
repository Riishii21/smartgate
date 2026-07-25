"""Exercise every branch end to end with a stubbed LLM.

Runs without an API key so the graph, router, and all four branches can be
verified independently of model availability.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from services import llm

CANNED = {
    "dispute": {"request_type": "billing_dispute", "urgency": "high", "confidence": 0.93,
                "sub_topic": "duplicate charge", "vulnerability_signals": ["none"],
                "entities": {"amount": "£84.99", "merchant": "Northgate Electronics", "transaction_date": "2026-07-12"},
                "rationale": "Customer contests a specific duplicate transaction."},
    "enquiry": {"request_type": "general_enquiry", "urgency": "low", "confidence": 0.91,
                "sub_topic": "balance transfer timescale", "vulnerability_signals": ["none"],
                "entities": {}, "rationale": "Asks for information only."},
    "service": {"request_type": "service_request", "urgency": "medium", "confidence": 0.88,
                "sub_topic": "address change", "vulnerability_signals": ["none"],
                "entities": {"requested_action": "update address", "new_address": "14 Mill Lane, Leeds LS6 2AB"},
                "rationale": "Administrative action requested."},
    "service_gap": {"request_type": "service_request", "urgency": "medium", "confidence": 0.86,
                    "sub_topic": "address change", "vulnerability_signals": ["none"],
                    "entities": {"requested_action": "update address"}, "rationale": "New address not supplied."},
    "complaint": {"request_type": "complaint", "urgency": "critical", "confidence": 0.9,
                  "sub_topic": "repeated service failure", "vulnerability_signals": ["bereavement"],
                  "entities": {}, "rationale": "Dissatisfaction with prior handling."},
    "ambiguous": {"request_type": "general_enquiry", "urgency": "low", "confidence": 0.41,
                  "sub_topic": "unclear", "vulnerability_signals": ["none"],
                  "entities": {}, "rationale": "Message mixes two request types."},
}

SAMPLES = {
    "dispute": ("Duplicate charge", "I was charged twice for £84.99 at Northgate Electronics on my card 4539 1488 0343 6467. Please refund. Call 07700 900123."),
    "enquiry": ("Balance transfer", "How long does a balance transfer usually take to complete?"),
    "service": ("Address change", "I have moved to 14 Mill Lane, Leeds LS6 2AB. Please update the address on my card ending 6467."),
    "service_gap": ("Address change", "I have moved house. Please update my address on the card ending 6467."),
    "complaint": ("Still unresolved", "This is the third time I have written. My husband passed away in May and nobody has actioned anything. It is unacceptable."),
    "ambiguous": ("Question", "Hi, wondering about a charge, also can you send a statement? Thanks."),
}

_current = {"key": "dispute"}
llm.complete_json = lambda system, user, temperature=0.0: CANNED[_current["key"]]
llm.complete = lambda system, user, temperature=0.3, max_tokens=350: ""  # force template fallback

from workflow.graph import process

print(f"{'case':<11}{'branch':<17}{'status':<26}{'hold':<6}{'steps':<7}routed to")
print("-" * 96)
failures = []
for key, (subject, text) in SAMPLES.items():
    _current["key"] = key
    try:
        s = process(text, subject=subject, channel="email")
        print(f"{key:<11}{s['branch']:<17}{s['status']:<26}{str(s.get('hold_for_human')):<6}{len(s['actions']):<7}{s['routed_to']}")
        if len(s["actions"]) < 2:
            failures.append(f"{key}: fewer than 2 downstream steps")
        if not s.get("audit"):
            failures.append(f"{key}: empty audit trail")
    except Exception as exc:
        failures.append(f"{key}: raised {type(exc).__name__}: {exc}")
        print(f"{key:<11}FAILED  {exc}")

print()
print("FAILURES:", failures if failures else "none")
