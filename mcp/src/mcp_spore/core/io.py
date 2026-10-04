import csv
from pathlib import Path
from typing import Any


def file_exists(path: str) -> bool:
    return Path(path).exists()


def read_csv(path: str) -> list[dict[str, str]]:
    if not Path(path).exists():
        return []

    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_csv(path: str, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def append_csv_row(path: str, row: dict[str, str], fieldnames: list[str]) -> None:
    p = Path(path)
    write_header = not p.exists() or p.stat().st_size == 0

    p.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)
