import httpx
import pytest
import respx

from backend.providers import ProviderClient, _guess_vision


pytestmark = pytest.mark.asyncio


async def test_guess_vision_hints():
    # Async so the module-level asyncio mark applies cleanly; body is sync.
    assert _guess_vision("llava:7b") is True
    assert _guess_vision("qwen2.5-vl-7b") is True
    assert _guess_vision("mistral-7b") is None


@respx.mock
async def test_list_ollama():
    respx.get("http://localhost:11434/api/tags").mock(
        return_value=httpx.Response(
            200,
            json={
                "models": [
                    {"name": "llama3.1:8b", "details": {}},
                    {"name": "llava:7b", "details": {}},
                ]
            },
        )
    )
    client = ProviderClient(provider="ollama", base_url="http://localhost:11434")
    models = await client.list_models(force=True)
    assert [m.id for m in models] == ["llama3.1:8b", "llava:7b"]
    assert models[1].supports_vision is True
    await client.close()


@respx.mock
async def test_list_vllm():
    respx.get("http://localhost:8000/v1/models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "qwen2.5-7b"}]})
    )
    client = ProviderClient(provider="vllm", base_url="http://localhost:8000")
    models = await client.list_models(force=True)
    assert models[0].id == "qwen2.5-7b"
    await client.close()


@respx.mock
async def test_cache_is_hit():
    route = respx.get("http://localhost:11434/api/tags").mock(
        return_value=httpx.Response(200, json={"models": [{"name": "a"}]})
    )
    client = ProviderClient(provider="ollama", base_url="http://localhost:11434")
    await client.list_models(force=True)
    await client.list_models()  # should not call again
    assert route.call_count == 1
    await client.close()
