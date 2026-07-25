"""Tiny keyword-scored knowledge base.

Deliberately not a vector store: ten articles do not justify an embedding
index, and a transparent scoring function is easier for an ops team to reason
about when an answer looks wrong.
"""
import json
import pathlib
import re
from typing import Any, Dict, List

_KB_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "kb" / "faq.json"
_STOPWORDS = {"the", "a", "an", "is", "are", "do", "does", "how", "what", "when", "my",
              "i", "to", "for", "of", "and", "can", "you", "it", "on", "in", "will"}


def _tokens(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z]+", text.lower()) if t not in _STOPWORDS and len(t) > 2]


def load() -> List[Dict[str, Any]]:
    if not _KB_PATH.exists():
        return []
    return json.loads(_KB_PATH.read_text())


def search(query: str, top_k: int = 2, min_score: int = 2) -> List[Dict[str, Any]]:
    q = set(_tokens(query))
    if not q:
        return []
    scored = []
    for article in load():
        haystack = set(_tokens(article["title"] + " " + article["body"] + " " + " ".join(article.get("tags", []))))
        score = len(q & haystack)
        if score >= min_score:
            scored.append((score, article))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [a for _, a in scored[:top_k]]
