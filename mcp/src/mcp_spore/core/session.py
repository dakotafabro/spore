"""The goose session this spore server belongs to, and what it has done.

goose starts one spore MCP server per session and sets AGENT_SESSION_ID in
its environment; the hooks get the same id in their payload. Counts come
from the logs and from goose's sessions.db, so they are per session even
when several sessions run at once.
"""

import os
import re
import sqlite3
from pathlib import Path

from mcp_spore.core.io import file_exists, read_csv

SESSION_ID = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
DEFAULT_GOOSE_DB = Path.home() / ".local" / "share" / "goose" / "sessions" / "sessions.db"


def current_session_id() -> str:
    """The goose session id from AGENT_SESSION_ID, or "" when unset or malformed."""
    value = os.environ.get("AGENT_SESSION_ID", "")
    return value if SESSION_ID.match(value) else ""


def goose_db_path() -> Path:
    return Path(os.environ.get("SPORE_GOOSE_DB", str(DEFAULT_GOOSE_DB)))


def tokens_spent(session_id: str, db_path: Path | None = None) -> int | None:
    """Total tokens goose recorded for the session, or None when unknown."""
    db_path = db_path or goose_db_path()
    if not session_id or not db_path.exists():
        return None
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2)
        try:
            row = con.execute(
                "select coalesce(accumulated_total_tokens, total_tokens) from sessions where id = ?",
                (session_id,),
            ).fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return None
    if row is None or row[0] is None:
        return None
    return int(row[0])


def rows_for(log_path: Path, session_id: str) -> int:
    """How many rows of a spore CSV log belong to the session."""
    if not session_id or not file_exists(str(log_path)):
        return 0
    return sum(1 for r in read_csv(str(log_path)) if r.get("session_id") == session_id)
