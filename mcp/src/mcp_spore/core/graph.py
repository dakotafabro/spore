import math
from collections import defaultdict
from datetime import date, datetime
from itertools import combinations
from typing import Any

from mcp_spore.core.io import read_csv, write_csv


def compute_proximity_graph(
    retrieval_log_path: str,
    output_path: str,
    proximity_decay_days: float = 60.0,
    prune_threshold: float = 0.5,
    reference_date: date | None = None,
) -> dict[str, Any]:
    if reference_date is None:
        reference_date = date.today()

    rows = read_csv(retrieval_log_path)
    if not rows:
        write_csv(output_path, [], ["source", "target", "weight", "last_co_retrieval", "sessions_shared"])
        return {"edges": 0, "nodes": 0, "pruned": 0}

    sessions: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        session_id = row.get("session_id", "")
        if session_id:
            sessions[session_id].append(row)

    edge_data: dict[tuple[str, str], dict[str, Any]] = {}

    for session_id, session_rows in sessions.items():
        files_in_session = list({row.get("file", "") for row in session_rows if row.get("file", "")})
        if len(files_in_session) < 2:
            continue

        session_dates = []
        for row in session_rows:
            try:
                session_dates.append(datetime.strptime(row.get("date", ""), "%Y-%m-%d").date())
            except (ValueError, TypeError):
                pass
        session_date = max(session_dates) if session_dates else reference_date

        for a, b in combinations(sorted(files_in_session), 2):
            edge_key = (a, b)
            if edge_key not in edge_data:
                edge_data[edge_key] = {
                    "sessions_shared": 0,
                    "last_co_retrieval": session_date,
                    "session_dates": [],
                }
            edge_data[edge_key]["sessions_shared"] += 1
            edge_data[edge_key]["session_dates"].append(session_date)
            if session_date > edge_data[edge_key]["last_co_retrieval"]:
                edge_data[edge_key]["last_co_retrieval"] = session_date

    decay_rate = math.log(2) / proximity_decay_days

    edges = []
    pruned_count = 0
    nodes: set[str] = set()

    for (source, target), data in edge_data.items():
        days_since = (reference_date - data["last_co_retrieval"]).days
        raw_weight = data["sessions_shared"]
        decayed_weight = raw_weight * math.exp(-decay_rate * days_since)

        if decayed_weight < prune_threshold:
            pruned_count += 1
            continue

        nodes.add(source)
        nodes.add(target)
        edges.append({
            "source": source,
            "target": target,
            "weight": round(decayed_weight, 3),
            "last_co_retrieval": data["last_co_retrieval"].isoformat(),
            "sessions_shared": str(data["sessions_shared"]),
        })

    edges.sort(key=lambda e: float(e["weight"]), reverse=True)
    write_csv(output_path, edges, ["source", "target", "weight", "last_co_retrieval", "sessions_shared"])

    return {
        "edges": len(edges),
        "nodes": len(nodes),
        "pruned": pruned_count,
        "top_edges": edges[:10],
    }
