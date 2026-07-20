"""
Gemini via the `google-genai` SDK (Google's current unified client, not
the deprecated `google-generativeai`). API shape differs from
OpenAI/Anthropic: no separate "system" role -- system instructions go in
GenerateContentConfig, and message history is a list of Content objects
with role "user"/"model" (not "assistant").

NOTE: this was written against the real SDK's method signatures (verified
via introspection: client.aio.models.generate_content_stream, response.text,
response.usage_metadata.{prompt,candidates}_token_count, and
google.genai.errors.ClientError for auth failures) but has not been
live-tested against the actual Gemini API in this environment -- there was
no API key available to test with. Treat the happy path as reviewed-but-
unverified rather than proven; if it misbehaves, the error handling below
at least fails as a normal ProviderError rather than crashing the stream.
"""
from collections.abc import AsyncIterator

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from app.agents.providers.base import CompletionUsage, ModelProvider, ProviderError, StreamChunk


class GeminiProvider(ModelProvider):
    name = "gemini"

    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)

    async def stream_completion(
        self, *, system_prompt: str, messages: list[dict], model_id: str
    ) -> AsyncIterator[StreamChunk]:
        # Gemini has no "system" role in the message list -- it's a
        # dedicated config field. "assistant" maps to "model".
        role_map = {"assistant": "model", "user": "user"}
        contents = [
            genai_types.Content(role=role_map.get(m["role"], "user"), parts=[genai_types.Part(text=m["content"])])
            for m in messages
        ]
        config = genai_types.GenerateContentConfig(system_instruction=system_prompt, max_output_tokens=4096)

        try:
            tokens_in = tokens_out = 0
            stream = await self._client.aio.models.generate_content_stream(
                model=model_id,
                contents=contents,
                config=config,
            )

            async for chunk in stream:
                if getattr(chunk, "text", None):
                    yield StreamChunk(delta=chunk.text)

                usage = getattr(chunk, "usage_metadata", None)
                if usage:
                    tokens_in = usage.prompt_token_count or tokens_in
                    tokens_out = usage.candidates_token_count or tokens_out

            self.usage = CompletionUsage(
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            )
        except genai_errors.ClientError as exc:
            if exc.code in (401, 403):
                raise ProviderError(self.name, "Invalid API key") from exc
            raise ProviderError(self.name, str(exc)) from exc
        except genai_errors.APIError as exc:
            raise ProviderError(self.name, str(exc)) from exc