import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest
import tomli_w


DEFAULT_CONFIG: dict[str, Any] = {
    "provider": "ollama",
    "base_url": "http://localhost:11434",
    "agent": {
        "max_turns": 5,
        "system_prompt": "you are a test",
    },
    "runtime": {"working_dir": "."},
    "tools": {
        "shell": True,
    },
    "permissions": {
        "shell": {
            "allowed_commands": ["ls*", "pwd", "echo*", "cat*", "grep", "git status", "git diff*"],
            "blocked_commands": ["rm -rf /*", "mkfs*", "dd if=*", ":(){:|:&};:"],
        },
    },
}


@pytest.fixture()
def tmp_config(tmp_path: Path) -> Path:
    p = tmp_path / "config.toml"
    with open(p, "wb") as f:
        tomli_w.dump(DEFAULT_CONFIG, f)
    return p
