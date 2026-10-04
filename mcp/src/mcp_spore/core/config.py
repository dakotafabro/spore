from pathlib import Path
from typing import Any
import os
import subprocess
import yaml


DEFAULT_CONFIG: dict[str, Any] = {
    "version": "0.1.0",
    "decay_rate": 0.03,
    "consolidation_threshold": 0.3,
    "proximity_decay_days": 60,
    "proximity_prune_threshold": 0.5,
    "importance_overrides": [],
    "phase": "germination",
}

PLUGIN_ROOT = Path.home() / ".agents" / "plugins" / "spore"


def resolve_repo_root() -> Path:
    env_root = os.environ.get("SPORE_REPO_ROOT")
    if env_root:
        return Path(env_root)

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return Path.cwd()


def load_config(repo_root: Path | None = None) -> dict[str, Any]:
    if repo_root is None:
        repo_root = resolve_repo_root()

    config_path = repo_root / ".spore.yaml"
    if not config_path.exists():
        return {**DEFAULT_CONFIG, "repo_root": str(repo_root)}

    with open(config_path, "r") as f:
        raw = yaml.safe_load(f) or {}

    spore_config = raw.get("spore", raw)
    merged = {**DEFAULT_CONFIG, **spore_config}
    merged["repo_root"] = str(repo_root)
    return merged


def load_trust_state(repo_root: Path | None = None) -> dict[str, Any]:
    if repo_root is None:
        repo_root = resolve_repo_root()

    trust_path = repo_root / ".trust-state.yaml"
    if not trust_path.exists():
        return {}

    with open(trust_path, "r") as f:
        return yaml.safe_load(f) or {}
