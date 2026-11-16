import json
import sqlite3

from mcp_spore.core.economy import (
    deliverables_for,
    derived_deliverables,
    fuel_economy,
    recent_session_ids,
    session_deliverables,
    session_usage,
    window_summary,
)
from mcp_spore.tools.logging import spore_log_deposition_impl
from mcp_spore.tools.status import spore_economy_impl, spore_sense_impl


SESSIONS = [("s1", "user", None), ("s2", "user", None), ("s3", "acp", None), ("h1", "hidden", None), ("s1-sub", "sub_agent", "s1")]


def make_ledger(path, rows, sessions=SESSIONS):
    con = sqlite3.connect(path)
    con.execute(
        "create table sessions (id text primary key, session_type text, parent_session_id text,"
        " total_tokens integer, accumulated_total_tokens integer)"
    )
    con.executemany("insert into sessions (id, session_type, parent_session_id) values (?, ?, ?)", sessions)
    con.execute("create table messages (id integer primary key autoincrement, session_id text, role text, content_json text)")
    con.execute(
        "create table usage_ledger (id integer primary key autoincrement, session_id text, created_timestamp integer,"
        " model text, input_tokens integer, output_tokens integer, total_tokens integer, cache_read_tokens integer,"
        " cache_write_tokens integer, cost real, cost_source text, is_compaction integer default 0)"
    )
    con.executemany(
        "insert into usage_ledger (session_id, created_timestamp, input_tokens, output_tokens, cache_read_tokens,"
        " cache_write_tokens, cost, is_compaction) values (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    con.commit()
    con.close()


LEDGER = [
    ("s1", 1000, 50_000, 2_000, 0, 50_000, 0.25, 0),
    ("s1", 1010, 60_000, 1_000, 50_000, 10_000, 0.10, 0),
    ("s1", 1020, 70_000, 1_000, 60_000, 10_000, 0.05, 0),
    ("s1", 1030, 90_000, 500, 0, 0, 0.30, 1),
    ("s2", 1040, 40_000, 4_000, 0, 40_000, 0.20, 0),
    ("s3", 1050, 30_000, 1_000, 0, 30_000, 0.10, 0),
    ("h1", 1060, 500, 10, 0, 0, 0.01, 0),
]


def add_call(path, session_id, call_id, name, arguments, text, stdout=None, exit_code=0):
    request = [{"type": "toolRequest", "id": call_id, "toolCall": {"status": "success", "value": {"name": name, "arguments": arguments}}}]
    value = {"content": [{"type": "text", "text": text}], "isError": False}
    if stdout is not None:
        value["structuredContent"] = {"stdout": stdout, "stderr": "", "exit_code": exit_code}
    response = [{"type": "toolResponse", "id": call_id, "toolResult": {"status": "success", "value": value}}]
    con = sqlite3.connect(path)
    con.execute("insert into messages (session_id, role, content_json) values (?, 'assistant', ?)", (session_id, json.dumps(request)))
    con.execute("insert into messages (session_id, role, content_json) values (?, 'user', ?)", (session_id, json.dumps(response)))
    con.commit()
    con.close()


def make_deposits(tmp_path, body):
    path = tmp_path / ".deposition-log.csv"
    path.write_text("date,session_id,file,context,type\n" + body)
    return path


class TestSessionUsage:
    def test_sums_requests_and_estimates_idle(self, tmp_path):
        db = tmp_path / "sessions.db"
        make_ledger(db, LEDGER)
        usage = session_usage("s1", db)
        assert usage["requests"] == 3
        assert usage["input_tokens"] == 180_000
        assert usage["output_tokens"] == 4_000
        assert usage["total_tokens"] == 184_000
        assert usage["cache_read_tokens"] == 110_000
        assert usage["fresh_input_tokens"] == 70_000
        assert usage["preamble_estimate"] == 50_000
        assert usage["idle_tokens"] == 150_000
        assert usage["cost"] == 0.4

    def test_skips_compaction_requests(self, tmp_path):
        db = tmp_path / "sessions.db"
        make_ledger(db, LEDGER)
        assert session_usage("s1", db)["requests"] == 3

    def test_folds_in_subagent_spend(self, tmp_path):
        db = tmp_path / "sessions.db"
        make_ledger(db, LEDGER + [("s1-sub", 1025, 20_000, 1_000, 0, 20_000, 0.05, 0)])
        usage = session_usage("s1", db)
        assert usage["requests"] == 4
        assert usage["total_tokens"] == 205_000
        assert usage["preamble_estimate"] == 50_000
        assert usage["idle_tokens"] == 200_000
        assert usage["subagent_sessions"] == 1

    def test_none_when_unknown(self, tmp_path):
        db = tmp_path / "sessions.db"
        make_ledger(db, [])
        assert session_usage("s1", db) is None
        assert session_usage("s1", tmp_path / "absent.db") is None
        assert session_usage("", db) is None

    def test_none_without_ledger_table(self, tmp_path):
        db = tmp_path / "sessions.db"
        sqlite3.connect(db).execute("create table sessions (id text)").connection.close()
        assert session_usage("s1", db) is None


class TestDeliverables:
    def test_counts_by_type_for_the_session(self, tmp_path):
        log = make_deposits(
            tmp_path,
            "2026-11-16,s1,a.md,,creation\n"
            "2026-11-16,s1,https://github.com/o/r/issues/1,\"filed, linked\",issue\n"
            "2026-11-16,s1,https://github.com/o/r/issues/2,,issue\n"
            "2026-11-16,s2,b.md,,\n",
        )
        assert deliverables_for(log, "s1") == {"creation": 1, "issue": 2}
        assert deliverables_for(log, "s2") == {"creation": 1}
        assert deliverables_for(log, "missing") == {}


class TestDerivedDeliverables:
    def test_reads_what_tools_produced(self, tmp_path):
        db = tmp_path / "sessions.db"
        make_ledger(db, LEDGER)
        url = "https://github.com/o/r/issues/7"
        add_call(db, "s1", "a", "shell", {"command": "gh issue create -R o/r --title t"}, url, stdout=url)
        add_call(db, "s1", "b", "shell", {"command": "gh issue view 7 -R o/r"}, url, stdout=url)
        add_call(db, "s1", "c", "shell", {"command": "git commit -qm x && git log -1"}, "", stdout="[main 1a2b3c4d] Add x\n 1 file changed")
        add_call(db, "s1", "d", "shell", {"command": "gh pr create --fill"}, "", stdout="boom", exit_code=1)
        add_call(db, "s1", "e", "shell", {"command": "gh pr merge 12 --squash"}, "", stdout="")
        add_call(db, "s1", "f", "write", {"path": "/repo/a.py"}, "Created /repo/a.py (3 lines)")
        add_call(db, "s1", "g", "write", {"path": "/tmp/x.md"}, "Created /tmp/x.md (3 lines)")
        add_call(db, "s1", "h", "shell", {"command": "grep -n 'gh pr merge 99' notes.md; echo \"gh issue create\""}, url, stdout="https://github.com/o/r/issues/8")
        add_call(db, "s1", "i", "shell", {"command": "cd /repo && git -C /repo commit -qm y"}, "", stdout="[main 9f8e7d6c] Add y")
        assert derived_deliverables("s1", db) == {
            url: "issue",
            "commit:1a2b3c4d": "commit",
            "commit:9f8e7d6c": "commit",
            "merge:12": "merge",
            "/repo/a.py": "creation",
        }

    def test_counts_each_deliverable_once_and_includes_subagents(self, tmp_path):
        db = tmp_path / "sessions.db"
        make_ledger(db, LEDGER)
        url = "https://github.com/o/r/pull/9"
        add_call(db, "s1", "a", "shell", {"command": "gh pr create --fill"}, url, stdout=url)
        add_call(db, "s1-sub", "b", "write", {"path": "/repo/b.py"}, "Created /repo/b.py (1 lines)")
        log = make_deposits(tmp_path, f"2026-11-16,s1,{url},,pr\n2026-11-16,s1,,note,doc\n")
        assert session_deliverables("s1", log, db) == {"pr": 1, "doc": 1, "creation": 1}


class TestFuelEconomy:
    def test_tokens_per_deliverable_with_idle_line(self):
        usage = {
            "requests": 3, "input_tokens": 180_000, "output_tokens": 4_000, "total_tokens": 184_000,
            "cache_read_tokens": 110_000, "cache_write_tokens": 70_000, "fresh_input_tokens": 70_000,
            "preamble_estimate": 50_000, "idle_tokens": 150_000, "cost": 0.4,
        }
        economy = fuel_economy(usage, {"issue": 2})
        assert economy["status"] == "ok"
        assert economy["tokens_per_deliverable"] == 92_000
        assert economy["idle_tokens_per_deliverable"] == 75_000
        assert economy["tokens"]["idle_share"] == 0.833
        assert economy["cost_per_deliverable"] == 0.2

    def test_no_figure_without_deliverables(self):
        usage = {
            "requests": 1, "input_tokens": 10, "output_tokens": 1, "total_tokens": 11, "cache_read_tokens": 0,
            "cache_write_tokens": 0, "fresh_input_tokens": 10, "preamble_estimate": 10, "idle_tokens": 10, "cost": None,
        }
        economy = fuel_economy(usage, {})
        assert economy["status"] == "no_deliverables"
        assert "tokens_per_deliverable" not in economy

    def test_no_usage(self):
        assert fuel_economy(None, {"issue": 1})["status"] == "no_usage"


class TestWindow:
    def test_recent_sessions_newest_first(self, tmp_path):
        db = tmp_path / "sessions.db"
        make_ledger(db, LEDGER)
        assert recent_session_ids(1, db, now=1060) == ["s3", "s2", "s1"]
        assert recent_session_ids(1, db, now=1045 + 86400) == ["s3"]

    def test_median_and_sessions_without_deliverables(self, tmp_path):
        db = tmp_path / "sessions.db"
        make_ledger(db, LEDGER)
        log = make_deposits(tmp_path, "2026-11-16,s1,a.md,,creation\n2026-11-16,s2,b.md,,commit\n")
        summary = window_summary(["s1", "s2", "s3"], log, db)
        assert summary["sessions_with_deliverables"] == 2
        assert summary["sessions_without_deliverables"] == 1
        assert summary["tokens_in_sessions_without_deliverables"] == 31_000
        assert summary["median_tokens_per_deliverable"] == 114_000
        assert [s["session_id"] for s in summary["sessions"]] == ["s1", "s2"]


class TestTools:
    def test_deposition_records_type(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SPORE_REPO_ROOT", str(tmp_path))
        monkeypatch.setenv("AGENT_SESSION_ID", "s1")
        result = json.loads(spore_log_deposition_impl("https://github.com/o/r/issues/1", "filed", type="issue"))
        assert result["type"] == "issue"
        assert deliverables_for(tmp_path / ".deposition-log.csv", "s1") == {"issue": 1}

    def test_deposition_rejects_unknown_type(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SPORE_REPO_ROOT", str(tmp_path))
        result = json.loads(spore_log_deposition_impl("x", type="vibes"))
        assert result["status"] == "error"
        assert not (tmp_path / ".deposition-log.csv").exists()

    def test_sense_includes_fuel_economy(self, tmp_path, monkeypatch):
        db = tmp_path / "sessions.db"
        make_ledger(db, LEDGER)
        make_deposits(tmp_path, "2026-11-16,s1,a.md,,creation\n")
        monkeypatch.setenv("SPORE_REPO_ROOT", str(tmp_path))
        monkeypatch.setenv("SPORE_GOOSE_DB", str(db))
        monkeypatch.setenv("AGENT_SESSION_ID", "s1")
        result = json.loads(spore_sense_impl())
        assert result["fuel_economy"]["tokens_per_deliverable"] == 184_000

    def test_economy_tool_clamps_window(self, tmp_path, monkeypatch):
        db = tmp_path / "sessions.db"
        make_ledger(db, [])
        monkeypatch.setenv("SPORE_REPO_ROOT", str(tmp_path))
        monkeypatch.setenv("SPORE_GOOSE_DB", str(db))
        assert json.loads(spore_economy_impl(500))["window_days"] == 90
        assert json.loads(spore_economy_impl(0))["window_days"] == 1
