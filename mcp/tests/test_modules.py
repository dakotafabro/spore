import json
from pathlib import Path

import yaml

from mcp_spore.core.io import write_csv
from mcp_spore.core.modules import collect_sessions, load_registry, module_topology, propose

NOW = 1_800_000_000.0


def _registry(tmp_path, repo_root):
    reg = {
        "repos": {"prof": {"path": str(repo_root)}, "ctx": {"path": str(tmp_path / "ctx")}},
        "dirs": {"ship": {}, "review": {}, "shared": {}},
        "modules": [
            {"id": "voice", "repo": "ctx", "file": "voice.md", "dir": "shared"},
            {"id": "commit", "repo": "ctx", "file": "commit.md", "dir": "ship"},
            {"id": "branch", "repo": "ctx", "file": "branch.md", "dir": "ship"},
            {"id": "audit", "repo": "prof", "file": "conventions/audit.md", "dir": "review"},
            {"id": "reply", "repo": "prof", "file": "conventions/reply.md", "dir": "review"},
            {"id": "inline", "repo": "ctx", "file": "inline.md", "dir": "ship"},
            {"id": "ticket", "repo": "ctx", "file": "ticket.md"},
            {"id": "lonely", "repo": "ctx", "file": "lonely.md"},
        ],
    }
    path = tmp_path / "modules.yaml"
    path.write_text(yaml.safe_dump(reg))
    return path


def _load(mod, sid, ts=NOW - 100):
    return {"ts": ts, "event": "load", "module": mod, "session": sid}


def test_collect_joins_router_loads_and_file_reads(tmp_path):
    root = tmp_path / "prof"
    root.mkdir()
    reg = load_registry(_registry(tmp_path, root))
    events = [_load("commit", "s1"), {"ts": NOW - 100, "event": "load", "module": "branch"}, _load("nope", "s1")]
    reads = [{"date": "2027-01-15", "session_id": "s1", "file": "conventions/audit.md"}]
    sessions, counts = collect_sessions(reg, events, reads, root, since=NOW - 86400 * 30)
    assert sessions == {"s1": {"commit", "audit"}}
    assert counts == {"router_loads": 1, "router_loads_without_session": 1, "file_reads": 1}


def test_collect_drops_events_before_window(tmp_path):
    root = tmp_path / "prof"
    root.mkdir()
    reg = load_registry(_registry(tmp_path, root))
    sessions, _ = collect_sessions(reg, [_load("commit", "old", ts=NOW - 86400 * 40)], [], root, since=NOW - 86400 * 30)
    assert sessions == {}


def test_propose_moves_label_and_never_loaded(tmp_path):
    root = tmp_path / "prof"
    root.mkdir()
    reg = load_registry(_registry(tmp_path, root))
    sessions = {}
    for i in range(4):
        sessions[f"r{i}"] = {"audit", "reply", "inline", "voice"}
        sessions[f"s{i}"] = {"commit", "branch", "ticket", "voice"}
        sessions[f"q{i}"] = {"audit", "reply"}
    result = propose(reg, sessions)
    by = {(p["type"], p["module"]): p for p in result["proposals"]}
    assert by[("move", "inline")]["to"] == "review"
    assert by[("label", "ticket")]["to"] == "ship"
    assert ("never_loaded", "lonely") in by
    assert "voice" in result["excluded_modules"]
    assert not any(p["module"] in {"commit", "branch", "audit", "reply"} for p in result["proposals"])


def test_shared_modules_do_not_bridge_directories(tmp_path):
    root = tmp_path / "prof"
    root.mkdir()
    reg = load_registry(_registry(tmp_path, root))
    sessions = {f"x{i}": {"ticket", "voice"} for i in range(5)}
    result = propose(reg, sessions)
    by = {(p["type"], p["module"]): p for p in result["proposals"]}
    assert by[("stay_unlabelled", "ticket")]["affinity"] == {"review": 0.0, "ship": 0.0}


def test_busy_directory_alone_does_not_win_a_label(tmp_path):
    root = tmp_path / "prof"
    root.mkdir()
    reg = load_registry(_registry(tmp_path, root))
    sessions = {f"b{i}": {"commit", "audit"} for i in range(6)}
    sessions.update({f"t{i}": {"commit", "audit", "ticket"} for i in range(4)})
    by = {(p["type"], p["module"]): p for p in propose(reg, sessions)["proposals"]}
    assert ("stay_unlabelled", "ticket") in by
    assert by[("stay_unlabelled", "ticket")]["lift"] == {"review": 1.0, "ship": 1.0}


def test_module_topology_reads_env_paths(tmp_path, monkeypatch):
    root = tmp_path / "prof"
    root.mkdir()
    reg_path = _registry(tmp_path, root)
    log = tmp_path / "loads.jsonl"
    log.write_text("\n".join(json.dumps(_load(m, "s1")) for m in ["commit", "branch"]) + "\nnot json\n")
    write_csv(str(root / ".retrieval-log.csv"), [], ["date", "session_id", "file", "context"])
    monkeypatch.setenv("SPORE_ROUTER_REGISTRY", str(reg_path))
    monkeypatch.setenv("SPORE_ROUTER_LOGS", str(log))
    out = module_topology(root, window_days=30, now=NOW)
    assert out["status"] == "ok"
    assert out["sources"]["router_loads"] == 2
    assert out["sessions_seen"] == 1


def test_module_topology_without_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("SPORE_ROUTER_REGISTRY", str(tmp_path / "missing.yaml"))
    assert module_topology(tmp_path)["status"] == "no_registry"
