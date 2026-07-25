"""PII redaction applied before any text leaves the process for an LLM API.

Tokens are reversible so generated drafts can be rehydrated for the human agent,
but the raw identifiers are never transmitted to the model provider.
"""
import re
from typing import Dict, List, Tuple

PATTERNS = [
    ("CARD", re.compile(r"\b\d(?:[ -]?\d){12,18}\b")),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")),
    ("PHONE", re.compile(r"(?<!\d)\+?\d(?:[ -]?\d){8,13}(?!\d)")),
    ("SORTCODE", re.compile(r"\b\d{2}-\d{2}-\d{2}\b")),
]


def redact(text: str) -> Tuple[str, Dict[str, str], List[str]]:
    """Return (redacted_text, token->original map, list of PII kinds found)."""
    pii_map: Dict[str, str] = {}
    found: List[str] = []
    counters: Dict[str, int] = {}

    def _sub(kind: str, match: re.Match) -> str:
        original = match.group(0)
        for token, existing in pii_map.items():
            if existing == original:
                return token
        counters[kind] = counters.get(kind, 0) + 1
        token = f"[{kind}_{counters[kind]}]"
        pii_map[token] = original
        if kind not in found:
            found.append(kind)
        return token

    redacted = text
    for kind, pattern in PATTERNS:
        redacted = pattern.sub(lambda m, k=kind: _sub(k, m), redacted)
    return redacted, pii_map, found


def rehydrate(text: str, pii_map: Dict[str, str]) -> str:
    for token, original in pii_map.items():
        text = text.replace(token, original)
    return text


STATED_LAST_FOUR = re.compile(r"(?:ending|ends with|last four|last 4)\D{0,8}(\d{4})\b", re.I)


def stated_last_four(text: str) -> str:
    """Pick up a last-4 the customer typed in plain text, e.g. 'card ending 6467'."""
    m = STATED_LAST_FOUR.search(text or "")
    return m.group(1) if m else ""


def last_four(pii_map: Dict[str, str]) -> str:
    """Card last-4 for display, derived without exposing the full number."""
    for token, original in pii_map.items():
        if token.startswith("[CARD"):
            digits = re.sub(r"\D", "", original)
            if len(digits) >= 4:
                return digits[-4:]
    return ""


UNRESOLVED = re.compile(r"\s*(?:ending|number|no\.?|ref(?:erence)?)?\s*\[[A-Z]+_\d+\]", re.I)


def strip_unresolved(text: str) -> str:
    """Remove redaction tokens the model invented with no matching original.

    The drafting prompt tells the model that identifiers appear as tokens, so it
    sometimes emits one even when the source message contained no PII. A stray
    placeholder must never reach a customer.
    """
    return UNRESOLVED.sub("", text)