import math
from datetime import date

from mcp_spore.core.decay import (
    compute_all_decay_scores,
    compute_base_strength,
    compute_strength,
)
from mcp_spore.core.io import write_csv


RETRIEVAL_HEADERS = ["date", "file", "session_id"]


class TestComputeBaseStrength:
    def test_single_retrieval_returns_one(self):
        assert compute_base_strength(1) == 1.0

    def test_increments_by_point_one(self):
        assert compute_base_strength(2) == 1.1
        assert compute_base_strength(6) == 1.5

    def test_caps_at_two(self):
        assert compute_base_strength(11) == 2.0

    def test_cap_holds_beyond_threshold(self):
        assert compute_base_strength(21) == 2.0
        assert compute_base_strength(100) == 2.0

    def test_zero_retrieval_goes_below_one(self):
        assert compute_base_strength(0) == 0.9


class TestComputeStrength:
    def test_zero_days_returns_base(self):
        assert compute_strength(1, 0) == 1.0

    def test_positive_days_decays(self):
        result = compute_strength(1, 10, 0.03)
        expected = 1.0 * math.exp(-0.03 * 10)
        assert abs(result - expected) < 1e-9

    def test_large_days_returns_near_zero(self):
        result = compute_strength(1, 1000, 0.03)
        assert result < 1e-10

    def test_custom_decay_rate(self):
        slow = compute_strength(5, 30, 0.01)
        fast = compute_strength(5, 30, 0.1)
        assert slow > fast

    def test_higher_retrieval_count_increases_strength(self):
        low = compute_strength(1, 10, 0.03)
        high = compute_strength(10, 10, 0.03)
        assert high > low

    def test_default_decay_rate_is_003(self):
        with_default = compute_strength(3, 20)
        with_explicit = compute_strength(3, 20, 0.03)
        assert with_default == with_explicit


class TestComputeAllDecayScores:
    def test_empty_csv_returns_empty(self, tmp_path):
        csv_path = str(tmp_path / "retrieval-log.csv")
        write_csv(csv_path, [], RETRIEVAL_HEADERS)
        result = compute_all_decay_scores(csv_path, reference_date=date(2026, 1, 15))
        assert result == []

    def test_nonexistent_file_returns_empty(self, tmp_path):
        result = compute_all_decay_scores(str(tmp_path / "nope.csv"), reference_date=date(2026, 1, 15))
        assert result == []

    def test_single_file_single_retrieval(self, tmp_path):
        csv_path = str(tmp_path / "retrieval-log.csv")
        write_csv(csv_path, [
            {"date": "2026-01-10", "file": "README.md", "session_id": "s1"},
        ], RETRIEVAL_HEADERS)

        result = compute_all_decay_scores(csv_path, decay_rate=0.03, reference_date=date(2026, 1, 15))
        assert len(result) == 1
        assert result[0]["file"] == "README.md"
        assert result[0]["retrieval_count"] == 1
        assert result[0]["days_since_last"] == 5
        expected_strength = round(1.0 * math.exp(-0.03 * 5), 4)
        assert result[0]["strength"] == expected_strength

    def test_multiple_files_sorted_by_strength_ascending(self, tmp_path):
        csv_path = str(tmp_path / "retrieval-log.csv")
        write_csv(csv_path, [
            {"date": "2026-01-01", "file": "old.md", "session_id": "s1"},
            {"date": "2026-01-14", "file": "recent.md", "session_id": "s2"},
        ], RETRIEVAL_HEADERS)

        result = compute_all_decay_scores(csv_path, reference_date=date(2026, 1, 15))
        assert len(result) == 2
        assert result[0]["file"] == "old.md"
        assert result[1]["file"] == "recent.md"
        assert result[0]["strength"] <= result[1]["strength"]

    def test_multiple_retrievals_increases_strength(self, tmp_path):
        csv_path = str(tmp_path / "retrieval-log.csv")
        write_csv(csv_path, [
            {"date": "2026-01-10", "file": "hot.md", "session_id": "s1"},
            {"date": "2026-01-12", "file": "hot.md", "session_id": "s2"},
            {"date": "2026-01-10", "file": "cold.md", "session_id": "s1"},
        ], RETRIEVAL_HEADERS)

        result = compute_all_decay_scores(csv_path, reference_date=date(2026, 1, 15))
        hot = next(r for r in result if r["file"] == "hot.md")
        cold = next(r for r in result if r["file"] == "cold.md")
        assert hot["retrieval_count"] == 2
        assert cold["retrieval_count"] == 1
        assert hot["strength"] > cold["strength"]

    def test_bad_date_rows_skipped(self, tmp_path):
        csv_path = str(tmp_path / "retrieval-log.csv")
        write_csv(csv_path, [
            {"date": "not-a-date", "file": "bad.md", "session_id": "s1"},
            {"date": "2026-01-10", "file": "good.md", "session_id": "s2"},
        ], RETRIEVAL_HEADERS)

        result = compute_all_decay_scores(csv_path, reference_date=date(2026, 1, 15))
        assert len(result) == 1
        assert result[0]["file"] == "good.md"

    def test_missing_file_field_skips_row(self, tmp_path):
        csv_path = str(tmp_path / "retrieval-log.csv")
        write_csv(csv_path, [
            {"date": "2026-01-10", "file": "", "session_id": "s1"},
            {"date": "2026-01-10", "file": "present.md", "session_id": "s2"},
        ], RETRIEVAL_HEADERS)

        result = compute_all_decay_scores(csv_path, reference_date=date(2026, 1, 15))
        assert len(result) == 1
        assert result[0]["file"] == "present.md"

    def test_last_retrieval_date_is_most_recent(self, tmp_path):
        csv_path = str(tmp_path / "retrieval-log.csv")
        write_csv(csv_path, [
            {"date": "2026-01-05", "file": "doc.md", "session_id": "s1"},
            {"date": "2026-01-12", "file": "doc.md", "session_id": "s2"},
            {"date": "2026-01-08", "file": "doc.md", "session_id": "s3"},
        ], RETRIEVAL_HEADERS)

        result = compute_all_decay_scores(csv_path, reference_date=date(2026, 1, 15))
        assert result[0]["last_retrieval"] == "2026-01-12"
        assert result[0]["days_since_last"] == 3
