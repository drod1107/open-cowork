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
    "permissions": {
        "filesystem": {"default": "ask", "allowed_dirs": [], "blocked_dirs": []},
        "shell": {
            "default": "ask",
            "allowed_commands": ["echo *", "ls*", "pwd"],
            "blocked_commands": ["rm -rf /*"],
        },
        "web": {"search": "allow", "fetch": "ask"},
        "browser": {"default": "ask"},
        "computer_use": {"default": "ask"},
        "coding": {"default": "ask", "git_commit": "ask"},
    },
}


@pytest.fixture()
def tmp_config(tmp_path: Path) -> Path:
    p = tmp_path / "config.toml"
    with open(p, "wb") as f:
        tomli_w.dump(DEFAULT_CONFIG, f)
    return p
