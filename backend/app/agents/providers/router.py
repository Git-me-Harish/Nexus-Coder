"""
Provider fallback router. Resolves each provider's API key per-tenant
(the user's own configured credential, or the platform fallback -- see
credential_service.resolve_api_key) before instantiating that provider.

Two routing modes:
  - Normal model (e.g. "claude-sonnet-4-6"): try its home provider first,
    fall back through DEFAULT_FALLBACK_ORDER on ProviderError.
  - "nexus-prime" (provider "nexus" in the catalog -- not a real backend
    provider): auto-pick whichever real provider the tenant actually has
    a usable key for, in DEFAULT_FALLBACK_ORDER priority, using that
    provider's own default model. This is what the catalog's "auto-picks
    whichever configured provider is available" description promises --
    previously nothing implemented it, so selecting Nexus Prime just
    silently failed with no working backend behind it at all.

If NO provider in the chain has a usable key for this tenant, raises
ProviderNotConfiguredError -- distinct from a mid-stream failure, so the
caller can tell the user exactly what to fix (open Configure Models)
instead of a generic "try again."
"""
import logging
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.constants import DEFAULT_FALLBACK_ORDER, FALLBACK_MODEL_FOR_PROVIDER, MODEL_REGISTRY
from app.agents.providers.anthropic_provider import AnthropicProvider
from app.agents.providers.base import (
    AgentMessage,
    ModelProvider,
    ProviderError,
    ProviderNotConfiguredError,
    StreamChunk,
    ToolSpec,
)
from app.agents.providers.gemini_provider import GeminiProvider
from app.agents.providers.groq_provider import GroqProvider
from app.agents.providers.openai_provider import OpenAIProvider
from app.services import credential_service

logger = logging.getLogger("nexus.providers.router")

_PROVIDERS: dict[str, type[ModelProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "groq": GroqProvider,
    "gemini": GeminiProvider,
}


def _resolve_provider_order(model_id: str) -> tuple[list[str], bool]:
    """Returns (provider_order, is_auto_pick). nexus-prime has no fixed
    home provider -- it's a pure priority walk across whatever's configured."""
    if model_id == "nexus-prime":
        return DEFAULT_FALLBACK_ORDER, True

    entry = MODEL_REGISTRY.get(model_id)
    home_provider = entry["provider"] if entry else "anthropic"
    return [home_provider] + [p for p in DEFAULT_FALLBACK_ORDER if p != home_provider], False


async def route_and_stream(
    *, db: AsyncSession, tenant_id: str, system_prompt: str, messages: list[AgentMessage],
    model_id: str, fallback_log: list[dict] | None = None,
    tools: list[ToolSpec] | None = None,
) -> AsyncIterator[tuple[StreamChunk, ModelProvider]]:
    """
    `messages` is the normalized AgentMessage list (see providers/base.py) --
    provider-neutral on purpose, so a conversation that already contains tool
    calls can still be replayed to a different provider when the primary one
    fails mid-session.
    """
    order, is_auto_pick = _resolve_provider_order(model_id)

    last_error: Exception | None = None
    any_key_found = False

    # Once the conversation contains tool calls, not every provider can pick it
    # up: Gemini requires its own thought_signature on each replayed
    # functionCall and 400s on one another vendor produced. Filtering here --
    # rather than discovering it as a hard error at the end of the chain --
    # is what keeps a transient blip on the primary provider from turning a
    # working agent turn into a failed one.
    has_foreign_tool_calls = any(m.get("tool_calls") for m in messages)

    for i, provider_name in enumerate(order):
        provider_cls = _PROVIDERS.get(provider_name)
        if provider_cls is None:
            continue

        if has_foreign_tool_calls and i > 0 and not provider_cls.accepts_foreign_tool_calls:
            logger.info(
                "skipping %s in fallback: it cannot accept tool calls made by another provider",
                provider_name,
            )
            continue

        api_key = await credential_service.resolve_api_key(db, tenant_id, provider_name)
        if api_key is None:
            continue  # this provider isn't usable for this tenant at all -- skip, don't count as a "failure"
        any_key_found = True

        provider = provider_cls(api_key=api_key)
        effective_model_id = FALLBACK_MODEL_FOR_PROVIDER.get(provider_name, model_id) if (is_auto_pick or i > 0) else model_id

        if (is_auto_pick or i > 0) and fallback_log is not None:
            fallback_log.append({
                "requested_model": model_id,
                "fallback_provider": provider_name,
                "fallback_model": effective_model_id,
                "reason": "Auto-routing to configured provider." if is_auto_pick and i == 0 and last_error is None
                else (str(last_error) if last_error else "Primary provider unavailable."),
            })

        # Tracked per attempt: a provider that dies *after* emitting text
        # leaves partial output in the consumer's accumulator. Falling back
        # without telling the consumer to drop it produces a message that is
        # the aborted attempt's prefix glued onto the next provider's full
        # response -- garbage that then gets persisted, rendered, and parsed
        # for file blocks. The reset chunk below is that signal.
        emitted_any = False
        try:
            async for chunk in provider.stream_completion(
                system_prompt=system_prompt, messages=messages,
                model_id=effective_model_id, tools=tools,
            ):
                emitted_any = emitted_any or bool(chunk.delta)
                yield chunk, provider
            return
        except ProviderError as exc:
            last_error = exc
            if emitted_any:
                yield StreamChunk(delta="", reset=True), provider
            continue

    if not any_key_found:
        fallback_provider_name = order[0] if order else "anthropic"
        raise ProviderNotConfiguredError(fallback_provider_name)
    raise last_error or ProviderError("router", "No provider available")