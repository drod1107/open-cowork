from backend.config_loader import (
    load_config,
    save_config,
    update_permission_pattern,
)


def test_load_roundtrip(tmp_config):
    cfg = load_config(tmp_config)
    assert cfg["active_provider"]["provider"] == "ollama"
    cfg["active_provider"]["provider"] = "vllm"
    save_config(cfg, tmp_config)
    cfg2 = load_config(tmp_config)
    assert cfg2["active_provider"]["provider"] == "vllm"


def test_shell_tool_enabled_by_default(tmp_config):
    cfg = load_config(tmp_config)
    assert cfg["tools"]["shell"] is True


def test_shell_tool_can_be_disabled(tmp_config):
    cfg = load_config(tmp_config)
    cfg["tools"]["shell"] = False
    save_config(cfg, tmp_config)
    cfg2 = load_config(tmp_config)
    assert cfg2["tools"]["shell"] is False


def test_update_permission_pattern_appends(tmp_config):
    update_permission_pattern(
        "shell", "cat *", list_key="allowed_commands", path=tmp_config
    )
    cfg = load_config(tmp_config)
    assert "cat *" in cfg["permissions"]["shell"]["allowed_commands"]


def test_update_permission_pattern_idempotent(tmp_config):
    update_permission_pattern("shell", "ls*", list_key="allowed_commands", path=tmp_config)
    update_permission_pattern("shell", "ls*", list_key="allowed_commands", path=tmp_config)
    cfg = load_config(tmp_config)
    assert cfg["permissions"]["shell"]["allowed_commands"].count("ls*") == 1


def test_nvidia_credentials_not_in_config(tmp_config):
    """Verify NVIDIA API credentials are NOT stored in config.toml (they go in .env)"""
    cfg = load_config(tmp_config)
    assert "nvidia_api_key" not in cfg
    assert "NVIDIA_API_KEY" not in cfg
    assert "nvidia_base_url" not in cfg
