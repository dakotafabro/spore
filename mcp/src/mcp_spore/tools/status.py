import json
from typing import Any

from mcp_spore.core.config import load_config, load_trust_state, resolve_repo_root
from mcp_spore.core.io import file_exists, read_csv
from mcp_spore.core.session import current_session_id, rows_for, tokens_spent


def _summarize_trust_state(trust_state: dict[str, Any]) -> dict[str, Any]:
    trust_levels = trust_state.get("trust_levels", {})
    if trust_levels:
        categories = {}
        for name, data in trust_levels.items():
            if isinstance(data, dict):
                categories[name] = {
                    "level": data.get("current_level", data.get("level", 2)),
                    "confirmations": data.get("consecutive_confirmations", 0),
                    "threshold": data.get("threshold_for_level_3"),
                }
        return {"format": "trust_levels", "categories": categories}

    return {
        "format": "simple",
        "level": trust_state.get("level", "observe"),
        "escalations": len(trust_state.get("escalations", [])),
    }


def spore_status_impl() -> str:
    """Retrieval stats, trust state, and proximity graph summary for the current repo."""
    repo_root = resolve_repo_root()
    config = load_config(repo_root)

    retrieval_path = str(repo_root / ".retrieval-log.csv")
    graph_path = str(repo_root / ".proximity-graph.csv")

    if not file_exists(retrieval_path):
        return json.dumps({
            "status": "uninitialized",
            "message": "No .retrieval-log.csv found. Run spore_init to set up spore in this repo.",
            "repo_root": str(repo_root),
        }, indent=2)

    retrievals = read_csv(retrieval_path)
    trust_state = load_trust_state(repo_root)

    unique_files = len({r.get("file", "") for r in retrievals if r.get("file", "")})
    unique_sessions = len({r.get("session_id", "") for r in retrievals if r.get("session_id", "")})

    graph_edges = []
    if file_exists(graph_path):
        graph_edges = read_csv(graph_path)

    top_files: dict[str, int] = {}
    for r in retrievals:
        f = r.get("file", "")
        if f:
            top_files[f] = top_files.get(f, 0) + 1
    sorted_files = sorted(top_files.items(), key=lambda x: x[1], reverse=True)[:10]

    result: dict[str, Any] = {
        "status": "active",
        "repo_root": str(repo_root),
        "phase": config.get("phase", "unknown"),
        "retrieval_stats": {
            "total_retrievals": len(retrievals),
            "unique_files": unique_files,
            "unique_sessions": unique_sessions,
            "top_files": [{"file": f, "count": c} for f, c in sorted_files],
        },
        "trust_state": _summarize_trust_state(trust_state),
        "graph_summary": {
            "edges": len(graph_edges),
            "top_connections": graph_edges[:5] if graph_edges else [],
        },
    }

    return json.dumps(result, indent=2)


def spore_sense_impl() -> str:
    """Resource state for this goose session, counted from the logs and goose's sessions.db."""
    repo_root = resolve_repo_root()
    session_id = current_session_id()
    retrieval_path = repo_root / ".retrieval-log.csv"
    total_retrievals = len(read_csv(str(retrieval_path))) if file_exists(str(retrieval_path)) else 0

    if not session_id:
        return json.dumps({
            "status": "no_session",
            "message": "AGENT_SESSION_ID is not set, so this server can't tell which session it belongs to.",
            "repo_root": str(repo_root),
            "total_retrievals_all_time": total_retrievals,
        }, indent=2)

    tokens = tokens_spent(session_id)
    result = {
        "session_id": session_id,
        "repo_root": str(repo_root),
        "retrievals_this_session": rows_for(retrieval_path, session_id),
        "tokens_spent_estimate": tokens if tokens is not None else 0,
        "tokens_source": "goose sessions.db" if tokens is not None else "unavailable",
        "deliverables_this_session": rows_for(repo_root / ".deposition-log.csv", session_id),
        "total_retrievals_all_time": total_retrievals,
    }

    return json.dumps(result, indent=2)
