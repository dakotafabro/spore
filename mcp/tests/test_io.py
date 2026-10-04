from mcp_spore.core.io import append_csv_row, file_exists, read_csv, write_csv


class TestReadCsv:
    def test_nonexistent_file_returns_empty(self, tmp_path):
        result = read_csv(str(tmp_path / "missing.csv"))
        assert result == []

    def test_valid_csv_returns_list_of_dicts(self, tmp_path):
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("name,value\nalpha,1\nbeta,2\n")

        result = read_csv(str(csv_path))
        assert len(result) == 2
        assert result[0] == {"name": "alpha", "value": "1"}
        assert result[1] == {"name": "beta", "value": "2"}

    def test_header_only_returns_empty(self, tmp_path):
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("name,value\n")

        result = read_csv(str(csv_path))
        assert result == []


class TestWriteCsv:
    def test_creates_file_with_headers_and_rows(self, tmp_path):
        csv_path = str(tmp_path / "out.csv")
        write_csv(csv_path, [{"a": "1", "b": "2"}], ["a", "b"])

        content = (tmp_path / "out.csv").read_text()
        lines = content.strip().split("\n")
        assert lines[0] == "a,b"
        assert lines[1] == "1,2"

    def test_creates_parent_directories(self, tmp_path):
        csv_path = str(tmp_path / "nested" / "deep" / "out.csv")
        write_csv(csv_path, [{"x": "y"}], ["x"])
        assert read_csv(csv_path) == [{"x": "y"}]

    def test_empty_rows_writes_header_only(self, tmp_path):
        csv_path = str(tmp_path / "empty.csv")
        write_csv(csv_path, [], ["col1", "col2"])

        content = (tmp_path / "empty.csv").read_text()
        assert content.strip() == "col1,col2"


class TestRoundTrip:
    def test_write_then_read_returns_same_data(self, tmp_path):
        csv_path = str(tmp_path / "round.csv")
        original = [
            {"name": "alpha", "score": "0.95"},
            {"name": "beta", "score": "0.42"},
            {"name": "gamma", "score": "0.01"},
        ]
        write_csv(csv_path, original, ["name", "score"])
        result = read_csv(csv_path)
        assert result == original


class TestAppendCsvRow:
    def test_creates_file_with_header_on_first_append(self, tmp_path):
        csv_path = str(tmp_path / "append.csv")
        append_csv_row(csv_path, {"a": "1", "b": "2"}, ["a", "b"])

        result = read_csv(csv_path)
        assert len(result) == 1
        assert result[0] == {"a": "1", "b": "2"}

    def test_appends_without_duplicate_header(self, tmp_path):
        csv_path = str(tmp_path / "append.csv")
        append_csv_row(csv_path, {"a": "1"}, ["a"])
        append_csv_row(csv_path, {"a": "2"}, ["a"])

        result = read_csv(csv_path)
        assert len(result) == 2
        assert result[0]["a"] == "1"
        assert result[1]["a"] == "2"


class TestFileExists:
    def test_existing_file(self, tmp_path):
        p = tmp_path / "exists.txt"
        p.write_text("hi")
        assert file_exists(str(p)) is True

    def test_nonexistent_file(self, tmp_path):
        assert file_exists(str(tmp_path / "nope.txt")) is False
