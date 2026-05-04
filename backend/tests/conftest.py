"""Shared fixtures for backend tests."""
import pytest
from unittest.mock import AsyncMock
from pathlib import Path

# Import existing fixtures
from backend.tests.server_harness import start_server, stop_server


@pytest.fixture(scope="module", autouse=True)
def run_server():
    """Start server for tests that need it."""
    start_server()
    yield
    stop_server()


@pytest.fixture
def hub():
    """Mock HubState for tests that need it."""
    h = AsyncMock()
    h.provider = AsyncMock()
    h.provider.list_models = AsyncMock(return_value=[])
    h.selected_model = None
    return h


@pytest.fixture
def tmp_config(tmp_path: Path) -> Path:
    """Create a temporary config.toml for testing."""
    config = '''[runtime]
working_dir = "."

[active_provider]
provider = "ollama"
base_url = "http://localhost:11434"
model = "test-model"

[tools]
shell = true

[permissions]
enabled = false
'''
    config_path = tmp_path / "config.toml"
    config_path.write_text(config)
    return config_path
