import yaml

from mcp_spore.core.config import DEFAULT_CONFIG, load_config, load_trust_state


class TestLoadConfig:
    def test_no_spore_yaml_returns_defaults(self, tmp_path):
        config = load_config(tmp_path)
        for key, value in DEFAULT_CONFIG.items():
            assert config[key] == value

    def test_always_includes_repo_root(self, tmp_path):
        config = load_config(tmp_path)
        assert config["repo_root"] == str(tmp_path)

    def test_merges_over_defaults(self, tmp_path):
        spore_yaml = tmp_path / ".spore.yaml"
        spore_yaml.write_text(yaml.dump({"spore": {"decay_rate": 0.05, "phase": "fruiting"}}))

        config = load_config(tmp_path)
        assert config["decay_rate"] == 0.05
        assert config["phase"] == "fruiting"
        assert config["consolidation_threshold"] == DEFAULT_CONFIG["consolidation_threshold"]

    def test_flat_yaml_also_works(self, tmp_path):
        spore_yaml = tmp_path / ".spore.yaml"
        spore_yaml.write_text(yaml.dump({"decay_rate": 0.07}))

        config = load_config(tmp_path)
        assert config["decay_rate"] == 0.07

    def test_empty_yaml_returns_defaults(self, tmp_path):
        spore_yaml = tmp_path / ".spore.yaml"
        spore_yaml.write_text("")

        config = load_config(tmp_path)
        for key, value in DEFAULT_CONFIG.items():
            assert config[key] == value

    def test_env_var_override(self, tmp_path, monkeypatch):
        target = tmp_path / "custom"
        target.mkdir()
        monkeypatch.setenv("SPORE_REPO_ROOT", str(target))

        from mcp_spore.core.config import resolve_repo_root
        resolved = resolve_repo_root()
        assert resolved == target


class TestLoadTrustState:
    def test_no_file_returns_empty_dict(self, tmp_path):
        result = load_trust_state(tmp_path)
        assert result == {}

    def test_with_file_returns_contents(self, tmp_path):
        trust_path = tmp_path / ".trust-state.yaml"
        trust_path.write_text(yaml.dump({"approved": True, "level": 3}))

        result = load_trust_state(tmp_path)
        assert result["approved"] is True
        assert result["level"] == 3

    def test_empty_file_returns_empty_dict(self, tmp_path):
        trust_path = tmp_path / ".trust-state.yaml"
        trust_path.write_text("")

        result = load_trust_state(tmp_path)
        assert result == {}
