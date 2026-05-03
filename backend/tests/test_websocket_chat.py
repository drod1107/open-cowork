"""Tests for WebSocket chat flow using websockets library.

Tests the actual WebSocket endpoint behavior.
"""
import asyncio
import json
import pytest


pytestmark = pytest.mark.asyncio


async def test_websocket_connect_and_receive_pong():
    """Verify WebSocket connection works and responds to ping."""
    import websockets

    uri = "ws://localhost:7337/ws"
    try:
        async with websockets.connect(uri, timeout=2) as ws:
            await ws.send(json.dumps({"type": "ping"}))
            response = await asyncio.wait_for(ws.recv(), timeout=2)
            data = json.loads(response)
            assert data["type"] == "pong"
    except (ConnectionRefusedError, OSError):
        pytest.skip("Backend server not running on port 7337")


async def test_stop_message_accepted():
    """Verify stop message is accepted and returns final message."""
    import websockets

    uri = "ws://localhost:7337/ws"
    try:
        async with websockets.connect(uri, timeout=2) as ws:
            await ws.send(json.dumps({"type": "stop"}))
            response = await asyncio.wait_for(ws.recv(), timeout=2)
            data = json.loads(response)
            assert data["type"] == "final"
            assert "stopped by user" in data["text"]
    except (ConnectionRefusedError, OSError):
        pytest.skip("Backend server not running on port 7337")


async def test_invalid_json_returns_error():
    """Verify bad JSON returns error message."""
    import websockets

    uri = "ws://localhost:7337/ws"
    try:
        async with websockets.connect(uri, timeout=2) as ws:
            await ws.send("not valid json")
            response = await asyncio.wait_for(ws.recv(), timeout=2)
            data = json.loads(response)
            assert data["type"] == "error"
            assert "bad json" in data["error"]
    except (ConnectionRefusedError, OSError):
        pytest.skip("Backend server not running on port 7337")


async def test_unknown_message_type_returns_error():
    """Verify unknown message type returns error."""
    import websockets

    uri = "ws://localhost:7337/ws"
    try:
        async with websockets.connect(uri, timeout=2) as ws:
            await ws.send(json.dumps({"type": "unknown_type", "data": "test"}))
            response = await asyncio.wait_for(ws.recv(), timeout=2)
            data = json.loads(response)
            assert data["type"] == "error"
            assert "unknown message type" in data["error"]
    except (ConnectionRefusedError, OSError):
        pytest.skip("Backend server not running on port 7337")


async def test_chat_message_accepted():
    """Verify chat message is accepted (may fail without model selected)."""
    import websockets

    uri = "ws://localhost:7337/ws"
    try:
        async with websockets.connect(uri, timeout=2) as ws:
            await ws.send(json.dumps({"type": "chat", "text": "hello"}))
            # Should receive some response
            response = await asyncio.wait_for(ws.recv(), timeout=2)
            data = json.loads(response)
            assert "type" in data
    except (ConnectionRefusedError, OSError):
        pytest.skip("Backend server not running on port 7337")
