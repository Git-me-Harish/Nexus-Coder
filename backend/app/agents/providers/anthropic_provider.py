"""
Anthropic provider, with native tool use.

Wire shape: tool calls arrive as `tool_use` content blocks on the assistant
turn, and results go back as `tool_result` blocks inside a *user* message --
not a dedicated "tool" role. `_to_anthropic` below is what maps our
normalized AgentMessage onto that.
"""
import json
from collections.abc import AsyncIterator

import anthropic

from app.agents.providers.base import (
    AgentMessage,
    CompletionUsage,
    ModelProvider,
    ProviderError,
    StreamChunk,
    ToolCall,
    ToolSpec,
)

MAX_TOKENS = 8192


def _to_anthropic(messages: list[AgentMessage]) -> list[dict]:
    """Normalized messages -> Anthropic's content-block format."""
    out: list[dict] = []
    for m in messages:
        role = m.get("role")

        if role == "tool":
            # Results ride on a user turn as tool_result blocks.
            out.append({
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": r.call_id,
                        "content": r.content,
                        **({"is_error": True} if r.is_error else {}),
                    }
                    for r in m.get("tool_results", [])
                ],
            })
            continue

        if role == "assistant" and m.get("tool_calls"):
            blocks: list[dict] = []
            if m.get("content"):
                blocks.append({"type": "text", "text": m["content"]})
            blocks.extend(
                {"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments}
                for c in m["tool_calls"]
            )
            out.append({"role": "assistant", "content": blocks})
            continue

        # Anthropic rejects empty content; a turn that produced only tool
        # calls has already been handled above, so anything empty here is
        # genuinely nothing worth sending.
        if m.get("content"):
            out.append({"role": role, "content": m["content"]})

    return out


class AnthropicProvider(ModelProvider):
    name = "anthropic"

    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

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
            "max_tokens": MAX_TOKENS,
            "system": system_prompt,
            "messages": _to_anthropic(messages),
        }
        if tools:
            request["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in tools
            ]

        try:
            async with self._client.messages.stream(**request) as stream:
                async for text in stream.text_stream:
                    yield StreamChunk(delta=text)

                final = await stream.get_final_message()
                self.usage = CompletionUsage(
                    tokens_in=final.usage.input_tokens, tokens_out=final.usage.output_tokens
                )

                calls = [
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        # SDK gives dict input already; guard the string case
                        # rather than trust it, since a malformed arg blob
                        # should surface as a tool error, not a crash here.
                        arguments=block.input if isinstance(block.input, dict) else json.loads(block.input or "{}"),
                    )
                    for block in final.content
                    if block.type == "tool_use"
                ]
                yield StreamChunk(finished=True, tool_calls=calls, stop_reason=final.stop_reason)

        except anthropic.AuthenticationError as exc:
            raise ProviderError(self.name, "Invalid API key") from exc
        except anthropic.APIError as exc:
            raise ProviderError(self.name, str(exc)) from exc
