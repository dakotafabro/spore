import json
from typing import Any

from mcp_spore.core.config import PLUGIN_ROOT, load_config, load_trust_state, resolve_repo_root
from mcp_spore.core.io import file_exists, read_csv


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
    """Current session resource state from the plugin's session state file."""
    session_state_path = PLUGIN_ROOT / ".session-state"

    if not session_state_path.exists():
        return json.dumps({
            "status": "no_session",
            "message": "No active session state found. The hooks may not have fired yet this session.",
        }, indent=2)

    lines = session_state_path.read_text().strip().splitlines()

    session_id = lines[0] if len(lines) > 0 else "unknown"
    repo_root_str = lines[1] if len(lines) > 1 else str(resolve_repo_root())
    retrievals_this_session = int(lines[2]) if len(lines) > 2 else 0
    tokens_spent = int(lines[3]) if len(lines) > 3 else 0
    deliverables = int(lines[4]) if len(lines) > 4 else 0

    repo_root = resolve_repo_root()
    retrieval_path = str(repo_root / ".retrieval-log.csv")
    total_retrievals = len(read_csv(retrieval_path)) if file_exists(retrieval_path) else 0

    result = {
        "session_id": session_id,
        "repo_root": repo_root_str,
        "retrievals_this_session": retrievals_this_session,
        "tokens_spent_estimate": tokens_spent,
        "deliverables_this_session": deliverables,
        "total_retrievals_all_time": total_retrievals,
    }

    return json.dumps(result, indent=2)
