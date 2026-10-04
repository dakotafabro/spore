import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from mcp_spore.core.config import DEFAULT_CONFIG, resolve_repo_root
from mcp_spore.core.io import file_exists


def spore_init_impl() -> str:
    """Initialize spore in the current repo. Creates data files and config. Idempotent."""
    repo_root = resolve_repo_root()
    created: list[str] = []
    already_existed: list[str] = []
    topology: dict[str, Any] = {}

    retrieval_path = repo_root / ".retrieval-log.csv"
    if not retrieval_path.exists():
        retrieval_path.write_text("date,session_id,file,context\n", encoding="utf-8")
        created.append(".retrieval-log.csv")
    else:
        already_existed.append(".retrieval-log.csv")

    interoception_path = repo_root / ".interoception-log.csv"
    if not interoception_path.exists():
        interoception_path.write_text(
            "timestamp,session_id,context_remaining_pct,retrievals,tokens_spent,deliverables,efficiency_vs_baseline,agent_observation\n",
            encoding="utf-8",
        )
        created.append(".interoception-log.csv")
    else:
        already_existed.append(".interoception-log.csv")

    trust_path = repo_root / ".trust-state.yaml"
    if not trust_path.exists():
        trust_state = {
            "level": "observe",
            "escalations": [],
            "last_check": None,
            "initialized": date.today().isoformat(),
        }
        with open(trust_path, "w") as f:
            yaml.dump(trust_state, f, default_flow_style=False)
        created.append(".trust-state.yaml")
    else:
        already_existed.append(".trust-state.yaml")

    config_path = repo_root / ".spore.yaml"
    if not config_path.exists():
        spore_config = {
            "spore": {
                **DEFAULT_CONFIG,
                "repo_root": str(repo_root),
                "initialized": date.today().isoformat(),
            }
        }
        with open(config_path, "w") as f:
            yaml.dump(spore_config, f, default_flow_style=False)
        created.append(".spore.yaml")
    else:
        already_existed.append(".spore.yaml")

    from mcp_spore.core.config import PLUGIN_ROOT

    spore_env_path = PLUGIN_ROOT / ".spore-env"
    env_line = f"SPORE_REPO_ROOT={repo_root}\n"
    if not spore_env_path.exists() or spore_env_path.read_text() != env_line:
        spore_env_path.write_text(env_line, encoding="utf-8")
        created.append(".spore-env (plugin hook config)")
    else:
        already_existed.append(".spore-env (plugin hook config)")

    has_index = (repo_root / "INDEX.md").exists()
    topology["has_root_index"] = has_index

    git_dir = repo_root / ".git"
    topology["is_git_repo"] = git_dir.exists()

    top_level_dirs = sorted([
        d.name for d in repo_root.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ])
    topology["top_level_directories"] = top_level_dirs[:20]

    index_count = sum(1 for _ in repo_root.rglob("INDEX.md"))
    topology["index_file_count"] = index_count

    result = {
        "status": "initialized" if created else "already_initialized",
        "repo_root": str(repo_root),
        "created": created,
        "already_existed": already_existed,
        "topology": topology,
    }

    if not has_index:
        result["recommendation"] = "Consider creating a root INDEX.md for fast agent lookup."

    return json.dumps(result, indent=2)
