"""Run every sample request and write a per-branch output log.

Produces data/sample_outputs/ — one readable log per branch type, satisfying the
brief's requirement for sample inputs with corresponding outputs.
"""
import pathlib
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from workflow.graph import process

ROOT = pathlib.Path(__file__).resolve().parent
SAMPLES = ROOT / "data" / "sample_requests"
OUT = ROOT / "data" / "sample_outputs"


def parse(path: pathlib.Path):
    text = path.read_text(encoding="utf-8").strip()
    subject = ""
    if text.lower().startswith("subject:"):
        first, _, rest = text.partition("\n")
        subject = first.split(":", 1)[1].strip()
        text = rest.strip()
    return subject, text


def write_log(path: pathlib.Path, subject: str, source: str, state: dict) -> None:
    cls = state["classification"]
    L = []
    L.append("=" * 78)
    L.append(f"SAMPLE OUTPUT — {source}")
    L.append("=" * 78)
    L.append("")
    L.append("INPUT")
    L.append("-" * 78)
    L.append(f"Subject: {subject}")
    L.append(f"Channel: {state.get('channel', 'email')}")
    L.append("")
    L.append(state.get("raw_text", "").strip())
    L.append("")
    L.append("PII REDACTION")
    L.append("-" * 78)
    found = state.get("pii_found", [])
    L.append(f"Identifiers tokenised before the model call: {', '.join(found) if found else 'none found'}")
    if found:
        L.append("Text as seen by the model:")
        L.append(state.get("redacted_text", "").strip())
    L.append("")
    L.append("CLASSIFICATION")
    L.append("-" * 78)
    L.append(f"Type        : {cls.request_type.value}")
    L.append(f"Urgency     : {cls.urgency.value}")
    L.append(f"Confidence  : {cls.confidence:.2f}")
    L.append(f"Sub-topic   : {cls.sub_topic}")
    L.append(f"Source      : {state.get('classifier_source')}")
    L.append(f"Reasoning   : {cls.rationale}")
    vulns = [v.value for v in cls.vulnerability_signals if v.value != "none"]
    L.append(f"Vulnerability signals: {', '.join(vulns) if vulns else 'none'}")
    if cls.entities:
        L.append("Entities extracted:")
        for k, v in cls.entities.items():
            L.append(f"  {k}: {v}")
    L.append("")
    L.append("ROUTING DECISION")
    L.append("-" * 78)
    L.append(f"Branch      : {state['branch']}")
    L.append(f"Assigned to : {state['routed_to']}")
    L.append(f"Auto-send   : {'NO — held for a person' if state.get('hold_for_human') else 'yes'}")
    for reason in state.get("hold_reasons", []):
        L.append(f"  ! {reason}")
    L.append("")
    L.append("REMEDIATION STEPS EXECUTED")
    L.append("-" * 78)
    for i, a in enumerate(state["actions"], 1):
        L.append(f"{i}. {a.step}")
        L.append(f"   {a.detail}")
        if a.output:
            L.append(f"   -> {a.output}")
    L.append("")
    L.append("GENERATED DRAFT REPLY")
    L.append("-" * 78)
    L.append(state.get("draft_response", "").strip())
    L.append("")
    L.append("CASE RECORD")
    L.append("-" * 78)
    L.append(f"Case ID     : {state['case_id']}")
    L.append(f"Status      : {state['status']}")
    L.append(f"SLA due     : {state.get('sla_due_at', '—')}")
    L.append("")
    L.append("AUDIT TRAIL")
    L.append("-" * 78)
    for e in state.get("audit", []):
        L.append(f"[{e['ts']}] {e['node']}")
        L.append(f"    decision: {e['decision']}")
        if e.get("detail"):
            L.append(f"    detail  : {e['detail']}")
    L.append("")
    L.append("=" * 78)
    L.append(f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    path.write_text("\n".join(L))


def main() -> None:
    OUT.mkdir(exist_ok=True)
    files = sorted(SAMPLES.glob("*.txt"))
    print(f"Processing {len(files)} sample requests…\n")
    for path in files:
        subject, text = parse(path)
        state = process(text, subject=subject, channel="email")
        out_path = OUT / path.name.replace(".txt", "_output.txt")
        write_log(out_path, subject, path.name, state)
        held = "HELD" if state.get("hold_for_human") else "auto"
        print(f"  {path.name:<32} -> {state['branch']:<16} {held:<5} {out_path.name}")
    print(f"\nWritten to {OUT}")


if __name__ == "__main__":
    main()