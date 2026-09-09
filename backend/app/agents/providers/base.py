"""
Common provider interface.

Every provider streams text deltas and, when tools are offered, surfaces the
model's tool calls in one normalized shape, so the ReAct loop in
app/agents/graph.py never needs to know which vendor served the request.

WHY THE NORMALIZED MESSAGE FORMAT MATTERS
-----------------------------------------
The four providers disagree about how a tool round-trip is represented on
the wire:

  - Anthropic: assistant content blocks (`tool_use`); results come back as
    `tool_result` blocks inside a *user* message.
  - OpenAI / Groq: `tool_calls` on the assistant message; results come back
    as separate messages with `role: "tool"` and a `tool_call_id`.
  - Gemini: `functionCall` parts on a `model` turn, results as
    `functionResponse` parts on a *user* turn, and no `system` role at all.

Rather than leak that into the graph, the agent speaks one internal dialect
(`AgentMessage` below) and each provider translates on the way in and out.
That is also what keeps provider fallback working once tools are in play: a
conversation started on Anthropic can be replayed to OpenAI mid-session,
because what we persist and resend is provider-neutral.
"""
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict


@dataclass
class ToolSpec:
    """A tool offered to the model. `input_schema` is JSON Schema."""
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class ToolCall:
    """A tool invocation the model asked for."""
    id: str
    name: str
    arguments: dict[str, Any]

    provider_meta: dict[str, Any] = field(default_factory=dict)
    """
    Opaque, provider-specific data that must be echoed back verbatim when this
    call is replayed, and ignored by every other provider.

    Gemini 3.x is why this exists: it stamps each `functionCall` part with a
    `thought_signature` and rejects the turn with a 400 if the signature is
    missing when you send that call back. Without carrying it here, Gemini
    could not sustain a multi-step ReAct loop at all -- step 2 would fail on
    the history step 1 produced.
    """


@dataclass
class ToolResult:
    call_id: str
    name: str
    content: str
    is_error: bool = False


class AgentMessage(TypedDict, total=False):
    """
    One turn in the normalized conversation.

    role "assistant" may carry `tool_calls`; role "tool" carries the matching
    `tool_results`. Everything else is plain `content` text.
    """
    role: Literal["user", "assistant", "tool"]
    content: str
    tool_calls: list[ToolCall]
    tool_results: list[ToolResult]


@dataclass
class StreamChunk:
    delta: str = ""
    finished: bool = False
    reset: bool = False
    """
    Signals that every delta yielded so far for this call is invalid and the
    consumer must discard its accumulator before applying anything further.

    Emitted by the router when a provider dies *after* it already streamed
    partial text and we fall back to another provider: without this the
    consumer would concatenate the aborted attempt's partial output onto the
    replacement provider's complete response and persist the garbled result.
    A `reset` chunk carries no text of its own (`delta` is always "").
    """

    tool_calls: list[ToolCall] = field(default_factory=list)
    """
    Tool calls the model requested, emitted once its turn completes. Non-empty
    means the turn ended by asking to act: the caller must execute these and
    send the results back as a `role: "tool"` message before the model can
    continue.
    """

    stop_reason: str | None = None


@dataclass
class CompletionUsage:
    tokens_in: int
    tokens_out: int


class ModelProvider(ABC):
    name: str

    usage: CompletionUsage | None = None

    accepts_foreign_tool_calls: bool = True
    """
    Whether this provider will accept a conversation containing tool calls
    that a DIFFERENT provider produced.

    Most will: an OpenAI-shaped `tool_calls` entry is just data. Gemini will
    not -- it requires its own `thought_signature` on every replayed
    functionCall part and 400s without it, and a signature from another vendor
    does not exist. The router consults this before falling back mid-tool-
    conversation; without it, a transient failure on the primary provider
    turns a working agent turn into a hard error, which is exactly what
    happened the first time this ran for real.
    """

    @abstractmethod
    async def stream_completion(
        self,
        *,
        system_prompt: str,
        messages: list[AgentMessage],
        model_id: str,
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Yields text deltas as they arrive, then a final chunk carrying any
        `tool_calls` the model requested. `usage` is populated once the
        generator is exhausted.

        When `tools` is None the provider must not send a tools field at all --
        offering tools changes how a model answers even when it uses none, so
        the non-agentic phases must not silently pay that.
        """
        ...


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
