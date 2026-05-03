"""OpenCowork agent loop.

We talk directly to the provider's OpenAI-compatible endpoint via the
`openai` SDK and dispatch tool calls ourselves. This mirrors Alejandro
AO's tutorial pattern, keeps the loop easy to reason about, and avoids
tight coupling to a specific `openai-agents` SDK version.

`Agent.run_stream` is an async generator yielding dict events. The
FastAPI WebSocket hub relays these to the frontend verbatim:

{"type": "token", "text": "..."}
{"type": "tool_call", "tool": "shell", "input": {...}}
{"type": "tool_result", "tool": "shell", "output": {...}}
{"type": "permission_request", "request": {...}}
{"type": "final", "text": "..."}
{"type": "error", "error": "..."}

The agent does not care *how* tool calls are routed — tools are provided
as a dict of name -> async callable. This makes mocking trivial in
tests.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

ToolFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolFn

    def to_openai(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """Rough token count: sum of len(content) // 4 across all messages."""
    total = 0
    for m in messages:
        content = m.get("content", "")
        if content:
            total += len(content) // 4
    return total


def _is_ollama(base_url: str) -> bool:
    """Heuristic: Ollama typically runs on localhost:11434."""
    return "11434" in base_url or "localhost" in base_url


@dataclass
class Agent:
    model: str
    base_url: str
    system_prompt: str
    tools: dict[str, ToolSpec] = field(default_factory=dict)
    max_turns: int = 50
    num_ctx: int = 8192
    api_key: str = "sk-opencowork-local"

    def _client(self) -> AsyncOpenAI:
        return AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)

    def register(self, spec: ToolSpec) -> None:
        self.tools[spec.name] = spec

    async def run_stream(
        self,
        user_message: str,
        history: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        client = self._client()
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        tools_payload = [spec.to_openai() for spec in self.tools.values()] or None
        logger.info("agent starting: model=%s tools=%s msg_len=%d", self.model, list(self.tools.keys()), len(messages))

        create_kwargs: dict[str, Any] = dict(
            model=self.model,
            messages=messages,
            tools=tools_payload,
            temperature=0.2,
        )
        if _is_ollama(self.base_url):
            create_kwargs["extra_body"] = {"options": {"num_ctx": self.num_ctx}}

        for turn in range(self.max_turns):
            logger.debug("agent turn %d: calling LLM", turn + 1)
            try:
                completion = await client.chat.completions.create(**create_kwargs)
            except asyncio.CancelledError:
                logger.warning("agent LLM call cancelled on turn %d", turn + 1)
                yield {"type": "error", "error": "agent stopped by user during LLM call"}
                return
            except Exception as exc:
                logger.error("agent LLM call failed: %s", exc)
                yield {"type": "error", "error": f"provider call failed: {exc}"}
                return

            choice = completion.choices[0]
            msg = choice.message
            assistant_entry: dict[str, Any] = {"role": "assistant"}
            if msg.content:
                logger.debug("agent token: %d chars", len(msg.content))
                yield {"type": "token", "text": msg.content}
                assistant_entry["content"] = msg.content
            if msg.tool_calls:
                assistant_entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]
            messages.append(assistant_entry)

            finish = choice.finish_reason or ""
            if not msg.tool_calls or finish == "stop":
                logger.info("agent finished after %d turns", turn + 1)
                yield {"type": "final", "text": msg.content or ""}
                return

            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                logger.info("agent tool_call: %s(%s)", name, json.dumps(args)[:200])
                yield {"type": "tool_call", "tool": name, "input": args}

                spec = self.tools.get(name)
                if spec is None:
                    result = {"ok": False, "error": f"unknown tool: {name}"}
                    logger.error("agent unknown tool: %s", name)
                else:
                    try:
                        result = await spec.handler(args)
                    except asyncio.CancelledError:
                        logger.warning("agent tool %s cancelled by user stop", name)
                        yield {"type": "error", "error": f"tool {name} cancelled by user stop"}
                        return
                    except Exception as exc: # pragma: no cover - defensive
                        result = {"ok": False, "error": str(exc)}
                        logger.error("agent tool %s failed: %s", name, exc)

                logger.info("agent tool_result: %s -> %s", name, json.dumps(result, default=str)[:200])
                yield {"type": "tool_result", "tool": name, "output": result}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": name,
                        "content": json.dumps(result, default=str),
                    }
                )

        logger.error("agent max_turns reached (%d)", self.max_turns)
        yield {"type": "error", "error": "max_turns reached"}
