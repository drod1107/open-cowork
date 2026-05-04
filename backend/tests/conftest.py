import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

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
def tmp_config(tmp_path: Path, hub) -> Path:
    p = tmp_path / "config.toml"
    with open(p, "wb") as f:
        tomli_w.dump(DEFAULT_CONFIG, f)
    return p


@pytest.fixture()
def hub(tmp_path: Path):
    """Set up app.state.hub with a real HubState + mocked provider.

    TestClient doesn't run the FastAPI lifespan, so we must initialise
    HubState manually. The provider's network calls are mocked so tests
    don't need a live Ollama / OpenAI endpoint.
    """
    from backend.main import HubState, app

    h = HubState()
    h.provider = AsyncMock()
    h.provider.provider = "ollama"
    h.provider.base_url = "http://localhost:11434"
    h.provider.list_models = AsyncMock(return_value=[])

    app.state.hub = h
    yield h

    if hasattr(app.state, "hub"):
        del app.state.hub
