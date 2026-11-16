#!/usr/bin/env python3
"""Backfill session-tagged router loads from goose's session database.

agent-context-router logs loads without a session before it learned to read
AGENT_SESSION_ID. Goose keeps every load_module tool call with its session, so
this rebuilds those events. It writes module ids, session ids and timestamps
only, never message content.

Usage: router_loads_from_goose.py [--days N] [--db PATH] [--out PATH]
"""

import argparse
import json
import re
import sqlite3
import time
from pathlib import Path

DEFAULT_DB = Path.home() / ".local" / "share" / "goose" / "sessions" / "sessions.db"
DEFAULT_OUT = Path.home() / ".local" / "state" / "agent-context-router" / "loads-backfill.jsonl"
CALL = re.compile(r'"name":"agent-context-router__load_module","arguments":\{"id":"([^"]+)"')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    since = time.time() - args.days * 86400
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows = con.execute(
        "select session_id, created_timestamp, content_json from messages "
        "where role = 'assistant' and created_timestamp > ? "
        "and content_json like '%agent-context-router__load_module%'",
        (since,),
    ).fetchall()

    seen = set()
    events = []
    for sid, ts, content in rows:
        for m in CALL.finditer(content):
            key = (sid, m.group(1))
            if key in seen:
                continue
            seen.add(key)
            events.append({"ts": float(ts), "event": "load", "module": m.group(1), "session": sid, "source": "goose-sessions"})

    events.sort(key=lambda e: e["ts"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
    tmp.replace(args.out)
    print(f"{len(events)} loads from {len({e['session'] for e in events})} sessions written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
