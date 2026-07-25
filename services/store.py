"""SQLite case store and append-only audit trail."""
import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    received_at TEXT,
    channel TEXT,
    subject TEXT,
    request_type TEXT,
    urgency TEXT,
    confidence REAL,
    classifier_source TEXT,
    branch TEXT,
    routed_to TEXT,
    hold_for_human INTEGER,
    hold_reasons TEXT,
    status TEXT,
    sla_due_at TEXT,
    draft_response TEXT,
    actions TEXT,
    customer_message TEXT
);
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT,
    ts TEXT,
    node TEXT,
    decision TEXT,
    detail TEXT
);
"""


@contextmanager
def _conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create the schema, and add any column introduced after a database existed."""
    with _conn() as conn:
        conn.executescript(SCHEMA)
        existing = {r["name"] for r in conn.execute("PRAGMA table_info(cases)")}
        for column, ddl in [("customer_message", "TEXT")]:
            if column not in existing:
                conn.execute(f"ALTER TABLE cases ADD COLUMN {column} {ddl}")


def save_case(state: Dict[str, Any]) -> None:
    cls = state.get("classification")
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO cases VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                state["case_id"], state.get("received_at", ""), state.get("channel", ""),
                state.get("subject", ""),
                cls.request_type.value if cls else "", cls.urgency.value if cls else "",
                cls.confidence if cls else 0.0, state.get("classifier_source", ""),
                state.get("branch", ""), state.get("routed_to", ""),
                int(bool(state.get("hold_for_human"))),
                json.dumps(state.get("hold_reasons", [])),
                state.get("status", ""), state.get("sla_due_at", ""),
                state.get("draft_response", ""),
                json.dumps([a.model_dump() for a in state.get("actions", [])]),
                state.get("raw_text", ""),
            ),
        )
        for event in state.get("audit", []):
            conn.execute(
                "INSERT INTO audit_events (case_id, ts, node, decision, detail) VALUES (?,?,?,?,?)",
                (state["case_id"], event["ts"], event["node"], event["decision"], event.get("detail", "")),
            )


def all_cases() -> List[Dict[str, Any]]:
    with _conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM cases ORDER BY received_at DESC")]


def audit_for(case_id: str) -> List[Dict[str, Any]]:
    with _conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM audit_events WHERE case_id=? ORDER BY id", (case_id,))]


def approve_case(case_id: str) -> None:
    with _conn() as conn:
        conn.execute("UPDATE cases SET status='approved_and_sent', hold_for_human=0 WHERE case_id=?", (case_id,))
        conn.execute(
            "INSERT INTO audit_events (case_id, ts, node, decision, detail) VALUES (?, datetime('now'), 'human_review', 'approved', 'Agent approved held output')",
            (case_id,),
        )