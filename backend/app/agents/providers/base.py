"""Common provider interface — every provider streams (role, delta) chunks
and returns final usage counts, so the graph node and the SSE route don't
need to know which vendor served the request."""
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass
class StreamChunk:
    delta: str
    finished: bool = False


@dataclass
class CompletionUsage:
    tokens_in: int
    tokens_out: int


class ModelProvider(ABC):
    name: str

    @abstractmethod
    async def stream_completion(
        self, *, system_prompt: str, messages: list[dict], model_id: str
    ) -> AsyncIterator[StreamChunk]:
        """Yields text deltas; the last yielded chunk carries usage via
        the caller reading `.usage` populated after the generator exhausts."""
        ...

    usage: CompletionUsage | None = None


class ProviderError(RuntimeError):
    def __init__(self, provider: str, detail: str):
        super().__init__(f"[{provider}] {detail}")
        self.provider = provider


class ProviderNotConfiguredError(ProviderError):
    """Raised when no usable API key exists for this provider/tenant --
    distinct from a transient failure (rate limit, outage) so the stream
    route can tell the user exactly what to do (configure a key) instead
    of a generic 'try again'."""
    def __init__(self, provider: str):
        super().__init__(provider, f"No API key configured for {provider}")