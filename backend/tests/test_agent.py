import json
from dataclasses import dataclass
from typing import Any

import pytest

from backend.agent import Agent, ToolSpec


pytestmark = pytest.mark.asyncio


@dataclass
class _Fn:
    name: str
    arguments: str


@dataclass
class _TC:
    id: str
    function: _Fn
    type: str = "function"


@dataclass
class _Msg:
    content: str | None = None
    tool_calls: list[_TC] | None = None


@dataclass
class _Choice:
    message: _Msg
    finish_reason: str


@dataclass
class _Completion:
    choices: list[_Choice]


class _FakeCompletions:
    def __init__(self, script):
        self._script = list(script)

    async def create(self, **kwargs):
        return self._script.pop(0)


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


class _FakeOpenAI:
    def __init__(self, completions):
        self.chat = _FakeChat(completions)


def _patch_agent_client(agent: Agent, completions) -> None:
    agent._client = lambda: _FakeOpenAI(completions)  # type: ignore[assignment]


async def test_agent_plain_response(monkeypatch):
    completions = _FakeCompletions(
        [
            _Completion(
                [_Choice(_Msg(content="hi there"), finish_reason="stop")]
            )
        ]
    )
    agent = Agent(model="x", base_url="http://x", system_prompt="sys")
    _patch_agent_client(agent, completions)
    events = [ev async for ev in agent.run_stream("hello")]
    assert any(ev["type"] == "final" and ev["text"] == "hi there" for ev in events)


async def test_agent_dispatches_tool_call():
    call = _TC(id="t1", function=_Fn(name="echo", arguments=json.dumps({"msg": "hi"})))
    completions = _FakeCompletions(
        [
            _Completion(
                [_Choice(_Msg(content=None, tool_calls=[call]), finish_reason="tool_calls")]
            ),
            _Completion(
                [_Choice(_Msg(content="done"), finish_reason="stop")]
            ),
        ]
    )
    seen: dict[str, Any] = {}

    async def echo(args):
        seen["args"] = args
        return {"ok": True, "echo": args["msg"]}

    agent = Agent(model="x", base_url="http://x", system_prompt="sys")
    agent.register(
        ToolSpec(
            name="echo",
            description="echo",
            parameters={"type": "object", "properties": {"msg": {"type": "string"}}, "required": ["msg"]},
            handler=echo,
        )
    )
    _patch_agent_client(agent, completions)

    events = [ev async for ev in agent.run_stream("do it")]
    types = [e["type"] for e in events]
    assert "tool_call" in types
    assert "tool_result" in types
    assert seen["args"] == {"msg": "hi"}
    assert any(e.get("text") == "done" for e in events)
