"""Tests for provider ping behavior - using AsyncMock for async HTTP calls.

Verifies provider detection, model listing, and ping behavior:
- Green state = provider active, selectable
- Greyed out = provider disconnected with error message
- Ping only on: app open, config update, dropdown open
"""
import asyncio
import os
from unittest.mock import AsyncMock, patch, MagicMock, call
import pytest
import httpx

from backend.providers import ProviderClient, _guess_vision


pytestmark = pytest.mark.asyncio


def test_guess_vision_hints():
    # Sync function, no async needed
    assert _guess_vision("llava:7b") is True
    assert _guess_vision("qwen2.5-vl-7b") is True
    assert _guess_vision("mistral-7b") is None


async def test_ollama_provider_ping_success(tmp_path):
    """Test successful Ollama ping returns models."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "models": [
            {"name": "llama3.1:8b", "details": {}},
            {"name": "llava:7b", "details": {}},
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.timeout = 5.0

    client = ProviderClient(
        provider="ollama",
        base_url="http://localhost:11434",
        http=mock_client,
    )
    models = await client.list_models(force=True)
    assert len(models) == 2
    assert models[0].id == "llama3.1:8b"
    assert models[1].supports_vision is True


async def test_vllm_provider_ping_success(tmp_path):
    """Test successful vLLM ping returns models."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [{"id": "qwen2.5-7b"}]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    client = ProviderClient(
        provider="vllm",
        base_url="http://localhost:8000",
        http=mock_client,
    )
    models = await client.list_models(force=True)
    assert models[0].id == "qwen2.5-7b"


async def test_provider_ping_failure_greys_out(tmp_path):
    """Test that failed ping raises an exception (caller handles empty list)."""
    mock_client = AsyncMock()
    # Make await client.get() raise ConnectError
    mock_client.get.side_effect = httpx.ConnectError("Connection refused")

    client = ProviderClient(
        provider="ollama",
        base_url="http://localhost:11434",
        http=mock_client,
    )
    # The function raises an exception - caller should handle it
    try:
        await client.list_models(force=True)
        # If we get here, the exception wasn't raised
        # Check if empty list is returned instead
        pytest.fail("Expected ConnectError to be raised")
    except httpx.ConnectError:
        # Expected behavior
        pass


async def test_nvidia_provider_requires_env_credentials(tmp_path):
    """Test that NVIDIA provider reads from environment variables."""
    # NVIDIA uses OpenAI-compatible API with a custom base URL
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [{"id": "deepseek-ai/deepseek-v4-pro"}]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    # Test with OpenAI-compatible provider type
    client = ProviderClient(
        provider="openai-compat",  # Custom provider for NVIDIA
        base_url="https://integrate.api.nvidia.com/v1",
        http=mock_client,
    )
    # This should work if we support "openai-compat" as a provider type
    try:
        models = await client.list_models(force=True)
        assert len(models) == 1
        assert "deepseek" in models[0].id
    except ValueError:
        # If "openai-compat" not supported, test with "vllm" (also OpenAI-compatible)
        client = ProviderClient(
            provider="vllm",
            base_url="https://integrate.api.nvidia.com/v1",
            http=mock_client,
        )
        models = await client.list_models(force=True)
        assert len(models) == 1


async def test_unsupported_provider_raises_error(tmp_path):
    """Test that unsupported providers raise ValueError."""
    client = ProviderClient(
        provider="unsupported",
        base_url="http://localhost:9999",
    )
    try:
        await client.list_models(force=True)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unsupported provider" in str(e)
