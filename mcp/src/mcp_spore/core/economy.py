"""Fuel economy for agent sessions: what a session spent per deliverable.

Reported as consumption per outcome (tokens per deliverable), the way liters
per 100 km is, rather than outcomes per token the way MPG is. Ratios like MPG
make savings hard to judge (Larrick and Soll, "The MPG Illusion", Science,
2008); consumption per outcome shows the most wasteful sessions as the
biggest gains.

Spend comes from goose's usage_ledger, one row per model request. Idle is the
preamble paid on every request (system prompt, policy, tool schemas),
estimated as the smallest input of any request in the session times the
number of requests. Deliverables come from spore's deposition log and from what the session's
tools produced (issues and PRs created, commits, merges, new files). Cost is
read live from goose and never written to spore's logs.
"""

import json
import re
import sqlite3
import statistics
import time
from pathlib import Path
from typing import Any

from mcp_spore.core.io import file_exists, read_csv
from mcp_spore.core.session import goose_db_path

DELIVERABLE_TYPES = ("creation", "issue", "commit", "pr", "merge", "doc", "draft", "review", "other")
WINDOW_SESSION_TYPES = ("user", "acp")

GITHUB_ITEM = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/(issues|pull)/\d+")
COMMIT_LINE = re.compile(r"^\[[^\]\n]+ ([0-9a-f]{7,40})\]", re.MULTILINE)
CREATED_FILE = re.compile(r"^Created (/\S+)", re.MULTILINE)
COMMAND_START = r"(?:^|[;&|(\n])\s*"
CREATES_ITEM = re.compile(COMMAND_START + r"gh (?:issue|pr) create\b")
COMMITS = re.compile(COMMAND_START + r"git (?:-C \S+ )?commit\b")
MERGE_TARGET = re.compile(COMMAND_START + r"gh pr merge\s+([^\s-]\S*)")
SCRATCH_PREFIXES = ("/tmp/", "/private/tmp/", "/var/folders/")


def _connect(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2)


def session_family(session_id: str, db_path: Path | None = None) -> list[str]:
    """The session plus its subagent sessions, whose spend and output belong to it."""
    db_path = db_path or goose_db_path()
    family = [session_id]
    if not db_path.exists():
        return family
    try:
        con = _connect(db_path)
        try:
            rows = con.execute("select id from sessions where parent_session_id = ?", (session_id,)).fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return family
    return family + [r[0] for r in rows]


def _tool_calls(con: sqlite3.Connection, session_id: str) -> tuple[dict[str, tuple[str, dict]], dict[str, dict]]:
    requests: dict[str, tuple[str, dict]] = {}
    responses: dict[str, dict] = {}
    rows = con.execute(
        "select role, content_json from messages where session_id = ? and content_json like '%toolRe%'",
        (session_id,),
    ).fetchall()
    for role, content in rows:
        try:
            parts = json.loads(content)
        except (TypeError, ValueError):
            continue
        for part in parts if isinstance(parts, list) else []:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "toolRequest":
                value = (part.get("toolCall") or {}).get("value") or {}
                requests[part.get("id", "")] = (str(value.get("name", "")), value.get("arguments") or {})
            elif part.get("type") == "toolResponse":
                responses[part.get("id", "")] = (part.get("toolResult") or {}).get("value") or {}
    return requests, responses


def _response_text(value: dict) -> tuple[str, bool]:
    structured = value.get("structuredContent") or {}
    if "stdout" in structured:
        return str(structured.get("stdout", "")), structured.get("exit_code", 0) == 0 and not value.get("isError")
    text = "\n".join(c.get("text", "") for c in value.get("content") or [] if isinstance(c, dict))
    return text, not value.get("isError")


