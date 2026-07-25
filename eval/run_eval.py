"""Measure the triage pipeline against the labelled dataset.

Two modes:
  default  classification + gate only  (1 LLM call per case, fast, for prompt iteration)
  --full   the whole graph             (2 calls per case, verifies branch trajectory)

Reports type accuracy, urgency accuracy, gate behaviour, and -- most importantly --
vulnerability recall, which is the metric that must not regress.
"""
import argparse
import json
import pathlib
import sys
import time
from collections import Counter, defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from workflow.nodes.classify import classify
from workflow.nodes.intake import intake, redact_pii
from workflow.router import gate

DATASET = pathlib.Path(__file__).resolve().parent / "dataset.jsonl"
REPORT = pathlib.Path(__file__).resolve().parent / "report.md"
URGENCY_ORDER = ["low", "medium", "high", "critical"]
TYPES = ["billing_dispute", "general_enquiry", "service_request", "complaint"]
BRANCH_OF = {"billing_dispute": "dispute", "general_enquiry": "enquiry",
             "service_request": "service_request", "complaint": "complaint"}


def classify_only(text: str, subject: str) -> dict:
    state = {"raw_text": text, "subject": subject, "channel": "email", "audit": []}
    state.update(intake(state))
    state.update(redact_pii(state))
    state.update(classify(state))
    state.update(gate(state))
    return state


def run_full(text: str, subject: str) -> dict:
    from workflow.graph import process
    return process(text, subject=subject)


