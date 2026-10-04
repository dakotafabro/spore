import json
from datetime import datetime

from mcp_spore.core.config import resolve_repo_root
from mcp_spore.core.io import append_csv_row, file_exists, read_csv


INTEROCEPTION_FIELDS = [
    "timestamp",
    "session_id",
    "context_remaining_pct",
    "retrievals",
    "tokens_spent",
    "deliverables",
    "efficiency_vs_baseline",
    "agent_observation",
]

RETRIEVAL_FIELDS = ["date", "session_id", "file", "context"]
DEPOSITION_FIELDS = ["date", "session_id", "file", "context", "type"]


def spore_log_interoception_impl(
    context_remaining_pct: float,
    retrievals: int,
    tokens_spent: int,
    deliverables: int,
    efficiency_vs_baseline: str,
    agent_observation: str,
    session_id: str = "",
) -> str:
    """Log the agent's self-observed resource state at a natural transition point."""
    repo_root = resolve_repo_root()
    log_path = str(repo_root / ".interoception-log.csv")

    if not file_exists(log_path):
        return json.dumps({
            "status": "error",
            "message": "No .interoception-log.csv found. Run spore_init first.",
        }, indent=2)

    if not session_id:
        today = datetime.now().strftime("%Y-%m-%d")
        session_id = f"{today}-session"

    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "session_id": session_id,
        "context_remaining_pct": str(context_remaining_pct),
        "retrievals": str(retrievals),
        "tokens_spent": str(tokens_spent),
        "deliverables": str(deliverables),
        "efficiency_vs_baseline": efficiency_vs_baseline,
        "agent_observation": agent_observation,
    }

    append_csv_row(log_path, row, INTEROCEPTION_FIELDS)

    return json.dumps({
        "status": "logged",
        "timestamp": row["timestamp"],
        "session_id": session_id,
        "observation_preview": agent_observation[:100],
    }, indent=2)


def spore_log_deposition_impl(
    file_path: str,
    context: str = "",
    session_id: str = "",
) -> str:
    """Log a file creation (deposition into the knowledge substrate)."""
    repo_root = resolve_repo_root()
    log_path = str(repo_root / ".deposition-log.csv")

    today = datetime.now().strftime("%Y-%m-%d")
    if not session_id:
        session_id = f"{today}-session"

    row = {
        "date": today,
        "session_id": session_id,
        "file": file_path,
        "context": context,
        "type": "creation",
    }

    append_csv_row(log_path, row, DEPOSITION_FIELDS)

    return json.dumps({
        "status": "deposited",
        "date": today,
        "session_id": session_id,
        "file": file_path,
        "context": context or "(none)",
    }, indent=2)


def spore_log_retrieval_impl(
    file_path: str,
    context: str = "",
    session_id: str = "",
) -> str:
    """Manually log a file retrieval when hooks don't fire (e.g., Code Mode)."""
    repo_root = resolve_repo_root()
    log_path = str(repo_root / ".retrieval-log.csv")

    if not file_exists(log_path):
        return json.dumps({
            "status": "error",
            "message": "No .retrieval-log.csv found. Run spore_init first.",
        }, indent=2)

    today = datetime.now().strftime("%Y-%m-%d")
    if not session_id:
        session_id = f"{today}-manual"

    row = {
        "date": today,
        "session_id": session_id,
        "file": file_path,
        "context": context,
    }

    append_csv_row(log_path, row, RETRIEVAL_FIELDS)

    result = {
        "status": "logged",
        "date": today,
        "session_id": session_id,
        "file": file_path,
        "context": context or "(none)",
    }

    all_rows = read_csv(log_path)
    count = sum(1 for r in all_rows if r.get("file") == file_path)
    if count == 5:
        result["proposal_opportunity"] = {
            "category": "index_maintenance",
            "file": file_path,
            "retrieval_count": count,
            "suggestion": f"This file has been retrieved {count} times. Consider enriching its INDEX entry to reduce full-doc retrievals.",
        }

    return json.dumps(result, indent=2)
