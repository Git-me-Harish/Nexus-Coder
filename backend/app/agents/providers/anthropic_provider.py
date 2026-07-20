from collections.abc import AsyncIterator

import anthropic

from app.agents.providers.base import CompletionUsage, ModelProvider, ProviderError, StreamChunk


class AnthropicProvider(ModelProvider):
    name = "anthropic"

    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def stream_completion(
        self, *, system_prompt: str, messages: list[dict], model_id: str
    ) -> AsyncIterator[StreamChunk]:
        try:
            async with self._client.messages.stream(
                model=model_id,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            ) as stream:
                async for text in stream.text_stream:
                    yield StreamChunk(delta=text)
                final = await stream.get_final_message()
                self.usage = CompletionUsage(
                    tokens_in=final.usage.input_tokens, tokens_out=final.usage.output_tokens
                )
        except anthropic.AuthenticationError as exc:
            raise ProviderError(self.name, "Invalid API key") from exc
        except anthropic.APIError as exc:
            raise ProviderError(self.name, str(exc)) from exc