def derived_deliverables(session_id: str, db_path: Path | None = None) -> dict[str, str]:
    """Deliverables read from what the session's tools actually produced, keyed so each counts once.

    Counts an issue or PR only when a `gh issue create` or `gh pr create` call printed its URL,
    a commit only when `git commit` printed its sha, a merge only when `gh pr merge` exited 0,
    and a file only when the write tool reported creating it outside scratch directories.
    """
    db_path = db_path or goose_db_path()
    found: dict[str, str] = {}
    if not session_id or not db_path.exists():
        return found
    try:
        con = _connect(db_path)
        try:
            requests, responses = _tool_calls(con, session_id)
        finally:
            con.close()
    except sqlite3.Error:
        return found

    for call_id, (name, args) in requests.items():
        if call_id not in responses:
            continue
        text, ok = _response_text(responses[call_id])
        if not ok:
            continue
        command = str(args.get("command", "")) if isinstance(args, dict) else ""
        if name.endswith("shell") and command:
            if CREATES_ITEM.search(command):
                for match in GITHUB_ITEM.finditer(text):
                    found[match.group(0)] = "issue" if match.group(1) == "issues" else "pr"
            if COMMITS.search(command):
                for sha in COMMIT_LINE.findall(text):
                    found[f"commit:{sha[:12]}"] = "commit"
            if MERGE_TARGET.search(command):
                for target in MERGE_TARGET.findall(command):
                    found[f"merge:{target}"] = "merge"
        elif name.endswith("write"):
            for path in CREATED_FILE.findall(text):
                if not path.startswith(SCRATCH_PREFIXES):
                    found[path] = "creation"
    return found


def session_deliverables(session_id: str, log_path: Path, db_path: Path | None = None) -> dict[str, int]:
    """Logged deliverables plus derived ones from the session and its subagents, each counted once."""
    keyed: dict[str, str] = {}
    if session_id and file_exists(str(log_path)):
        for index, row in enumerate(read_csv(str(log_path))):
            if row.get("session_id") == session_id:
                kind = (row.get("type") or "creation").strip() or "creation"
                keyed[row.get("file") or f"logged:{index}"] = kind
    if session_id:
        for sid in session_family(session_id, db_path):
            for key, kind in derived_deliverables(sid, db_path).items():
                keyed.setdefault(key, kind)
    counts: dict[str, int] = {}
    for kind in keyed.values():
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def session_usage(session_id: str, db_path: Path | None = None) -> dict[str, Any] | None:
    """Token spend for one session from goose's usage_ledger, or None when unknown."""
    db_path = db_path or goose_db_path()
    if not session_id or not db_path.exists():
        return None
    family = session_family(session_id, db_path)
    try:
        con = _connect(db_path)
        try:
            rows = con.execute(
                "select coalesce(input_tokens, 0), coalesce(output_tokens, 0),"
                " coalesce(cache_read_tokens, 0), coalesce(cache_write_tokens, 0), cost, session_id"
                f" from usage_ledger where session_id in ({','.join('?' * len(family))})"
                " and coalesce(is_compaction, 0) = 0",
                family,
            ).fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return None
    if not rows:
        return None

    own = [r[0] for r in rows if r[5] == session_id] or [r[0] for r in rows]
    inputs = [r[0] for r in rows]
    costs = [r[4] for r in rows if r[4] is not None]
    preamble = min(own)
    input_tokens = sum(inputs)
    output_tokens = sum(r[1] for r in rows)
    return {
        "requests": len(rows),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cache_read_tokens": sum(r[2] for r in rows),
        "cache_write_tokens": sum(r[3] for r in rows),
        "fresh_input_tokens": max(input_tokens - sum(r[2] for r in rows), 0),
        "preamble_estimate": preamble,
        "idle_tokens": min(preamble * len(rows), input_tokens),
        "subagent_sessions": len(family) - 1,
        "cost": round(sum(costs), 4) if costs else None,
    }


