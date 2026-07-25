"""Run a single request through the graph and print the result.

Usage:
    python run_one.py data/sample_requests/01_billing_dispute.txt
    python run_one.py --all
    echo "my card was charged twice" | python run_one.py -
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from workflow.graph import process

SAMPLES_DIR = pathlib.Path(__file__).resolve().parent / "data" / "sample_requests"


def parse(path: pathlib.Path):
    """Split a leading 'Subject: ...' line off the sample file."""
    text = path.read_text(encoding="utf-8").strip()
    subject = ""
    if text.lower().startswith("subject:"):
        first, _, rest = text.partition("\n")
        subject = first.split(":", 1)[1].strip()
        text = rest.strip()
    return subject, text


def show(state, source: str) -> None:
    cls = state["classification"]
    print("=" * 78)
    print(f"SOURCE   {source}")
    print(f"CASE     {state['case_id']}   status: {state['status']}")
    print("-" * 78)
    print(f"TYPE     {cls.request_type.value}    URGENCY  {cls.urgency.value}")
    print(f"CONF     {cls.confidence:.2f}  (via {state['classifier_source']})")
    print(f"TOPIC    {cls.sub_topic}")
    print(f"WHY      {cls.rationale}")
    if cls.entities:
        print(f"ENTITIES {cls.entities}")
    vulns = [v.value for v in cls.vulnerability_signals if v.value != "none"]
    if vulns:
        print(f"VULN     {', '.join(vulns)}")
    if state.get("pii_found"):
        print(f"REDACTED {', '.join(state['pii_found'])}")
    print("-" * 78)
    print(f"BRANCH   {state['branch']}   ->  {state['routed_to']}")
    if state.get("hold_for_human"):
        print("HELD FOR HUMAN:")
        for reason in state.get("hold_reasons", []):
            print(f"   ! {reason}")
    print("STEPS:")
    for i, action in enumerate(state["actions"], 1):
        print(f"   {i}. {action.step}: {action.detail}")
    print("-" * 78)
    print("DRAFT RESPONSE:")
    for line in state.get("draft_response", "").splitlines():
        print(f"   {line}")
    print("=" * 78)
    print()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", help="path to a request file, or - for stdin")
    ap.add_argument("--all", action="store_true", help="run every file in data/sample_requests")
    args = ap.parse_args()

    if args.all:
        for path in sorted(SAMPLES_DIR.glob("*.txt")):
            subject, text = parse(path)
            show(process(text, subject=subject), path.name)
        return

    if not args.path:
        ap.error("give a file path, or --all")

    if args.path == "-":
        text = sys.stdin.read().strip()
        show(process(text, subject=""), "stdin")
    else:
        path = pathlib.Path(args.path)
        subject, text = parse(path)
        show(process(text, subject=subject), path.name)


if __name__ == "__main__":
    main()
