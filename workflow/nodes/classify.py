"""Classification node: the single point where an LLM makes a decision.

Output is validated against the Classification schema. If the LLM is
unavailable or never returns valid JSON, a deterministic keyword classifier
takes over at low confidence, which guarantees the router sends the case to a
human rather than acting on a guess.
"""
from datetime import datetime, timezone
from typing import Any, Dict

from pydantic import ValidationError

import config
from services import llm
from workflow.schemas import Classification, RequestType, Urgency, VulnerabilitySignal

SYSTEM_PROMPT = """You are a triage classifier for a retail bank's card servicing operation.
You classify inbound customer messages. You never answer the customer.

Return a single JSON object with exactly these keys:
  request_type: one of billing_dispute, general_enquiry, service_request, complaint
  urgency: one of low, medium, high, critical
  confidence: float 0.0-1.0, your honest certainty in request_type
  sub_topic: short noun phrase, max 5 words
  vulnerability_signals: list from none, bereavement, financial_hardship, health_condition, severe_distress
  entities: flat object of extracted facts (amounts, dates, merchant, card_last_four)
  rationale: one sentence, max 25 words
  distinct_requests: integer, how many separate things the customer is asking you to do or answer
  alternative_type: the second most plausible request_type, or JSON null (not the string "none")

Definitions:
- billing_dispute: customer contests a specific charge or transaction they believe is wrong.
- general_enquiry: asks for information; no action needed on their account.
- service_request: asks the bank to perform an administrative action (replace card, change address, cancel).
- complaint: expresses dissatisfaction with the bank's service, conduct, or a prior failure to resolve.

A message can be angry without being a complaint. If the customer's core ask is a
specific wrong charge, it is a billing_dispute regardless of tone.

Urgency is judged on customer impact, not on tone:
- critical: suspected fraud or card compromise, or the customer discloses circumstances
  (bereavement, hardship, illness, acute distress) that mean they face immediate detriment.
- high: money is wrong, missing, or disputed, or the customer is raising a formal complaint
  about a service failure.
- medium: an account action is requested with no immediate financial impact.
- low: information only, with nothing to action on the account.

Count distinct_requests literally: "refund this charge and send me a statement" is 2.
A single ask with supporting detail is 1.

Set alternative_type only when you could genuinely defend either label on the evidence given,
so that a colleague reading the same message might reasonably choose the other one. If one
reading is clearly better, return null. Do not name an alternative merely because another
type is conceivable.

Set confidence below 0.75 when the message lacks the detail needed to be sure.
Under-confidence is safe; over-confidence is not.

Personal identifiers have been replaced with tokens like [CARD_1]. Treat them as opaque.

Flag vulnerability_signals only on explicit textual evidence, for example bereavement,
inability to afford essentials, a stated health condition, or acute distress. Use ["none"]
otherwise. This flag only routes the case to a trained human; never act on it yourself."""

KEYWORDS = {
    RequestType.BILLING_DISPUTE: ["charged twice", "double charge", "unauthorised", "unauthorized",
                                  "dispute", "did not make", "didn't make", "refund", "wrong amount",
                                  "fraudulent", "chargeback"],
    RequestType.SERVICE_REQUEST: ["replace", "new card", "change my address", "update my",
                                  "cancel", "close my account", "statement copy", "increase my limit"],
    RequestType.COMPLAINT: ["complaint", "unacceptable", "appalling", "third time", "no one has",
                            "still waiting", "poor service", "escalate", "ombudsman"],
    RequestType.GENERAL_ENQUIRY: ["how do i", "what is", "can you tell me", "when will",
                                  "do you offer", "interest rate", "how long does"],
}

VULNERABILITY_KEYWORDS = {
    VulnerabilitySignal.BEREAVEMENT: ["passed away", "died", "deceased", "bereave", "funeral", "late husband", "late wife"],
    VulnerabilitySignal.FINANCIAL_HARDSHIP: ["can't afford", "cannot afford", "lost my job", "redundant",
                                             "struggling to pay", "food bank", "in arrears"],
    VulnerabilitySignal.HEALTH_CONDITION: ["in hospital", "chemotherapy", "disability", "terminal", "carer for"],
    VulnerabilitySignal.SEVERE_DISTRESS: ["desperate", "at breaking point", "can't cope", "cannot cope"],
}

URGENCY_BY_TYPE = {
    RequestType.BILLING_DISPUTE: Urgency.HIGH,
    RequestType.GENERAL_ENQUIRY: Urgency.LOW,
    RequestType.SERVICE_REQUEST: Urgency.MEDIUM,
    RequestType.COMPLAINT: Urgency.CRITICAL,
}


def rules_fallback(text: str) -> Classification:
    """Deterministic keyword classifier. Always low confidence by design."""
    lowered = text.lower()
    scores = {rt: sum(1 for kw in kws if kw in lowered) for rt, kws in KEYWORDS.items()}
    best = max(scores, key=lambda k: scores[k])
    matched = scores[best]

    signals = [sig for sig, kws in VULNERABILITY_KEYWORDS.items()
               if any(kw in lowered for kw in kws)] or [VulnerabilitySignal.NONE]

    return Classification(
        request_type=best if matched else RequestType.GENERAL_ENQUIRY,
        urgency=URGENCY_BY_TYPE[best] if matched else Urgency.LOW,
        confidence=0.35 if matched else 0.2,
        sub_topic="keyword match" if matched else "unrecognised",
        vulnerability_signals=signals,
        entities={},
        rationale="Rules fallback used; LLM classification unavailable or invalid.",
    )


def classify(state: Dict[str, Any]) -> Dict[str, Any]:
    text = state.get("redacted_text", "")
    user_prompt = f"Channel: {state.get('channel', 'email')}\nSubject: {state.get('subject', '')}\n\nMessage:\n{text}"

    classification, source, detail = None, "rules_fallback", ""
    try:
        payload = llm.complete_json(SYSTEM_PROMPT, user_prompt)
        if payload is not None:
            try:
                classification = Classification(**payload)
                source, detail = "llm", "Schema-valid LLM classification"
            except ValidationError as exc:
                detail = f"Schema validation failed: {str(exc)[:90]}"
        else:
            detail = "LLM returned no parseable JSON after retries"
    except llm.LLMUnavailable as exc:
        detail = f"LLM unavailable: {exc}"

    if classification is None:
        classification = rules_fallback(text)

    return {
        "classification": classification,
        "classifier_source": source,
        "audit": state.get("audit", []) + [{
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "node": "classify",
            "decision": f"{classification.request_type.value} / {classification.urgency.value} "
                        f"(confidence {classification.confidence:.2f}, via {source})",
            "detail": detail or classification.rationale,
        }],
    }