def deliverables_for(log_path: Path, session_id: str) -> dict[str, int]:
    """Deliverables the session logged, counted by type."""
    counts: dict[str, int] = {}
    if not session_id or not file_exists(str(log_path)):
        return counts
    for row in read_csv(str(log_path)):
        if row.get("session_id") != session_id:
            continue
        kind = (row.get("type") or "creation").strip() or "creation"
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def fuel_economy(usage: dict[str, Any] | None, deliverables: dict[str, int]) -> dict[str, Any]:
    """Tokens and cost per deliverable, with idle shown as its own line."""
    count = sum(deliverables.values())
    if usage is None:
        return {"status": "no_usage", "message": "goose's usage_ledger has no requests for this session.", "deliverables": count}

    result: dict[str, Any] = {
        "deliverables": count,
        "deliverables_by_type": deliverables,
        "tokens": {
            "total": usage["total_tokens"],
            "input_fresh": usage["fresh_input_tokens"],
            "input_cache_read": usage["cache_read_tokens"],
            "output": usage["output_tokens"],
            "idle": usage["idle_tokens"],
            "idle_share": round(usage["idle_tokens"] / usage["input_tokens"], 3) if usage["input_tokens"] else None,
        },
        "requests": usage["requests"],
        "preamble_estimate": usage["preamble_estimate"],
        "cost_estimate": usage["cost"],
    }
    if count == 0:
        result["status"] = "no_deliverables"
        result["message"] = "Tokens spent with no deliverable logged yet, so there is no per-deliverable figure."
        return result

    result["status"] = "ok"
    result["tokens_per_deliverable"] = round(usage["total_tokens"] / count)
    result["idle_tokens_per_deliverable"] = round(usage["idle_tokens"] / count)
    if usage["cost"] is not None:
        result["cost_per_deliverable"] = round(usage["cost"] / count, 4)
    return result


def recent_session_ids(window_days: int, db_path: Path | None = None, now: float | None = None) -> list[str]:
    """User and ACP sessions with model requests inside the window, newest first.

    Subagent sessions fold into their parent; hidden sessions (titles and other goose internals) are left out.
    """
    db_path = db_path or goose_db_path()
    if not db_path.exists():
        return []
    since = (now if now is not None else time.time()) - window_days * 86400
    try:
        con = _connect(db_path)
        try:
            rows = con.execute(
                "select u.session_id, max(u.created_timestamp) as last from usage_ledger u"
                " join sessions s on s.id = u.session_id"
                f" where u.created_timestamp >= ? and s.session_type in ({','.join('?' * len(WINDOW_SESSION_TYPES))})"
                " and s.parent_session_id is null"
                " group by u.session_id order by last desc",
                (int(since), *WINDOW_SESSION_TYPES),
            ).fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return []
    return [r[0] for r in rows]


def window_summary(session_ids: list[str], log_path: Path, db_path: Path | None = None) -> dict[str, Any]:
    """Fuel economy across sessions: median tokens per deliverable, and sessions with none."""
    sessions = []
    without = 0
    tokens_without = 0
    for sid in session_ids:
        usage = session_usage(sid, db_path)
        if usage is None:
            continue
        economy = fuel_economy(usage, session_deliverables(sid, log_path, db_path))
        if economy["status"] == "no_deliverables":
            without += 1
            tokens_without += usage["total_tokens"]
            continue
        sessions.append({
            "session_id": sid,
            "deliverables": economy["deliverables"],
            "deliverables_by_type": economy["deliverables_by_type"],
            "tokens_per_deliverable": economy["tokens_per_deliverable"],
            "idle_share": economy["tokens"]["idle_share"],
        })

    per = [s["tokens_per_deliverable"] for s in sessions]
    idle = [s["idle_share"] for s in sessions if s["idle_share"] is not None]
    return {
        "sessions_with_deliverables": len(sessions),
        "sessions_without_deliverables": without,
        "tokens_in_sessions_without_deliverables": tokens_without,
        "median_tokens_per_deliverable": round(statistics.median(per)) if per else None,
        "median_idle_share": round(statistics.median(idle), 3) if idle else None,
        "sessions": sorted(sessions, key=lambda s: s["tokens_per_deliverable"], reverse=True),
    }
