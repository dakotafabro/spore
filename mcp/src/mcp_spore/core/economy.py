"""Fuel economy for agent sessions: what a session spent per deliverable.

Reported as consumption per outcome (tokens per deliverable), the way liters
per 100 km is, rather than outcomes per token the way MPG is. Ratios like MPG
make savings hard to judge (Larrick and Soll, "The MPG Illusion", Science,
2008); consumption per outcome shows the most wasteful sessions as the
biggest gains.

Spend comes from goose's usage_ledger, one row per model request. Idle is the
preamble paid on every request (system prompt, policy, tool schemas),
estimated as the smallest input of any request in the session times the
number of requests. Forms (asks) and amends (rework) are reported beside the
ratio, not in it. Deliverables come from spore's deposition log and from what the session's
tools produced: issues and PRs, commits, merges, comments, replies, reviews,
decision forms, Linear issues and comments, published notes, Drive docs and new files. Cost is
read live from goose and never written to spore's logs. Whether issues and PRs
were kept is checked against GitHub only when asked (KeptChecker); everything
else here stays on this machine.
"""

import json
import os
import re
import sqlite3
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any

from mcp_spore.core.io import file_exists, read_csv
from mcp_spore.core.session import goose_db_path

DELIVERABLE_TYPES = (
    "creation", "issue", "commit", "pr", "merge", "doc", "draft", "review", "comment", "reply", "form", "message", "other",
)
WINDOW_SESSION_TYPES = ("user", "acp")

GITHUB_ITEM = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/(issues|pull)/\d+")
COMMIT_LINE = re.compile(r"^\[[^\]\n]+ ([0-9a-f]{7,40})\]", re.MULTILINE)
CREATED_FILE = re.compile(r"^Created (/\S+)", re.MULTILINE)
COMMAND_START = r"(?:^|[;&|(\n])\s*"
CREATES_ITEM = re.compile(COMMAND_START + r"gh (?:issue|pr) create\b")
COMMITS = re.compile(COMMAND_START + r"git (?:-C \S+ )?commit\b([^;&|\n]*)")
MERGE_TARGET = re.compile(COMMAND_START + r"gh pr merge\s+([^\s-]\S*)")
REVIEWS = re.compile(COMMAND_START + r"gh pr review\b")
COMMENTS = re.compile(COMMAND_START + r"gh (?:issue|pr) comment\b")
FORMS = re.compile(COMMAND_START + r"trellis ask\b(?![^\n;&|]*\s-check\b)")
API_CALL = re.compile(COMMAND_START + r"gh api\b[^;&|\n]*")
API_WRITE_FLAG = re.compile(r"\s(?:-X\s*(?:POST|PATCH|PUT)|--method[ =](?:POST|PATCH|PUT)|-f|-F|--field|--raw-field|--input)\s")
API_READ_FLAG = re.compile(r"\s(?:-X\s*GET|--method[ =]GET)\b")
GRAPHQL_REPLY = re.compile(r"\b(addPullRequestReviewThreadReply|addPullRequestReviewComment|addComment)\b")
GRAPHQL_REVIEW = re.compile(r"\b(addPullRequestReview|submitPullRequestReview)\b")
POSTED_URL = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/(?:issues|pull)/\d+#(issuecomment|discussion_r|pullrequestreview)-?(\d+)")
REQUEST_ID = re.compile(r"^request (\S+)", re.MULTILINE)
DRIVE_WRITES = ("create", "insert", "update", "replace", "append", "batch", "write", "copy", "upload", "delete_text", "format")
FORM_FILE = re.compile(r"(?:^|/)(?:review-forms|decision-forms|forms)/.*\.json$")
SIDE_LINES = {"form": "asks", "amend": "amends"}
URL_KIND = {"issuecomment": "comment", "discussion_r": "reply", "pullrequestreview": "review"}
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


def _take(found: dict[str, str], keys: list[str], count: int, kind: str, fallback: str) -> None:
    """Record `count` deliverables of a kind, keyed by what the tool printed when it printed enough."""
    for i in range(count):
        found.setdefault(keys[i] if i < len(keys) else f"{fallback}:{i}", kind)


