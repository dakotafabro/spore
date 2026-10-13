import json
import sqlite3

from mcp_spore.core.session import current_session_id, rows_for, tokens_spent
from mcp_spore.tools.logging import spore_log_retrieval_impl
from mcp_spore.tools.status import spore_sense_impl


def make_goose_db(path, rows):
    con = sqlite3.connect(path)
    con.execute("create table sessions (id text primary key, total_tokens integer, accumulated_total_tokens integer)")
    con.executemany("insert into sessions values (?, ?, ?)", rows)
    con.commit()
    con.close()


def make_repo(tmp_path):
    (tmp_path / ".retrieval-log.csv").write_text(
        "date,session_id,file,context\n"
        "2026-10-13,20261013_69,a.md,hook:shell_read\n"
        "2026-10-13,20261013_75,b.md,hook:shell_read\n"
        "2026-10-13,20261013_69,c.md,manual\n"
    )
    (tmp_path / ".deposition-log.csv").write_text(
        "date,session_id,file,context,type\n2026-10-13,20261013_69,new.md,,creation\n"
    )
    (tmp_path / ".interoception-log.csv").write_text(
        "timestamp,session_id,context_remaining_pct,retrievals,tokens_spent,deliverables,efficiency_vs_baseline,agent_observation\n"
    )
    return tmp_path


class TestCurrentSessionId:
    def test_reads_agent_session_id(self, monkeypatch):
        monkeypatch.setenv("AGENT_SESSION_ID", "20261013_69")
        assert current_session_id() == "20261013_69"

    def test_rejects_malformed_ids(self, monkeypatch):
        monkeypatch.setenv("AGENT_SESSION_ID", "x'; drop table sessions; --")
        assert current_session_id() == ""

    def test_empty_when_unset(self, monkeypatch):
        monkeypatch.delenv("AGENT_SESSION_ID", raising=False)
        assert current_session_id() == ""


class TestTokensSpent:
    def test_prefers_accumulated_total(self, tmp_path):
        db = tmp_path / "sessions.db"
        make_goose_db(db, [("s1", 100, 900), ("s2", 50, None)])
        assert tokens_spent("s1", db) == 900
        assert tokens_spent("s2", db) == 50

    def test_none_when_unknown(self, tmp_path):
        db = tmp_path / "sessions.db"
        make_goose_db(db, [])
        assert tokens_spent("missing", db) is None
        assert tokens_spent("s1", tmp_path / "absent.db") is None


class TestSense:
    def test_counts_only_this_session(self, tmp_path, monkeypatch):
        # given
        repo = make_repo(tmp_path)
        db = tmp_path / "sessions.db"
        make_goose_db(db, [("20261013_69", 172000, 9700000)])
        monkeypatch.setenv("SPORE_REPO_ROOT", str(repo))
        monkeypatch.setenv("SPORE_GOOSE_DB", str(db))
        monkeypatch.setenv("AGENT_SESSION_ID", "20261013_69")

        # when
        out = json.loads(spore_sense_impl())

        # then
        assert out["session_id"] == "20261013_69"
        assert out["retrievals_this_session"] == 2
        assert out["deliverables_this_session"] == 1
        assert out["tokens_spent_estimate"] == 9700000
        assert out["tokens_source"] == "goose sessions.db"
        assert out["total_retrievals_all_time"] == 3

    def test_says_so_without_a_session(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SPORE_REPO_ROOT", str(make_repo(tmp_path)))
        monkeypatch.delenv("AGENT_SESSION_ID", raising=False)
        assert json.loads(spore_sense_impl())["status"] == "no_session"


class TestDefaultSessionId:
    def test_manual_retrieval_uses_the_goose_session(self, tmp_path, monkeypatch):
        # given
        repo = make_repo(tmp_path)
        monkeypatch.setenv("SPORE_REPO_ROOT", str(repo))
        monkeypatch.setenv("AGENT_SESSION_ID", "20261013_69")

        # when
        out = json.loads(spore_log_retrieval_impl("d.md"))

        # then
        assert out["session_id"] == "20261013_69"
        assert rows_for(repo / ".retrieval-log.csv", "20261013_69") == 3
