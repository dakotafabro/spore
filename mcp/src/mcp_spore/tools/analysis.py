import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from mcp_spore.core.config import load_config, resolve_repo_root
from mcp_spore.core.decay import compute_all_decay_scores
from mcp_spore.core.graph import compute_proximity_graph
from mcp_spore.core.io import file_exists, read_csv


def spore_suggest_impl() -> str:
    """Data-driven topology recommendations based on retrieval patterns and co-retrieval graph."""
    repo_root = resolve_repo_root()
    config = load_config(repo_root)
    retrieval_path = str(repo_root / ".retrieval-log.csv")
    graph_path = str(repo_root / ".proximity-graph.csv")

    if not file_exists(retrieval_path):
        return json.dumps({
            "status": "no_data",
            "message": "No retrieval data found. Run spore_init and accumulate some retrieval history first.",
        }, indent=2)

    retrievals = read_csv(retrieval_path)
    if not retrievals:
        return json.dumps({
            "status": "no_data",
            "message": "Retrieval log is empty. Accumulate some retrieval history first.",
        }, indent=2)

    suggestions: list[dict[str, Any]] = []

    file_counts: dict[str, int] = {}
    for r in retrievals:
        f = r.get("file", "")
        if f:
            file_counts[f] = file_counts.get(f, 0) + 1

    hotspots = [(f, c) for f, c in file_counts.items() if c >= 5]
    hotspots.sort(key=lambda x: x[1], reverse=True)
    if hotspots:
        suggestions.append({
            "type": "retrieval_hotspots",
            "description": "Files retrieved 5+ times - consider holding in working context or improving INDEX summaries",
            "files": [{"file": f, "count": c} for f, c in hotspots[:10]],
        })

    dir_counts: dict[str, int] = defaultdict(int)
    for f in file_counts:
        parent = str(Path(f).parent)
        if parent != ".":
            dir_counts[parent] += file_counts[f]

    high_traffic_dirs = [(d, c) for d, c in dir_counts.items() if c >= 8]
    high_traffic_dirs.sort(key=lambda x: x[1], reverse=True)

    for dir_path, count in high_traffic_dirs[:5]:
        index_path = repo_root / dir_path / "INDEX.md"
        if not index_path.exists():
            suggestions.append({
                "type": "index_needed",
                "description": f"High-traffic directory ({count} retrievals) without INDEX.md",
                "directory": dir_path,
                "retrieval_count": count,
                "suggestion": f"Create INDEX.md in {dir_path} to reduce full-doc retrievals",
            })

    if file_exists(graph_path):
        graph_edges = read_csv(graph_path)
        if graph_edges:
            node_connections: dict[str, list[str]] = defaultdict(list)
            for edge in graph_edges:
                source = edge.get("source", "")
                target = edge.get("target", "")
                weight = float(edge.get("weight", "0"))
                if weight >= 2.0:
                    node_connections[source].append(target)
                    node_connections[target].append(source)

            clusters: list[set[str]] = []
            visited: set[str] = set()
            for node, neighbors in node_connections.items():
                if node in visited:
                    continue
                cluster = {node}
                queue = list(neighbors)
                while queue:
                    n = queue.pop()
                    if n in visited:
                        continue
                    visited.add(n)
                    cluster.add(n)
                    queue.extend(node_connections.get(n, []))
                visited.add(node)
                if len(cluster) >= 3:
                    clusters.append(cluster)

            for cluster in clusters[:5]:
                suggestions.append({
                    "type": "grouping_suggestion",
                    "description": "Strongly co-retrieved files - consider cross-referencing or shared tags",
                    "files": sorted(cluster),
                    "cluster_size": len(cluster),
                })

            bridge_nodes: list[tuple[str, int]] = []
            for node, neighbors in node_connections.items():
                dirs_connected = {str(Path(n).parent) for n in neighbors}
                if len(dirs_connected) >= 3:
                    bridge_nodes.append((node, len(dirs_connected)))

            bridge_nodes.sort(key=lambda x: x[1], reverse=True)
            if bridge_nodes:
                suggestions.append({
                    "type": "bridge_detection",
                    "description": "Files that bridge multiple directories - high-value connectors",
                    "bridges": [{"file": f, "directories_connected": d} for f, d in bridge_nodes[:5]],
                })

    decay_scores = compute_all_decay_scores(
        retrieval_path,
        decay_rate=config.get("decay_rate", 0.03),
    )
    threshold = config.get("consolidation_threshold", 0.3)
    stale = [s for s in decay_scores if s["strength"] < threshold]
    if stale:
        suggestions.append({
            "type": "consolidation_nudge",
            "description": f"{len(stale)} files below consolidation threshold ({threshold})",
            "count": len(stale),
            "sample": stale[:5],
            "action": "Run spore_consolidate for full list with decay details",
        })

    if not suggestions:
        suggestions.append({
            "type": "healthy",
            "description": "No topology issues detected. Retrieval patterns look balanced.",
        })

    return json.dumps({"suggestions": suggestions}, indent=2)


def spore_consolidate_impl() -> str:
    """Compute exponential decay for all tracked documents and return consolidation candidates."""
    repo_root = resolve_repo_root()
    config = load_config(repo_root)
    retrieval_path = str(repo_root / ".retrieval-log.csv")

    if not file_exists(retrieval_path):
        return json.dumps({
            "status": "no_data",
            "message": "No retrieval data found. Run spore_init first.",
        }, indent=2)

    decay_rate = config.get("decay_rate", 0.03)
    threshold = config.get("consolidation_threshold", 0.3)

    all_scores = compute_all_decay_scores(retrieval_path, decay_rate=decay_rate)

    candidates = [s for s in all_scores if s["strength"] < threshold]
    healthy = [s for s in all_scores if s["strength"] >= threshold]

    result = {
        "decay_rate": decay_rate,
        "consolidation_threshold": threshold,
        "total_tracked_files": len(all_scores),
        "candidates_below_threshold": len(candidates),
        "healthy_files": len(healthy),
        "candidates": candidates,
        "note": "These are candidates only. Spore never archives silently. Present to practitioner for confirmation.",
    }

    return json.dumps(result, indent=2)


def spore_graph_impl() -> str:
    """Regenerate proximity graph from co-retrieval data and return summary."""
    repo_root = resolve_repo_root()
    config = load_config(repo_root)
    retrieval_path = str(repo_root / ".retrieval-log.csv")
    graph_path = str(repo_root / ".proximity-graph.csv")

    if not file_exists(retrieval_path):
        return json.dumps({
            "status": "no_data",
            "message": "No retrieval data found. Run spore_init first.",
        }, indent=2)

    summary = compute_proximity_graph(
        retrieval_log_path=retrieval_path,
        output_path=graph_path,
        proximity_decay_days=config.get("proximity_decay_days", 60.0),
        prune_threshold=config.get("proximity_prune_threshold", 0.5),
    )

    result = {
        "status": "regenerated",
        "output_path": graph_path,
        "edges": summary["edges"],
        "nodes": summary["nodes"],
        "pruned_below_threshold": summary["pruned"],
        "top_edges": summary.get("top_edges", []),
    }

    return json.dumps(result, indent=2)
