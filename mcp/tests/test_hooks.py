import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from hook_payload import shell_reads  # noqa: E402


def run_hook(name, payload, plugin_root, env=None):
    full_env = {"PATH": os.environ["PATH"], "HOME": str(plugin_root), "PLUGIN_ROOT": str(plugin_root)}
    full_env.update(env or {})
    return subprocess.run(
        ["bash", str(plugin_root / "scripts" / name)],
        input=json.dumps(payload), capture_output=True, text=True, env=full_env, timeout=10,
    )


def make_plugin(tmp_path, repo):
    plugin = tmp_path / "plugin"
    shutil.copytree(SCRIPTS, plugin / "scripts")
    (plugin / ".spore-env").write_text(f"SPORE_REPO_ROOT={repo}\n")
    return plugin


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "a.md").write_text("a")
    (repo / "docs" / "b.md").write_text("b")
    (repo / ".retrieval-log.csv").write_text("date,session_id,file,context\n")
    return repo


class TestShellReads:
    def test_follows_cd_and_skips_missing_files(self, tmp_path):
        # given
        repo = make_repo(tmp_path)
        other = tmp_path / "other"
        (other / "hooks").mkdir(parents=True)
        (other / "hooks" / "hooks.json").write_text("{}")

        # when
        found = shell_reads(f"cd {other}; cat hooks/hooks.json docs/a.md", str(repo))

        # then
        assert found == [str(other / "hooks" / "hooks.json")]

    def test_expands_globs_and_ignores_flags(self, tmp_path):
        repo = make_repo(tmp_path)
        found = shell_reads("head -n 5 docs/*.md | grep x", str(repo))
        assert found == [str(repo / "docs" / "a.md"), str(repo / "docs" / "b.md")]

    def test_relative_paths_use_working_dir(self, tmp_path):
        repo = make_repo(tmp_path)
        assert shell_reads('cat "docs/a.md" && tail docs/b.md', str(repo)) == [
            str(repo / "docs" / "a.md"), str(repo / "docs" / "b.md")]

    def test_unbalanced_quotes_do_not_crash(self, tmp_path):
        assert shell_reads('cat "docs/a.md', str(make_repo(tmp_path))) == []


class TestHooksKeepSessionsApart:
    def test_two_sessions_count_separately(self, tmp_path):
        # given
        repo = make_repo(tmp_path)
        plugin = make_plugin(tmp_path, repo)
        for sid in ("s1", "s2"):
            assert run_hook("session-start.sh", {"event": "SessionStart", "session_id": sid}, plugin).returncode == 0

        # when
        run_hook("on-shell-exec.sh", {"session_id": "s1", "matcher_context": "cat docs/a.md docs/b.md", "working_dir": str(repo)}, plugin)
        run_hook("on-shell-exec.sh", {"session_id": "s2", "matcher_context": f"cd {repo}/docs && cat a.md", "working_dir": "/"}, plugin)
        run_hook("on-shell-exec.sh", {"session_id": "s2", "matcher_context": "cat missing.md", "working_dir": str(repo)}, plugin)

        # then
        rows = (repo / ".retrieval-log.csv").read_text().splitlines()[1:]
        assert sorted(r.split(",")[1] + ":" + r.split(",")[2] for r in rows) == ["s1:docs/a.md", "s1:docs/b.md", "s2:docs/a.md"]
        assert (plugin / ".sessions" / "s1").read_text().splitlines()[2] == "2"
        assert (plugin / ".sessions" / "s2").read_text().splitlines()[2] == "1"

    def test_session_end_removes_only_its_own_state(self, tmp_path):
        # given
        repo = make_repo(tmp_path)
        plugin = make_plugin(tmp_path, repo)
        for sid in ("s1", "s2"):
            run_hook("session-start.sh", {"session_id": sid}, plugin)

        # when
        run_hook("session-end.sh", {"session_id": "s1"}, plugin)

        # then
        assert not (plugin / ".sessions" / "s1").exists()
        assert (plugin / ".sessions" / "s2").exists()

    def test_malformed_session_id_is_ignored(self, tmp_path):
        # given
        repo = make_repo(tmp_path)
        plugin = make_plugin(tmp_path, repo)

        # when
        run_hook("session-start.sh", {"session_id": "../../etc"}, plugin)

        # then
        names = [p.name for p in (plugin / ".sessions").iterdir()]
        assert len(names) == 1 and ".." not in names[0] and "/" not in names[0]


class TestSessionsStartedBeforeTheUpgrade:
    def test_read_hook_creates_missing_state(self, tmp_path):
        # given a session whose SessionStart ran under the old shared state file
        repo = make_repo(tmp_path)
        plugin = make_plugin(tmp_path, repo)

        # when
        run_hook("on-shell-exec.sh", {"session_id": "old", "matcher_context": "cat docs/a.md", "working_dir": str(repo)}, plugin)

        # then
        state = (plugin / ".sessions" / "old").read_text().splitlines()
        assert state == ["old", str(repo), "1"]
        assert (repo / ".retrieval-log.csv").read_text().splitlines()[1].split(",")[1:3] == ["old", "docs/a.md"]
