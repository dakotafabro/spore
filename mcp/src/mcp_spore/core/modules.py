"""Module topology from router loads and file reads.

Joins agent-context-router load events with spore's retrieval log, groups
them by session, and proposes where each router module belongs. Proposals
are suggestions for a human to decide; nothing here edits the registry.
"""

import json
import os
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import yaml

from mcp_spore.core.io import read_csv

STATE_DIR = Path.home() / ".local" / "state" / "agent-context-router"
DEFAULT_REGISTRY = Path.home() / ".config" / "agent-context-router" / "modules.yaml"
DEFAULT_LOGS = [STATE_DIR / "loads.jsonl", STATE_DIR / "loads-backfill.jsonl"]


def registry_path() -> Path:
    return Path(os.environ.get("SPORE_ROUTER_REGISTRY") or DEFAULT_REGISTRY)


def log_paths() -> list[Path]:
    raw = os.environ.get("SPORE_ROUTER_LOGS")
    if raw:
        return [Path(p) for p in raw.split(os.pathsep) if p]
    return list(DEFAULT_LOGS)


def load_registry(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    repos = {
        name: Path(os.path.expanduser(spec.get("path", ""))).resolve()
        for name, spec in (raw.get("repos") or {}).items()
    }
    modules = {
        m["id"]: {"dir": m.get("dir"), "repo": m.get("repo"), "file": m.get("file"), "profile": m.get("profile")}
        for m in raw.get("modules") or []
    }
    return {"repos": repos, "modules": modules, "dirs": sorted((raw.get("dirs") or {}).keys())}


def read_load_events(paths: Iterable[Path]) -> list[dict[str, Any]]:
    events = []
    for p in paths:
        if not p.exists():
            continue
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return events


def collect_sessions(
    registry: dict[str, Any],
    events: list[dict[str, Any]],
    retrievals: list[dict[str, str]],
    repo_root: Path | None,
    since: float,
) -> tuple[dict[str, set[str]], dict[str, int]]:
    sessions: dict[str, set[str]] = defaultdict(set)
    counts = {"router_loads": 0, "router_loads_without_session": 0, "file_reads": 0}
    known = registry["modules"]

    for e in events:
        if e.get("event") != "load" or e.get("module") not in known:
            continue
        if float(e.get("ts", 0)) < since:
            continue
        sid = e.get("session")
        if not sid:
            counts["router_loads_without_session"] += 1
            continue
        sessions[sid].add(e["module"])
        counts["router_loads"] += 1

    if repo_root is not None:
        root = repo_root.resolve()
        by_file = {
            m["file"]: mid
            for mid, m in known.items()
            if m.get("file") and registry["repos"].get(m.get("repo")) == root
        }
        since_day = datetime.fromtimestamp(since).date()
        for r in retrievals:
            mid = by_file.get(r.get("file", ""))
            sid = r.get("session_id", "")
            if not mid or not sid:
                continue
            try:
                if date.fromisoformat(r.get("date", "")) < since_day:
                    continue
            except ValueError:
                continue
            sessions[sid].add(mid)
            counts["file_reads"] += 1

    return dict(sessions), counts


def propose(
    registry: dict[str, Any],
    sessions: dict[str, set[str]],
    exclude_dirs: tuple[str, ...] = ("shared",),
    min_sessions: int = 3,
    margin: float = 0.2,
    label_floor: float = 0.5,
    min_lift: float = 1.2,
) -> dict[str, Any]:
    modules = registry["modules"]
    excluded = {mid for mid, m in modules.items() if m.get("dir") in exclude_dirs}
    dirs = [d for d in registry["dirs"] if d not in exclude_dirs]
    members = {d: {mid for mid, m in modules.items() if m.get("dir") == d} for d in dirs}

    trimmed = {sid: mods - excluded for sid, mods in sessions.items()}
    trimmed = {sid: mods for sid, mods in trimmed.items() if mods}

    total = len(trimmed) or 1
    seen: dict[str, list[str]] = defaultdict(list)
    for sid, mods in trimmed.items():
        for mid in mods:
            seen[mid].append(sid)

    report: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []

    for mid in sorted(modules):
        if mid in excluded:
            continue
        own = modules[mid].get("dir")
        sids = seen.get(mid, [])
        n = len(sids)
        affinity = {}
        lift = {}
        for d in dirs:
            others = members[d] - {mid}
            if not others or not n:
                affinity[d] = 0.0
                lift[d] = 0.0
                continue
            hit = sum(1 for sid in sids if trimmed[sid] & others)
            affinity[d] = round(hit / n, 3)
            base = sum(1 for mods in trimmed.values() if mods & others) / total
            lift[d] = round(affinity[d] / base, 2) if base else 0.0
        entry = {"module": mid, "dir": own, "sessions": n, "affinity": affinity, "lift": lift}
        report.append(entry)

        if n == 0:
            proposals.append({
                "type": "never_loaded", "module": mid, "dir": own, "sessions": 0,
                "profile": modules[mid].get("profile"),
            })
            continue
        if n < min_sessions:
            continue
        best = max(dirs, key=lambda d: lift[d]) if dirs else None
        if best is None:
            continue
        rest = [lift[d] for d in dirs if d != best]
        clear = lift[best] >= min_lift and all(lift[best] >= r + margin for r in rest)
        detail = {"sessions": n, "affinity": affinity, "lift": lift}
        if own in dirs:
            if best != own and clear and affinity[best] >= label_floor:
                proposals.append({"type": "move", "module": mid, "from": own, "to": best, **detail})
        elif own is None:
            if clear and affinity[best] >= label_floor:
                proposals.append({"type": "label", "module": mid, "to": best, **detail})
            else:
                proposals.append({"type": "stay_unlabelled", "module": mid, **detail})

    return {
        "excluded_dirs": list(exclude_dirs),
        "excluded_modules": sorted(excluded),
        "sessions_used": len(trimmed),
        "modules": report,
        "proposals": proposals,
    }


def module_topology(
    repo_root: Path | None,
    window_days: int = 30,
    now: float | None = None,
) -> dict[str, Any]:
    reg_path = registry_path()
    if not reg_path.exists():
        return {"status": "no_registry", "registry": str(reg_path)}
    registry = load_registry(reg_path)
    now = time.time() if now is None else now
    since = now - window_days * 86400
    events = read_load_events(log_paths())
    retrievals = []
    if repo_root is not None:
        retrievals = read_csv(str(repo_root / ".retrieval-log.csv"))
    sessions, counts = collect_sessions(registry, events, retrievals, repo_root, since)
    result = propose(registry, sessions)
    return {
        "status": "ok",
        "window_days": window_days,
        "since": (datetime.fromtimestamp(now) - timedelta(days=window_days)).date().isoformat(),
        "registry": str(reg_path),
        "logs": [str(p) for p in log_paths() if p.exists()],
        "sources": counts,
        "sessions_seen": len(sessions),
        **result,
    }