def _api_writes(command: str) -> tuple[int, int, int]:
    """REST writes, GraphQL replies and GraphQL reviews made by `gh api` calls in a command."""
    rest = replies = reviews = 0
    for call in API_CALL.findall(command):
        if "graphql" in call:
            continue
        if API_WRITE_FLAG.search(call + " ") and not API_READ_FLAG.search(call):
            rest += 1
    if re.search(r"gh api graphql", command) and "mutation" in command:
        replies = len(GRAPHQL_REPLY.findall(command))
        reviews = len(GRAPHQL_REVIEW.findall(command))
    return rest, replies, reviews


def _from_shell(found: dict[str, str], call_id: str, command: str, text: str) -> None:
    if CREATES_ITEM.search(command):
        for match in GITHUB_ITEM.finditer(text):
            found.setdefault(match.group(0), "issue" if match.group(1) == "issues" else "pr")
    commit_flags = COMMITS.findall(command)
    new_commits = sum(1 for flags in commit_flags if "--amend" not in flags)
    _take(found, [f"commit:{sha[:12]}" for sha in COMMIT_LINE.findall(text)], new_commits, "commit", f"commit:{call_id}")
    _take(found, [], len(commit_flags) - new_commits, "amend", f"amend:{call_id}")
    for target in MERGE_TARGET.findall(command):
        found.setdefault(f"merge:{target}", "merge")

    posted: dict[str, list[str]] = {"comment": [], "reply": [], "review": []}
    for match in POSTED_URL.finditer(text):
        posted[URL_KIND[match.group(1)]].append(match.group(0))
    rest, graphql_replies, graphql_reviews = _api_writes(command)
    comment_count = len(COMMENTS.findall(command))
    _take(found, posted["comment"], comment_count, "comment", f"comment:{call_id}")
    _take(found, [], len(REVIEWS.findall(command)), "review", f"review:{call_id}")
    _take(found, [], graphql_replies, "reply", f"reply:{call_id}")
    _take(found, [], graphql_reviews, "review", f"graphql-review:{call_id}")
    if rest:
        api_urls = posted["reply"] + posted["review"] + posted["comment"][comment_count:]
        api_urls += [f"reply:{n}" for n in re.findall(r'"id":\s*(\d+),\s*"in_reply_to_id"', text)]
        for url in api_urls[:rest]:
            kind = "reply" if url.startswith("reply:") or "#discussion_r" in url else "review" if "#pullrequestreview" in url else "comment"
            found.setdefault(url, kind)
    forms = len(FORMS.findall(command))
    _take(found, [f"form:{r}" for r in REQUEST_ID.findall(text)], forms, "form", f"form:{call_id}")


def _from_tool(found: dict[str, str], call_id: str, name: str, args: dict, text: str) -> None:
    short = name.rsplit("__", 1)[-1]
    if short == "write":
        for path in CREATED_FILE.findall(text):
            if not path.startswith(SCRATCH_PREFIXES) and not FORM_FILE.search(path):
                found.setdefault(path, "creation")
    elif short == "save_issue" and re.search(r'"action":\s*"created"', text):
        ident = re.search(r'"identifier":\s*"([^"]+)"', text)
        found.setdefault(f"linear:{ident.group(1) if ident else call_id}", "issue")
    elif short == "add_comment" and re.search(r'"success":\s*true', text):
        ident = re.search(r'"id":\s*"([^"]+)"', text)
        found.setdefault(f"linear-comment:{ident.group(1) if ident else call_id}", "comment")
    elif short == "notes_publish" and not re.search(r'"refused":\s*true', text):
        stored = re.search(r'stored at ([^"\s]+)', text)
        found.setdefault(f"note:{stored.group(1) if stored else args.get('plan_id') or call_id}", "doc")
    elif "googledrive" in name.lower():
        operation = str(args.get("operation") or args.get("action") or short).lower()
        if any(word in operation for word in DRIVE_WRITES):
            target = args.get("document_id_or_url") or args.get("file_id") or args.get("spreadsheet_id") or args.get("presentation_id") or call_id
            found.setdefault(f"drive:{target}", "doc")


