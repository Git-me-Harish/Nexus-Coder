"""
Shared implementation for the OpenAI-compatible providers (OpenAI, Groq).

Groq exposes the same request/response shape at a different base_url, so the
streaming + tool-call-assembly logic lives here once. Previously both
providers carried their own near-identical copy; adding tool support to two
copies is exactly how they drift apart.

Wire shape: tool calls arrive as `tool_calls` on the assistant delta, and --
critically -- they arrive *fragmented across chunks*. Each delta carries an
`index` plus a slice of the JSON argument string, which must be concatenated
per index before it can be parsed. Assembling that correctly is the fiddly
part of this file.
"""
import json
import logging
from collections.abc import AsyncIterator

from openai import APIError, AsyncOpenAI, AuthenticationError

from app.agents.providers.base import (
    AgentMessage,
    CompletionUsage,
    ModelProvider,
    ProviderError,
    StreamChunk,
    ToolCall,
    ToolSpec,
)

logger = logging.getLogger("nexus.providers.openai_compat")

MAX_TOKENS = 8192


def to_openai_messages(system_prompt: str, messages: list[AgentMessage]) -> list[dict]:
    """Normalized messages -> OpenAI chat format."""
    out: list[dict] = [{"role": "system", "content": system_prompt}]
    for m in messages:
        role = m.get("role")

        if role == "tool":
            # One message per result, each keyed to its call id.
            for r in m.get("tool_results", []):
                out.append({"role": "tool", "tool_call_id": r.call_id, "content": r.content})
            continue

        if role == "assistant" and m.get("tool_calls"):
            out.append({
                "role": "assistant",
                # None, not "" -- the API rejects an empty-string content
                # paired with tool_calls.
                "content": m.get("content") or None,
                "tool_calls": [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                    }
                    for c in m["tool_calls"]
                ],
            })
            continue

        if m.get("content"):
            out.append({"role": role, "content": m["content"]})

    return out


def to_openai_tools(tools: list[ToolSpec]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {"name": t.name, "description": t.description, "parameters": t.input_schema},
        }
        for t in tools
    ]


class OpenAICompatibleProvider(ModelProvider):
    """Base for any provider speaking the OpenAI chat-completions dialect."""

    base_url: str | None = None

    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=self.base_url)

    async def stream_completion(
        self,
        *,
        system_prompt: str,
        messages: list[AgentMessage],
        model_id: str,
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        request: dict = {
            "model": model_id,
            "messages": to_openai_messages(system_prompt, messages),
            "max_completion_tokens": MAX_TOKENS,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            request["tools"] = to_openai_tools(tools)

        # Tool calls stream in fragments keyed by index: {index: {id, name, args_so_far}}.
        partial: dict[int, dict] = {}
        tokens_in = tokens_out = 0
        stop_reason = None

        try:
            stream = await self._client.chat.completions.create(**request)

            async for chunk in stream:
                if chunk.usage:
                    tokens_in = chunk.usage.prompt_tokens
                    tokens_out = chunk.usage.completion_tokens

                if not chunk.choices:
                    continue
                choice = chunk.choices[0]

                if choice.finish_reason:
                    stop_reason = choice.finish_reason

                delta = choice.delta
                if delta is None:
                    continue

                if delta.content:
                    yield StreamChunk(delta=delta.content)

                for tc in delta.tool_calls or []:
                    slot = partial.setdefault(tc.index, {"id": None, "name": "", "arguments": ""})
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function and tc.function.name:
                        slot["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        # Argument JSON arrives split across chunks; only the
                        # concatenation of every fragment is valid JSON.
                        slot["arguments"] += tc.function.arguments

            self.usage = CompletionUsage(tokens_in=tokens_in, tokens_out=tokens_out)
            yield StreamChunk(
                finished=True,
                tool_calls=self._assemble(partial),
                stop_reason=stop_reason,
            )

        except AuthenticationError as exc:
            raise ProviderError(self.name, "Invalid API key") from exc
        except APIError as exc:
            raise ProviderError(self.name, str(exc)) from exc

    def _assemble(self, partial: dict[int, dict]) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for index in sorted(partial):
            slot = partial[index]
            if not slot["name"]:
                continue
            raw = slot["arguments"] or "{}"
            try:
                arguments = json.loads(raw)
            except json.JSONDecodeError:
                # A truncated or malformed argument blob must not take down the
                # turn: surface it as a call with no arguments so the executor
                # reports a normal tool error the model can react to.
                logger.warning(
                    "%s: could not parse arguments for tool %s: %r", self.name, slot["name"], raw
                )
                arguments = {}
            if not isinstance(arguments, dict):
                arguments = {}
            calls.append(
                ToolCall(id=slot["id"] or f"call_{index}", name=slot["name"], arguments=arguments)
            )
        return calls
