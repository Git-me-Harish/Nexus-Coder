"""
Gemini via the `google-genai` SDK (Google's current unified client, not the
deprecated `google-generativeai`).

Its shape diverges from the other three in three ways that all have to be
handled here rather than leaked upward:
  - no "system" role: system instructions go in GenerateContentConfig
  - the assistant role is called "model", not "assistant"
  - tool calls are `function_call` parts on a model turn, and results are
    `function_response` parts on a *user* turn, correlated by function NAME
    rather than by a call id
"""
import logging
from collections.abc import AsyncIterator

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from app.agents.providers.base import (
    AgentMessage,
    CompletionUsage,
    ModelProvider,
    ProviderError,
    StreamChunk,
    ToolCall,
    ToolSpec,
)

logger = logging.getLogger("nexus.providers.gemini")

MAX_TOKENS = 8192


def _to_contents(messages: list[AgentMessage]) -> list[genai_types.Content]:
    contents: list[genai_types.Content] = []
    for m in messages:
        role = m.get("role")

        if role == "tool":
            contents.append(genai_types.Content(
                role="user",
                parts=[
                    genai_types.Part(
                        function_response=genai_types.FunctionResponse(
                            name=r.name,
                            response={"error": r.content} if r.is_error else {"result": r.content},
                        )
                    )
                    for r in m.get("tool_results", [])
                ],
            ))
            continue

        if role == "assistant" and m.get("tool_calls"):
            parts: list[genai_types.Part] = []
            if m.get("content"):
                parts.append(genai_types.Part(text=m["content"]))
            for c in m["tool_calls"]:
                # The signature Gemini stamped on this call when it produced
                # it. It is REQUIRED on replay -- omitting it is a 400, not a
                # soft warning -- so it round-trips through provider_meta.
                # Absent for a call another provider made; see
                # accepts_foreign_tool_calls below for how that case is kept
                # from reaching us at all.
                signature = (c.provider_meta or {}).get("thought_signature")
                parts.append(genai_types.Part(
                    function_call=genai_types.FunctionCall(name=c.name, args=c.arguments),
                    **({"thought_signature": signature} if signature else {}),
                ))
            contents.append(genai_types.Content(role="model", parts=parts))
            continue

        if m.get("content"):
            contents.append(genai_types.Content(
                role="model" if role == "assistant" else "user",
                parts=[genai_types.Part(text=m["content"])],
            ))

    return contents


def _to_tools(tools: list[ToolSpec]) -> list[genai_types.Tool]:
    return [
        genai_types.Tool(function_declarations=[
            genai_types.FunctionDeclaration(
                name=t.name, description=t.description, parameters_json_schema=t.input_schema
            )
            for t in tools
        ])
    ]


class GeminiProvider(ModelProvider):
    name = "gemini"

    #: Gemini 3.x requires its own thought_signature on every replayed
    #: functionCall part. A call produced by Anthropic/OpenAI/Groq has no such
    #: signature and never can, so handing Gemini that history is a guaranteed
    #: 400 -- the router must not fall back to it mid-tool-conversation.
    accepts_foreign_tool_calls = False

    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)

    async def stream_completion(
        self,
        *,
        system_prompt: str,
        messages: list[AgentMessage],
        model_id: str,
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        config_kwargs: dict = {
            "system_instruction": system_prompt,
            "max_output_tokens": MAX_TOKENS,
        }
        if tools:
            config_kwargs["tools"] = _to_tools(tools)

        calls: list[ToolCall] = []
        tokens_in = tokens_out = 0
        stop_reason = None

        try:
            stream = await self._client.aio.models.generate_content_stream(
                model=model_id,
                contents=_to_contents(messages),
                config=genai_types.GenerateContentConfig(**config_kwargs),
            )

            async for chunk in stream:
                # Read parts directly rather than `chunk.text`: the SDK's text
                # accessor warns or errors on a chunk whose parts are function
                # calls rather than text, which is exactly the agentic path.
                for candidate in getattr(chunk, "candidates", None) or []:
                    if getattr(candidate, "finish_reason", None):
                        stop_reason = str(candidate.finish_reason)
                    content = getattr(candidate, "content", None)
                    for part in (getattr(content, "parts", None) or []):
                        if getattr(part, "text", None):
                            yield StreamChunk(delta=part.text)
                        fc = getattr(part, "function_call", None)
                        if fc is not None and fc.name:
                            signature = getattr(part, "thought_signature", None)
                            calls.append(ToolCall(
                                # Gemini correlates results by name, not id;
                                # a synthetic id keeps our normalized shape
                                # uniform across providers.
                                id=f"gemini_{fc.name}_{len(calls)}",
                                name=fc.name,
                                arguments=dict(fc.args or {}),
                                # Captured here so the next step of the ReAct
                                # loop can hand it straight back; Gemini 400s
                                # on a replayed call without it.
                                provider_meta={"thought_signature": signature} if signature else {},
                            ))

                usage = getattr(chunk, "usage_metadata", None)
                if usage:
                    tokens_in = usage.prompt_token_count or tokens_in
                    tokens_out = usage.candidates_token_count or tokens_out

            self.usage = CompletionUsage(tokens_in=tokens_in, tokens_out=tokens_out)
            yield StreamChunk(finished=True, tool_calls=calls, stop_reason=stop_reason)

        except genai_errors.ClientError as exc:
            if exc.code in (401, 403):
                raise ProviderError(self.name, "Invalid API key") from exc
            raise ProviderError(self.name, str(exc)) from exc
        except genai_errors.APIError as exc:
            raise ProviderError(self.name, str(exc)) from exc
