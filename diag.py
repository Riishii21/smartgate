"""Diagnose why classification is falling back.

Calls the API directly, without the retry-and-fallback wrapper, so the real
exception surfaces instead of being swallowed.
"""
import sys, json, pathlib, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

import config
from services import llm
from workflow.nodes.classify import SYSTEM_PROMPT
from workflow.schemas import Classification

print(f"model: {config.GROQ_MODEL}")
print(f"system prompt: {len(SYSTEM_PROMPT)} chars (~{len(SYSTEM_PROMPT)//4} tokens)\n")

CASES = [
    ("Change of address", "I have moved to 14 Mill Lane, Leeds LS6 2AB. Please update my address."),
    ("Duplicate charge", "I've been charged twice for the same order. Please refund the second one."),
    ("Third time writing", "This is the third time I have written and nobody has actioned anything."),
    ("Balance transfer", "How long does a balance transfer normally take?"),
    ("Lost card", "I've lost my card. Please block it and send a replacement."),
]

ok = 0
for i, (subject, text) in enumerate(CASES, 1):
    t0 = time.time()
    try:
        raw = llm.complete(SYSTEM_PROMPT, f"Channel: email\nSubject: {subject}\n\nMessage:\n{text}")
        payload = json.loads(llm._extract_json(raw))
        Classification(**payload)
        ok += 1
        print(f"[{i}/5] OK    {time.time()-t0:.2f}s  {payload['request_type']}  conf={payload.get('confidence')}")
    except Exception as exc:
        print(f"[{i}/5] FAIL  {time.time()-t0:.2f}s  {type(exc).__name__}")
        print(f"        {str(exc)[:400]}")

print(f"\n{ok}/5 succeeded.")
if ok < 5:
    print("\nIf the errors mention rate limits, quota, or 429, the code is fine and you have\n"
          "hit Groq's free-tier limit. Re-run the eval with --sleep 1.0, or wait for the\n"
          "window to reset.")