"""
Groq is OpenAI-API-compatible (same request/response shape, different
base_url) -- reuses the openai SDK rather than a separate dependency.
"""
from collections.abc import AsyncIterator

from openai import APIError, AsyncOpenAI, AuthenticationError

from app.agents.providers.base import CompletionUsage, ModelProvider, ProviderError, StreamChunk

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqProvider(ModelProvider):
    name = "groq"

    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=GROQ_BASE_URL)

    async def stream_completion(
        self, *, system_prompt: str, messages: list[dict], model_id: str
    ) -> AsyncIterator[StreamChunk]:
        try:
            stream = await self._client.chat.completions.create(
                model=model_id,
                messages=[{"role": "system", "content": system_prompt}, *messages],
                stream=True,
                stream_options={"include_usage": True},
            )
            tokens_in = tokens_out = 0
            async for chunk in stream:
                if chunk.usage:
                    tokens_in, tokens_out = chunk.usage.prompt_tokens, chunk.usage.completion_tokens
                if chunk.choices and chunk.choices[0].delta.content:
                    yield StreamChunk(delta=chunk.choices[0].delta.content)
            self.usage = CompletionUsage(tokens_in=tokens_in, tokens_out=tokens_out)
        except AuthenticationError as exc:
            raise ProviderError(self.name, "Invalid API key") from exc
        except APIError as exc:
            raise ProviderError(self.name, str(exc)) from exc