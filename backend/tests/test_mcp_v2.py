"""Tests for MCP Server Integration feature (Phase 2, Feature #8) v2 - rewritten.

Using the actual ClientSessionGroup API from MCP Python SDK.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from pathlib import Path

from backend.permissions import PermissionResult, PermissionGate


@pytest.fixture(scope="module", autouse=True)
def run_server():
    yield


class MockTool:
    def __init__(self, name, description, input_schema):
        self.name = name
        self.description = description
        self.inputSchema = input_schema


class MockCallResult:
    def __init__(self, content, is_error=False):
        self.content = content
        self.isError = is_error


class MockContent:
    def __init__(self, text):
        self.text = text


class TestMCPManagerV2:
    @pytest.fixture
    def mock_group(self):
        group = MagicMock()
        mock_session = MagicMock()
        mock_session.tools = {}
        
        group.connect_to_server = AsyncMock(return_value=mock_session)
        group.disconnect_from_server = AsyncMock()
        
        mock_call_result = MockCallResult([MockContent("result")])
        group.call_tool = AsyncMock(return_value=mock_call_result)
        
        group.tools = {
            "server1_browse": MockTool("server1_browse", "Browse", {"type": "object"})
        }
        group.sessions = []
        
        return group

    @pytest.fixture
    def mock_exit_stack(self):
        stack = AsyncMock()
        stack.__aenter__ = AsyncMock(return_value=stack)
        stack.__aexit__ = AsyncMock()
        return stack

    @pytest.mark.asyncio
    async def test_start_connects_enabled_servers(self, mock_group, mock_exit_stack):
        with patch('backend.mcp.contextlib.AsyncExitStack', return_value=mock_exit_stack):
            with patch('backend.mcp.ClientSessionGroup', return_value=mock_group):
                from backend.mcp import MCPManager
                manager = MCPManager()
                
                config = {
                    "mcp": {
                        "server1": {"command": "npx", "args": ["serve"], "disabled": False},
                        "server2": {"command": "python", "args": ["server.py"], "disabled": True}
                    }
                }
                
                await manager.start(config)
                
                assert mock_group.connect_to_server.call_count == 1

    @pytest.mark.asyncio
    async def test_stop_closes_exit_stack(self, mock_group, mock_exit_stack):
        with patch('backend.mcp.contextlib.AsyncExitStack', return_value=mock_exit_stack):
            with patch('backend.mcp.ClientSessionGroup', return_value=mock_group):
                from backend.mcp import MCPManager
                manager = MCPManager()
                manager._group = mock_group
                manager._exit_stack = mock_exit_stack
                
                await manager.stop()
                
                mock_exit_stack.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_tool_specs_namespacing(self, mock_group):
        mock_group.tools = {
            "server1_browse": MockTool("server1_browse", "Browse a page", {"type": "object"}),
            "server1_search": MockTool("server1_search", "Search", {"type": "object"})
        }
        
        with patch('backend.mcp.ClientSessionGroup', return_value=mock_group):
            from backend.mcp import MCPManager
            manager = MCPManager()
            manager._group = mock_group
            
            mock_gate = MagicMock()
            mock_gate.check = lambda *args, **kwargs: PermissionResult(True, "allowed")
            
            tool_specs = manager.get_tool_specs(mock_gate)
            
            assert "server1_browse" in tool_specs
            assert "server1_search" in tool_specs

    @pytest.mark.asyncio
    async def test_get_status_returns_server_list(self, mock_group):
        with patch('backend.mcp.ClientSessionGroup', return_value=mock_group):
            from backend.mcp import MCPManager
            manager = MCPManager()
            manager._server_status = {
                "server1": {"status": "connected", "tools_count": 3},
                "server2": {"status": "disconnected", "tools_count": 0}
            }
            manager._server_params = {
                "server1": {"command": "npx"},
                "server2": {"command": "python"}
            }
            
            status = manager.get_status()
            
            assert len(status) == 2
            names = [s["name"] for s in status]
            assert "server1" in names
            assert "server2" in names

    @pytest.mark.asyncio
    async def test_add_server_stores_params(self, mock_group, mock_exit_stack):
        mock_session = MagicMock()
        mock_group.connect_to_server = AsyncMock(return_value=mock_session)
        
        with patch('backend.mcp.contextlib.AsyncExitStack', return_value=mock_exit_stack):
            with patch('backend.mcp.ClientSessionGroup', return_value=mock_group):
                from backend.mcp import MCPManager
                manager = MCPManager()
                manager._group = mock_group
                manager._server_params = {}
                
                await manager.add_server("new-server", {"command": "npx", "args": ["serve"]})
                
                assert "new-server" in manager._server_params
                mock_group.connect_to_server.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_server_removes_from_dicts(self, mock_group):
        with patch('backend.mcp.ClientSessionGroup', return_value=mock_group):
            from backend.mcp import MCPManager
            manager = MCPManager()
            manager._sessions = {"test-server": MagicMock()}
            manager._server_params = {"test-server": {"command": "npx"}}
            manager._server_status = {"test-server": "connected"}
            
            await manager.remove_server("test-server")
            
            assert "test-server" not in manager._sessions
            assert "test-server" not in manager._server_params

    @pytest.mark.asyncio
    async def test_start_server_reconnects(self, mock_group):
        mock_session = MagicMock()
        mock_list_result = MagicMock()
        mock_list_result.tools = []
        mock_session.list_tools = AsyncMock(return_value=mock_list_result)
        mock_group.connect_to_server = AsyncMock(return_value=mock_session)
        
        with patch('backend.mcp.ClientSessionGroup', return_value=mock_group):
            from backend.mcp import MCPManager
            manager = MCPManager()
            manager._group = mock_group
            manager._server_params = {"server1": {"command": "npx"}}
            manager._sessions = {}
            
            await manager.start_server("server1")
            
            assert "server1" in manager._sessions

    @pytest.mark.asyncio
    async def test_start_server_unknown_raises(self, mock_group):
        with patch('backend.mcp.ClientSessionGroup', return_value=mock_group):
            from backend.mcp import MCPManager
            manager = MCPManager()
            manager._server_params = {}
            
            with pytest.raises(ValueError):
                await manager.start_server("unknown-server")

    @pytest.mark.asyncio
    async def test_stop_server_disconnects(self, mock_group):
        mock_session = MagicMock()
        
        with patch('backend.mcp.ClientSessionGroup', return_value=mock_group):
            from backend.mcp import MCPManager
            manager = MCPManager()
            manager._group = mock_group
            manager._sessions = {"server1": mock_session}
            manager._server_status = {"server1": {"status": "connected", "tools_count": 0}}
            
            await manager.stop_server("server1")
            
            mock_group.disconnect_from_server.assert_called_once_with(mock_session)


class TestMCPPermissionGate:
    @pytest.mark.asyncio
    async def test_permission_denied_returns_error(self):
        from backend.mcp import MCPManager
        
        mock_group = MagicMock()
        mock_group.tools = {
            "secret_tool": MockTool("secret_tool", "Secret", {"type": "object"})
        }
        mock_call_result = MockCallResult([MockContent("secret result")])
        mock_group.call_tool = AsyncMock(return_value=mock_call_result)
        
        with patch('backend.mcp.ClientSessionGroup', return_value=mock_group):
            manager = MCPManager()
            manager._group = mock_group
            
            mock_gate = MagicMock()
            mock_gate.check = lambda *args, **kwargs: PermissionResult(False, "denied")
            
            tool_specs = manager.get_tool_specs(mock_gate)
            
            handler = tool_specs["secret_tool"].handler
            result = await handler({"arg": "value"})
            
            assert "Permission denied" in result.get("output", "")

    @pytest.mark.asyncio
    async def test_mcp_error_returns_error_flag(self):
        from backend.mcp import MCPManager
        
        mock_group = MagicMock()
        mock_group.tools = {
            "test_tool": MockTool("test_tool", "Test", {"type": "object"})
        }
        mock_call_result = MockCallResult([MockContent("error")], is_error=True)
        mock_group.call_tool = AsyncMock(return_value=mock_call_result)
        
        with patch('backend.mcp.ClientSessionGroup', return_value=mock_group):
            manager = MCPManager()
            manager._group = mock_group
            
            mock_gate = MagicMock()
            mock_gate.check = lambda *args, **kwargs: PermissionResult(True, "allowed")
            
            tool_specs = manager.get_tool_specs(mock_gate)
            
            handler = tool_specs["test_tool"].handler
            result = await handler({})
            
            assert result.get("error") is True

    @pytest.mark.asyncio
    async def test_generic_exception_returns_error(self):
        from backend.mcp import MCPManager
        
        mock_group = MagicMock()
        mock_group.tools = {
            "test_tool": MockTool("test_tool", "Test", {"type": "object"})
        }
        mock_group.call_tool = AsyncMock(side_effect=Exception("Something went wrong"))
        
        with patch('backend.mcp.ClientSessionGroup', return_value=mock_group):
            manager = MCPManager()
            manager._group = mock_group
            
            mock_gate = MagicMock()
            mock_gate.check = lambda *args, **kwargs: PermissionResult(True, "allowed")
            
            tool_specs = manager.get_tool_specs(mock_gate)
            
            handler = tool_specs["test_tool"].handler
            result = await handler({})
            
            assert result.get("error") is True
            assert "Something went wrong" in result.get("output", "")