def bar(value: float, width: int = 24) -> str:
    filled = int(round(value * width))
    return "#" * filled + "." * (width - filled)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="run the whole graph including branches")
    ap.add_argument("--limit", type=int, default=0, help="only run the first N cases")
    ap.add_argument("--sleep", type=float, default=0.0, help="seconds between calls, for rate limits")
    ap.add_argument("--stop-on-fallback", type=int, default=0,
                    help="abort after this many consecutive fallbacks (0 = never), so a quota wall\n                         does not silently poison the whole report")
    args = ap.parse_args()

    rows = [json.loads(line) for line in DATASET.read_text().splitlines() if line.strip()]
    if args.limit:
        rows = rows[:args.limit]

    results, confusion = [], defaultdict(Counter)
    started = time.time()

    for i, row in enumerate(rows, 1):
        t0 = time.time()
        try:
            state = run_full(row["text"], row["subject"]) if args.full else classify_only(row["text"], row["subject"])
            cls = state["classification"]
            got = {
                "type": cls.request_type.value,
                "urgency": cls.urgency.value,
                "confidence": cls.confidence,
                "vulnerable": cls.is_vulnerable,
                "hold": bool(state.get("hold_for_human")),
                "branch": state.get("branch", ""),
                "steps": len(state.get("actions", [])),
                "source": state.get("classifier_source", ""),
                "error": "",
            }
        except Exception as exc:
            got = {"type": "", "urgency": "", "confidence": 0.0, "vulnerable": False,
                   "hold": False, "branch": "", "steps": 0, "source": "error", "error": str(exc)[:80]}

        got["latency"] = time.time() - t0
        results.append({**row, "got": got})

        if args.stop_on_fallback:
            recent = [r["got"]["source"] for r in results[-args.stop_on_fallback:]]
            if len(recent) == args.stop_on_fallback and all(s != "llm" for s in recent):
                print(f"\n  Aborting: {args.stop_on_fallback} consecutive fallbacks -- "
                      "quota is likely exhausted. Re-run when it resets.")
                print("  No report written; your previous report.md is untouched.")
                return
        confusion[row["expected_type"]][got["type"] or "ERROR"] += 1

        mark = "ok " if got["type"] == row["expected_type"] else "MISS"
        print(f"[{i:>3}/{len(rows)}] {mark} {row['id']}  {row['expected_type']:<16} -> {got['type']:<16} "
              f"conf={got['confidence']:.2f} hold={'Y' if got['hold'] else 'n'}")
        if args.sleep:
            time.sleep(args.sleep)

    elapsed = time.time() - started
    n = len(results)
    scored = [r for r in results if not r["ambiguous"]]   # ambiguous cases judged on hold, not label

    type_hits = sum(r["got"]["type"] == r["expected_type"] for r in scored)
    urg_exact = sum(r["got"]["urgency"] == r["expected_urgency"] for r in scored)
    urg_near = sum(
        r["got"]["urgency"] in URGENCY_ORDER
        and abs(URGENCY_ORDER.index(r["got"]["urgency"]) - URGENCY_ORDER.index(r["expected_urgency"])) <= 1
        for r in scored)

    vuln_cases = [r for r in results if r["expected_vulnerable"]]
    vuln_detected = sum(r["got"]["vulnerable"] for r in vuln_cases)
    vuln_held = sum(r["got"]["hold"] for r in vuln_cases)
    false_vuln = sum(r["got"]["vulnerable"] and not r["expected_vulnerable"] for r in results)

    hold_tp = sum(r["got"]["hold"] and r["expected_hold"] for r in results)
    hold_fp = sum(r["got"]["hold"] and not r["expected_hold"] for r in results)
    hold_fn = sum(not r["got"]["hold"] and r["expected_hold"] for r in results)

    ambiguous_held = sum(r["got"]["hold"] for r in results if r["ambiguous"])
    fallbacks = sum(r["got"]["source"] != "llm" for r in results)
    errors = sum(bool(r["got"]["error"]) for r in results)
    branch_ok = sum(r["got"]["branch"] == BRANCH_OF.get(r["got"]["type"], "") for r in results if r["got"]["branch"])

    def pct(a, b):
        return (a / b * 100) if b else 0.0

    lines = []
    add = lines.append
    add(f"# Evaluation report\n")
    add(f"Mode: {'full graph' if args.full else 'classification + gate'} | cases: {n} "
        f"| wall clock: {elapsed:.1f}s | mean latency: {sum(r['got']['latency'] for r in results)/n:.2f}s\n")

    add("## Headline\n")
    add("| Metric | Value |")
    add("| --- | --- |")
    add(f"| Type accuracy (unambiguous, n={len(scored)}) | **{pct(type_hits, len(scored)):.1f}%** |")
    add(f"| Urgency exact | {pct(urg_exact, len(scored)):.1f}% |")
    add(f"| Urgency within one level | {pct(urg_near, len(scored)):.1f}% |")
    add(f"| Branch matches classification | {pct(branch_ok, n):.1f}% |")
    add(f"| Rules fallback used | {fallbacks} / {n} |")
    add(f"| Errors | {errors} |\n")

    add("## Safety\n")
    add("| Metric | Value | Target |")
    add("| --- | --- | --- |")
    add(f"| Vulnerability recall (detected) | {vuln_detected}/{len(vuln_cases)} ({pct(vuln_detected, len(vuln_cases)):.0f}%) | 100% |")
    add(f"| Vulnerable cases held for human | {vuln_held}/{len(vuln_cases)} ({pct(vuln_held, len(vuln_cases)):.0f}%) | 100% |")
    add(f"| False vulnerability flags | {false_vuln} | low |")
    add(f"| Ambiguous cases held | {ambiguous_held}/{sum(r['ambiguous'] for r in results)} | 100% |\n")
    add("Vulnerable cases held is the metric that must not regress. A missed detection means an\n"
        "automated reply was sent to someone who needed a trained handler.\n")

    add("## Gate behaviour\n")
    add(f"- Correctly held: {hold_tp}")
    add(f"- Held unnecessarily (cost: avoidable human time): {hold_fp}")
    add(f"- Not held but should have been (cost: risk): {hold_fn}")
    add(f"- Automation rate: {pct(n - hold_tp - hold_fp, n):.1f}% of cases actioned without a human\n")

    add("## Confusion matrix\n")
    add("Rows are expected, columns are predicted.\n")
    header = "| expected \\ got | " + " | ".join(t[:12] for t in TYPES) + " |"
    add(header)
    add("| --- " * (len(TYPES) + 1) + "|")
    for expected in TYPES:
        cells = " | ".join(str(confusion[expected].get(t, 0)) for t in TYPES)
        add(f"| {expected} | {cells} |")
    add("")

    add("## Per-type accuracy\n")
    for t in TYPES:
        subset = [r for r in scored if r["expected_type"] == t]
        hits = sum(r["got"]["type"] == t for r in subset)
        add(f"- `{t}` {pct(hits, len(subset)):5.1f}%  {bar(hits/len(subset) if subset else 0)}  ({hits}/{len(subset)})")
    add("")

    misses = [r for r in scored if r["got"]["type"] != r["expected_type"]]
    add(f"## Misclassifications ({len(misses)})\n")
    if misses:
        add("| id | expected | got | conf | held | note |")
        add("| --- | --- | --- | --- | --- | --- |")
        for r in misses:
            add(f"| {r['id']} | {r['expected_type']} | {r['got']['type'] or 'ERROR'} | "
                f"{r['got']['confidence']:.2f} | {'yes' if r['got']['hold'] else 'no'} | {r['note'] or '-'} |")
    else:
        add("None.")
    add("")

    REPORT.write_text("\n".join(lines))
    json.dump(results, open(REPORT.with_suffix(".json"), "w"), indent=2, default=str)

    print("\n" + "=" * 66)
    print(f"  Type accuracy       {pct(type_hits, len(scored)):.1f}%   ({type_hits}/{len(scored)})")
    print(f"  Urgency exact       {pct(urg_exact, len(scored)):.1f}%")
    print(f"  Vulnerable held     {vuln_held}/{len(vuln_cases)}   <- must be {len(vuln_cases)}/{len(vuln_cases)}")
    print(f"  Ambiguous held      {ambiguous_held}/{sum(r['ambiguous'] for r in results)}")
    print(f"  Automation rate     {pct(n - hold_tp - hold_fp, n):.1f}%")
    print(f"  Fallback / errors   {fallbacks} / {errors}")
    print("=" * 66)
    print(f"  Full report: {REPORT}")


if __name__ == "__main__":
    main()