def derived_deliverables(session_id: str, db_path: Path | None = None) -> dict[str, str]:
    """Deliverables read from what the session's tools actually produced, keyed so each counts once.

    Only successful calls count. Issues and PRs count when `gh issue create` or `gh pr create`
    printed their URL; commits once per `git commit` that isn't an amend, keyed by the sha when it printed one; merges when `gh pr merge` ran.
    Comments, replies and reviews count once per `gh issue/pr comment`, `gh pr review`, writing
    `gh api` call or GraphQL mutation, keyed by the URL the call printed when it printed one.
    Forms count per `trellis ask`, Linear issues and comments when the tool reports creating them,
    notes when published, Drive docs once per document written, and files when the write tool
    created them outside scratch directories.
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
        args = args if isinstance(args, dict) else {}
        command = str(args.get("command", ""))
        if name.rsplit("__", 1)[-1] == "shell" and command:
            _from_shell(found, call_id, command, text)
        else:
            _from_tool(found, call_id, name, args, text)
    return found


def session_outputs(session_id: str, log_path: Path, db_path: Path | None = None) -> dict[str, str]:
    """Everything the session and its subagents produced, keyed so each counts once, with its kind."""
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
    return keyed


def session_deliverables(session_id: str, log_path: Path, db_path: Path | None = None) -> dict[str, int]:
    """Counts by kind of what the session produced, asks (forms) and amends included."""
    counts: dict[str, int] = {}
    for kind in session_outputs(session_id, log_path, db_path).values():
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


def fuel_economy(usage: dict[str, Any] | None, outputs: dict[str, int], not_kept: int = 0) -> dict[str, Any]:
    """Tokens and cost per deliverable, with idle, asks (forms) and amends (rework) as their own lines.

    Asks and amends stay out of the ratio: a form asks for a decision and an amend reworks a commit,
    so counting either would make a session look more efficient for asking or redoing.
    """
    deliverables = {k: v for k, v in outputs.items() if k not in SIDE_LINES}
    side = {SIDE_LINES[k]: outputs.get(k, 0) for k in SIDE_LINES}
    count = sum(deliverables.values())
    if usage is None:
        return {"status": "no_usage", "message": "goose's usage_ledger has no requests for this session.", "deliverables": count, **side}

    result: dict[str, Any] = {
        "deliverables": count,
        "deliverables_by_type": deliverables,
        "asks": side["asks"],
        "rework": {
            "amends": side["amends"],
            "amends_per_deliverable": round(side["amends"] / count, 2) if count else None,
        },
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
        result["message"] = "Tokens spent with no deliverable yet (forms and amends don't count), so there is no per-deliverable figure."
        return result

    result["status"] = "ok"
    result["tokens_per_deliverable"] = round(usage["total_tokens"] / count)
    result["idle_tokens_per_deliverable"] = round(usage["idle_tokens"] / count)
    if usage["cost"] is not None:
        result["cost_per_deliverable"] = round(usage["cost"] / count, 4)
    if not_kept:
        result["not_kept"] = not_kept
        result["tokens_per_deliverable_less_not_kept"] = round(usage["total_tokens"] / (count - not_kept)) if count > not_kept else None
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


def window_summary(
    session_ids: list[str],
    log_path: Path,
    db_path: Path | None = None,
    kept_checker: "KeptChecker | None" = None,
) -> dict[str, Any]:
    """Fuel economy across sessions: median tokens per deliverable, asks, rework and sessions with none."""
    sessions = []
    without = 0
    tokens_without = 0
    asks = amends = 0
    kept_totals = {"kept": 0, "not_kept": 0, "pending": 0, "not_checked": 0}
    for sid in session_ids:
        usage = session_usage(sid, db_path)
        if usage is None:
            continue
        outputs = session_outputs(sid, log_path, db_path)
        counts: dict[str, int] = {}
        for kind in outputs.values():
            counts[kind] = counts.get(kind, 0) + 1
        not_kept = 0
        if kept_checker is not None:
            for key, kind in outputs.items():
                if kind in SIDE_LINES:
                    continue
                state = kept_checker.state(key, kind)
                kept_totals[state] += 1
                not_kept += state == "not_kept"
        economy = fuel_economy(usage, counts, not_kept)
        asks += economy.get("asks", 0)
        amends += economy.get("rework", {}).get("amends", 0)
        if economy["status"] == "no_deliverables":
            without += 1
            tokens_without += usage["total_tokens"]
            continue
        entry = {
            "session_id": sid,
            "deliverables": economy["deliverables"],
            "deliverables_by_type": economy["deliverables_by_type"],
            "asks": economy["asks"],
            "amends": economy["rework"]["amends"],
            "tokens_per_deliverable": economy["tokens_per_deliverable"],
            "idle_share": economy["tokens"]["idle_share"],
        }
        if not_kept:
            entry["not_kept"] = not_kept
        sessions.append(entry)

    per = [s["tokens_per_deliverable"] for s in sessions]
    idle = [s["idle_share"] for s in sessions if s["idle_share"] is not None]
    delivered = sum(s["deliverables"] for s in sessions)
    summary: dict[str, Any] = {
        "sessions_with_deliverables": len(sessions),
        "sessions_without_deliverables": without,
        "tokens_in_sessions_without_deliverables": tokens_without,
        "median_tokens_per_deliverable": round(statistics.median(per)) if per else None,
        "median_idle_share": round(statistics.median(idle), 3) if idle else None,
        "deliverables": delivered,
        "asks": asks,
        "rework": {"amends": amends, "amends_per_deliverable": round(amends / delivered, 2) if delivered else None},
        "sessions": sorted(sessions, key=lambda s: s["tokens_per_deliverable"], reverse=True),
    }
    if kept_checker is not None:
        decided = kept_totals["kept"] + kept_totals["not_kept"]
        summary["kept"] = {
            **kept_totals,
            "kept_share_of_checked": round(kept_totals["kept"] / decided, 3) if decided else None,
            "checks": "GitHub PRs (merged is kept, closed unmerged is not) and issues (closed as not planned or duplicate is not kept); other kinds are not checked",
        }
    return summary


ISSUE_OR_PR = re.compile(r"^https://github\.com/([\w.-]+)/([\w.-]+)/(issues|pull)/(\d+)$")
FINAL_STATES = ("kept", "not_kept")


class KeptChecker:
    """Asks GitHub, through `gh`, whether issues and PRs were kept. Used only when asked for.

    Results that can't change (merged, closed) are cached outside the repo so a weekly check
    repeats only the open ones. Every other kind of deliverable is reported as not checked.
    """

    def __init__(self, cache_path: Path | None = None, runner: Any = None, max_lookups: int = 300):
        self.cache_path = cache_path or Path(os.environ.get("SPORE_STATE_DIR", str(Path.home() / ".local" / "state" / "spore"))) / "kept-cache.json"
        self.runner = runner or self._gh
        self.max_lookups = max_lookups
        self.lookups = 0
        try:
            self.cache: dict[str, str] = json.loads(self.cache_path.read_text())
        except (OSError, ValueError):
            self.cache = {}

    @staticmethod
    def _gh(path: str, jq: str) -> str | None:
        try:
            result = subprocess.run(["gh", "api", path, "--jq", jq], capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return result.stdout.strip() if result.returncode == 0 else None

    def state(self, key: str, kind: str) -> str:
        match = ISSUE_OR_PR.match(key)
        if kind not in ("pr", "issue") or not match:
            return "not_checked"
        if key in self.cache:
            return self.cache[key]
        if self.lookups >= self.max_lookups:
            return "not_checked"
        self.lookups += 1
        owner, repo, section, number = match.groups()
        if section == "pull":
            out = self.runner(f"repos/{owner}/{repo}/pulls/{number}", '"\\(.state) \\(.merged_at != null)"')
            if out is None:
                return "not_checked"
            state = "kept" if out.endswith("true") else "not_kept" if out.startswith("closed") else "pending"
        else:
            out = self.runner(f"repos/{owner}/{repo}/issues/{number}", '"\\(.state) \\(.state_reason)"')
            if out is None:
                return "not_checked"
            state = "not_kept" if out.startswith("closed") and out.split()[-1] in ("not_planned", "duplicate") else "kept"
        if state in FINAL_STATES and not (section == "issues" and out.startswith("open")):
            self.cache[key] = state
        return state

    def save(self) -> None:
        if not self.cache:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache, indent=0, sort_keys=True))
