from backend.config_loader import (
    load_config,
    save_config,
    update_permission_pattern,
)


def test_load_roundtrip(tmp_config):
    cfg = load_config(tmp_config)
    assert cfg["provider"] == "ollama"
    cfg["provider"] = "vllm"
    save_config(cfg, tmp_config)
    cfg2 = load_config(tmp_config)
    assert cfg2["provider"] == "vllm"


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
