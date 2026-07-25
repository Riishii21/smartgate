"""Typed contracts between the LLM and the rest of the system.

The classifier is the only place an LLM decides anything. Everything downstream
consumes this validated object, so a malformed model response can never reach
the routing logic.
"""
from enum import Enum
from typing import Dict, List

from pydantic import BaseModel, Field, model_validator


class RequestType(str, Enum):
    BILLING_DISPUTE = "billing_dispute"
    GENERAL_ENQUIRY = "general_enquiry"
    SERVICE_REQUEST = "service_request"
    COMPLAINT = "complaint"


class Urgency(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class VulnerabilitySignal(str, Enum):
    """Signals that a customer may need a trained human rather than automation.

    Detection is used purely as a routing decision. The system never attempts to
    advise on or act upon the underlying circumstance.
    """
    NONE = "none"
    BEREAVEMENT = "bereavement"
    FINANCIAL_HARDSHIP = "financial_hardship"
    HEALTH_CONDITION = "health_condition"
    SEVERE_DISTRESS = "severe_distress"


class Classification(BaseModel):
    request_type: RequestType
    urgency: Urgency
    confidence: float = Field(ge=0.0, le=1.0)
    sub_topic: str = ""
    vulnerability_signals: List[VulnerabilitySignal] = Field(default_factory=list)
    entities: Dict[str, str] = Field(default_factory=dict)
    rationale: str = ""

    @model_validator(mode="before")
    @classmethod
    def _tolerate_model_quirks(cls, data):
        """Normalise predictable near-misses before validation.

        A language model asked for a constrained value will occasionally answer
        with something adjacent: a number where a string was specified, an
        unlisted vulnerability term, a list inside an entity field. Rejecting the
        whole classification for that discards an otherwise correct answer and
        drops the case to keyword matching, so this boundary is deliberately
        tolerant of near-misses rather than strict.
        """
        if not isinstance(data, dict):
            return data
        d = dict(data)

        try:
            d["confidence"] = max(0.0, min(1.0, float(d.get("confidence", 0.0))))
        except (TypeError, ValueError):
            d["confidence"] = 0.0

        allowed = {e.value for e in VulnerabilitySignal}
        signals = d.get("vulnerability_signals")
        if isinstance(signals, str):
            signals = [signals]
        if isinstance(signals, list):
            kept = [v for v in signals if isinstance(v, str) and v in allowed]
            d["vulnerability_signals"] = kept or ["none"]
        else:
            d["vulnerability_signals"] = ["none"]

        entities = d.get("entities")
        if isinstance(entities, dict):
            flat = {}
            for k, v in entities.items():
                if v is None:
                    continue
                flat[str(k)] = ", ".join(str(x) for x in v) if isinstance(v, (list, tuple)) else str(v)
            d["entities"] = flat
        else:
            d["entities"] = {}

        for key in ("sub_topic", "rationale"):
            if key in d and not isinstance(d[key], str):
                d[key] = "" if d[key] is None else str(d[key])

        return d

    @property
    def is_vulnerable(self) -> bool:
        return any(v != VulnerabilitySignal.NONE for v in self.vulnerability_signals)


class Action(BaseModel):
    """One executed remediation step. This is what an ops team actually reads."""
    step: str
    detail: str
    output: str = ""