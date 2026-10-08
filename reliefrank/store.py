"""
SQLite storage for cases and raw messages. One row per case, stored as JSON.
"""
import json
import sqlite3
import threading
import uuid
from datetime import datetime

import config
from reliefrank.models import Case

_lock = threading.Lock()


def _connect():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with _lock, _connect() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS cases (
                           case_id TEXT PRIMARY KEY,
                           score INTEGER,
                           status TEXT,
                           needs_call INTEGER,
                           received_at TEXT,
                           data TEXT)""")
        con.execute("""CREATE TABLE IF NOT EXISTS messages (
                           message_id TEXT PRIMARY KEY,
                           case_id TEXT,
                           text TEXT,
                           received_at TEXT)""")


def new_case_id() -> str:
    return "c_" + uuid.uuid4().hex[:8]


def new_message_id() -> str:
    return "m_" + uuid.uuid4().hex[:8]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def save_case(case: Case) -> Case:
    with _lock, _connect() as con:
        con.execute("""INSERT OR REPLACE INTO cases
                       (case_id, score, status, needs_call, received_at, data)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (case.case_id, case.score, case.status, int(case.needs_call),
                     case.received_at, json.dumps(case.to_dict(), ensure_ascii=False)))
        for mid, txt in zip(case.message_ids, case.raw_texts):
            con.execute("INSERT OR IGNORE INTO messages VALUES (?, ?, ?, ?)",
                        (mid, case.case_id, txt, case.received_at))
    return case


def get_case(case_id: str):
    with _lock, _connect() as con:
        row = con.execute("SELECT data FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    return Case.from_dict(json.loads(row["data"])) if row else None


def list_cases(status: str = None) -> list:
    """Highest score first, older first on ties. status='needs call' also matches needs_call=1."""
    q = "SELECT data FROM cases"
    args = ()
    if status == "needs call":
        q += " WHERE needs_call = 1 AND status NOT IN ('assigned', 'resolved')"
    elif status:
        q += " WHERE status = ?"
        args = (status,)
    q += " ORDER BY score DESC, received_at ASC"
    with _lock, _connect() as con:
        rows = con.execute(q, args).fetchall()
    return [Case.from_dict(json.loads(r["data"])) for r in rows]


def open_cases() -> list:
    """Cases still waiting for help (used by dedupe)."""
    return [c for c in list_cases() if c.status not in ("resolved",)]


def update_status(case_id: str, status: str):
    case = get_case(case_id)
    if case is None:
        return None
    case.status = status
    return save_case(case)


def clear_all() -> None:
    with _lock, _connect() as con:
        con.execute("DELETE FROM cases")
        con.execute("DELETE FROM messages")
