import math
from datetime import date, datetime
from typing import Any

from mcp_spore.core.io import read_csv


def compute_base_strength(retrieval_count: int) -> float:
    return min(2.0, 1.0 + (retrieval_count - 1) * 0.1)


def compute_strength(retrieval_count: int, days_since_last: float, decay_rate: float = 0.03) -> float:
    base = compute_base_strength(retrieval_count)
    return base * math.exp(-decay_rate * days_since_last)


def compute_all_decay_scores(
    retrieval_log_path: str,
    decay_rate: float = 0.03,
    reference_date: date | None = None,
) -> list[dict[str, Any]]:
    if reference_date is None:
        reference_date = date.today()

    rows = read_csv(retrieval_log_path)
    if not rows:
        return []

    file_stats: dict[str, dict[str, Any]] = {}
    for row in rows:
        file_path = row.get("file", "")
        if not file_path:
            continue

        date_str = row.get("date", "")
        try:
            row_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue

        if file_path not in file_stats:
            file_stats[file_path] = {"count": 0, "last_retrieval": row_date}
        file_stats[file_path]["count"] += 1
        if row_date > file_stats[file_path]["last_retrieval"]:
            file_stats[file_path]["last_retrieval"] = row_date

    results = []
    for file_path, stats in file_stats.items():
        days_since = (reference_date - stats["last_retrieval"]).days
        strength = compute_strength(stats["count"], days_since, decay_rate)
        results.append({
            "file": file_path,
            "retrieval_count": stats["count"],
            "last_retrieval": stats["last_retrieval"].isoformat(),
            "days_since_last": days_since,
            "strength": round(strength, 4),
        })

    results.sort(key=lambda x: x["strength"])
    return results
