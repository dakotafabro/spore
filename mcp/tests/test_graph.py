import math
from datetime import date

from mcp_spore.core.graph import compute_proximity_graph
from mcp_spore.core.io import read_csv, write_csv


RETRIEVAL_HEADERS = ["date", "file", "session_id"]
GRAPH_HEADERS = ["source", "target", "weight", "last_co_retrieval", "sessions_shared"]
REF_DATE = date(2026, 6, 1)


def _make_retrieval_log(tmp_path, rows):
    csv_path = str(tmp_path / "retrieval-log.csv")
    write_csv(csv_path, rows, RETRIEVAL_HEADERS)
    return csv_path


class TestComputeProximityGraph:
    def test_empty_log_produces_empty_graph(self, tmp_path):
        log_path = _make_retrieval_log(tmp_path, [])
        out_path = str(tmp_path / "graph.csv")
        result = compute_proximity_graph(log_path, out_path, reference_date=REF_DATE)
        assert result["edges"] == 0
        assert result["nodes"] == 0
        assert result["pruned"] == 0
        assert read_csv(out_path) == []

    def test_single_file_in_session_no_edges(self, tmp_path):
        log_path = _make_retrieval_log(tmp_path, [
            {"date": "2026-05-30", "file": "a.md", "session_id": "s1"},
        ])
        out_path = str(tmp_path / "graph.csv")
        result = compute_proximity_graph(log_path, out_path, reference_date=REF_DATE)
        assert result["edges"] == 0
        assert result["nodes"] == 0

    def test_two_files_in_session_one_edge(self, tmp_path):
        log_path = _make_retrieval_log(tmp_path, [
            {"date": "2026-06-01", "file": "a.md", "session_id": "s1"},
            {"date": "2026-06-01", "file": "b.md", "session_id": "s1"},
        ])
        out_path = str(tmp_path / "graph.csv")
        result = compute_proximity_graph(log_path, out_path, reference_date=REF_DATE)
        assert result["edges"] == 1
        assert result["nodes"] == 2

    def test_multiple_sessions_increase_weight(self, tmp_path):
        log_path = _make_retrieval_log(tmp_path, [
            {"date": "2026-06-01", "file": "a.md", "session_id": "s1"},
            {"date": "2026-06-01", "file": "b.md", "session_id": "s1"},
            {"date": "2026-06-01", "file": "a.md", "session_id": "s2"},
            {"date": "2026-06-01", "file": "b.md", "session_id": "s2"},
        ])
        out_path = str(tmp_path / "graph.csv")
        result = compute_proximity_graph(log_path, out_path, reference_date=REF_DATE)
        assert result["edges"] == 1
        edges = read_csv(out_path)
        assert float(edges[0]["weight"]) > 1.0

    def test_old_co_retrievals_decay_below_threshold(self, tmp_path):
        log_path = _make_retrieval_log(tmp_path, [
            {"date": "2025-01-01", "file": "a.md", "session_id": "s1"},
            {"date": "2025-01-01", "file": "b.md", "session_id": "s1"},
        ])
        out_path = str(tmp_path / "graph.csv")
        result = compute_proximity_graph(
            log_path, out_path,
            proximity_decay_days=60.0,
            prune_threshold=0.5,
            reference_date=REF_DATE,
        )
        assert result["edges"] == 0
        assert result["pruned"] == 1

    def test_output_csv_has_correct_columns(self, tmp_path):
        log_path = _make_retrieval_log(tmp_path, [
            {"date": "2026-06-01", "file": "x.md", "session_id": "s1"},
            {"date": "2026-06-01", "file": "y.md", "session_id": "s1"},
        ])
        out_path = str(tmp_path / "graph.csv")
        compute_proximity_graph(log_path, out_path, reference_date=REF_DATE)
        rows = read_csv(out_path)
        assert len(rows) == 1
        assert set(rows[0].keys()) == {"source", "target", "weight", "last_co_retrieval", "sessions_shared"}

    def test_top_edges_sorted_by_weight_descending(self, tmp_path):
        log_path = _make_retrieval_log(tmp_path, [
            {"date": "2026-06-01", "file": "a.md", "session_id": "s1"},
            {"date": "2026-06-01", "file": "b.md", "session_id": "s1"},
            {"date": "2026-06-01", "file": "a.md", "session_id": "s2"},
            {"date": "2026-06-01", "file": "b.md", "session_id": "s2"},
            {"date": "2026-06-01", "file": "a.md", "session_id": "s3"},
            {"date": "2026-06-01", "file": "b.md", "session_id": "s3"},
            {"date": "2026-06-01", "file": "c.md", "session_id": "s3"},
        ])
        out_path = str(tmp_path / "graph.csv")
        result = compute_proximity_graph(log_path, out_path, prune_threshold=0.0, reference_date=REF_DATE)
        top = result["top_edges"]
        weights = [float(e["weight"]) for e in top]
        assert weights == sorted(weights, reverse=True)

    def test_three_files_in_session_creates_three_edges(self, tmp_path):
        log_path = _make_retrieval_log(tmp_path, [
            {"date": "2026-06-01", "file": "a.md", "session_id": "s1"},
            {"date": "2026-06-01", "file": "b.md", "session_id": "s1"},
            {"date": "2026-06-01", "file": "c.md", "session_id": "s1"},
        ])
        out_path = str(tmp_path / "graph.csv")
        result = compute_proximity_graph(log_path, out_path, prune_threshold=0.0, reference_date=REF_DATE)
        assert result["edges"] == 3
        assert result["nodes"] == 3

    def test_duplicate_files_in_session_deduplicated(self, tmp_path):
        log_path = _make_retrieval_log(tmp_path, [
            {"date": "2026-06-01", "file": "a.md", "session_id": "s1"},
            {"date": "2026-06-01", "file": "a.md", "session_id": "s1"},
            {"date": "2026-06-01", "file": "b.md", "session_id": "s1"},
        ])
        out_path = str(tmp_path / "graph.csv")
        result = compute_proximity_graph(log_path, out_path, reference_date=REF_DATE)
        assert result["edges"] == 1

    def test_no_session_id_rows_ignored(self, tmp_path):
        log_path = _make_retrieval_log(tmp_path, [
            {"date": "2026-06-01", "file": "a.md", "session_id": ""},
            {"date": "2026-06-01", "file": "b.md", "session_id": ""},
        ])
        out_path = str(tmp_path / "graph.csv")
        result = compute_proximity_graph(log_path, out_path, reference_date=REF_DATE)
        assert result["edges"] == 0
