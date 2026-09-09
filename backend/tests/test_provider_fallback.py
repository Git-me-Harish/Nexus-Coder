"""
Cross-provider fallback once tool calls are in play.

Regression suite for a failure found by running the real app: a transient
blip on the primary provider sent the chain to Gemini, which hard-rejected a
conversation containing tool calls another vendor had produced ("Function
call is missing a thought_signature"). A recoverable hiccup became a failed
turn, and no provider_fallback event ever reached the client to explain it.
"""
import pytest

from app.agents.providers import router as router_mod
from app.agents.providers.base import (
    CompletionUsage,
    ModelProvider,
    ProviderError,
    StreamChunk,
    ToolCall,
)
from app.agents.providers.gemini_provider import GeminiProvider
from app.agents.providers.groq_provider import GroqProvider
from app.agents.providers.openai_provider import OpenAIProvider


class _Fake(ModelProvider):
    name = "fake"
    fail = False

    def __init__(self, api_key: str) -> None:
        self.usage = CompletionUsage(tokens_in=1, tokens_out=1)

    async def stream_completion(self, *, system_prompt, messages, model_id, tools=None):
        if type(self).fail:
            raise ProviderError(self.name, "simulated outage")
            yield  # pragma: no cover -- keeps this an async generator
        yield StreamChunk(delta=f"from-{self.name}")
        yield StreamChunk(finished=True)


def _make(name, *, accepts_foreign=True, fail=False):
    return type(
        f"P_{name}", (_Fake,),
        {"name": name, "accepts_foreign_tool_calls": accepts_foreign, "fail": fail},
    )


TOOL_HISTORY = [
    {"role": "user", "content": "go"},
    {"role": "assistant", "content": "",
     "tool_calls": [ToolCall(id="c1", name="list_files", arguments={})]},
    {"role": "tool", "tool_results": []},
]


async def _drain(monkeypatch, providers, messages, model_id="claude-sonnet-5"):
    monkeypatch.setattr(router_mod, "_PROVIDERS", providers)
    monkeypatch.setattr(router_mod, "DEFAULT_FALLBACK_ORDER", list(providers))
    monkeypatch.setattr(
        router_mod, "FALLBACK_MODEL_FOR_PROVIDER", {p: f"{p}-model" for p in providers}
    )
    # Also patch the registry the router resolves a model's HOME provider
    # from; without it every fake model falls through to "anthropic" and the
    # chain order under test is not the one being exercised.
    monkeypatch.setattr(
        router_mod, "MODEL_REGISTRY",
        {f"{p}-model": {"provider": p, "context_window": 1000} for p in providers},
    )

    async def resolve(db, tenant_id, provider):
        return "key"

    monkeypatch.setattr(router_mod.credential_service, "resolve_api_key", resolve)

    log: list[dict] = []
    text, used = "", None
    async for chunk, provider in router_mod.route_and_stream(
        db=None, tenant_id="t", system_prompt="s", messages=messages,
        model_id=model_id, fallback_log=log,
    ):
        text += chunk.delta
        used = provider.name
    return text, used, log


@pytest.mark.asyncio
async def test_fallback_skips_a_provider_that_cannot_accept_foreign_tool_calls(monkeypatch):
    """The exact production failure: primary dies mid-tool-conversation and
    the only remaining provider is one that rejects foreign tool calls."""
    providers = {
        "primary": _make("primary", fail=True),
        "picky": _make("picky", accepts_foreign=False),
        "ok": _make("ok"),
    }
    text, used, _ = await _drain(monkeypatch, providers, TOOL_HISTORY, model_id="primary-model")

    assert used == "ok", "should have skipped the picky provider and kept going"
    assert text == "from-ok"


@pytest.mark.asyncio
async def test_a_picky_provider_is_still_usable_as_the_primary(monkeypatch):
    """The restriction is only about FOREIGN calls. A provider replaying its
    own tool calls (with its own signatures) must not be shut out."""
    providers = {"picky": _make("picky", accepts_foreign=False), "ok": _make("ok")}
    text, used, _ = await _drain(monkeypatch, providers, TOOL_HISTORY, model_id="picky-model")

    assert used == "picky"
    assert text == "from-picky"


@pytest.mark.asyncio
async def test_picky_provider_is_a_normal_fallback_when_no_tools_are_in_play(monkeypatch):
    providers = {"primary": _make("primary", fail=True), "picky": _make("picky", accepts_foreign=False)}
    text, used, _ = await _drain(
        monkeypatch, providers, [{"role": "user", "content": "hi"}], model_id="primary-model"
    )

    assert used == "picky", "with no tool history there is nothing for it to choke on"


@pytest.mark.asyncio
async def test_fallback_is_recorded_even_when_the_whole_chain_fails(monkeypatch):
    """The user must be able to see that three providers were tried, rather
    than getting a bare 'the agent run failed'."""
    providers = {"a": _make("a", fail=True), "b": _make("b", fail=True)}
    with pytest.raises(ProviderError):
        await _drain(monkeypatch, providers, [{"role": "user", "content": "hi"}], model_id="a-model")


# --- the real provider classes carry the right flags ------------------------


def test_only_gemini_declares_it_cannot_take_foreign_tool_calls():
    assert GeminiProvider.accepts_foreign_tool_calls is False
    assert OpenAIProvider.accepts_foreign_tool_calls is True
    assert GroqProvider.accepts_foreign_tool_calls is True


def test_gemini_replays_the_thought_signature_it_was_given():
    """Gemini 400s on a replayed functionCall with no signature, so its own
    signature has to survive a round-trip through our normalized format --
    otherwise Gemini cannot sustain a multi-step ReAct loop at all."""
    from app.agents.providers.gemini_provider import _to_contents

    call = ToolCall(id="g1", name="list_files", arguments={},
                    provider_meta={"thought_signature": b"sig-123"})
    contents = _to_contents([
        {"role": "user", "content": "go"},
        {"role": "assistant", "content": "", "tool_calls": [call]},
    ])

    model_turn = next(c for c in contents if c.role == "model")
    fc_part = next(p for p in model_turn.parts if p.function_call is not None)
    assert fc_part.thought_signature == b"sig-123"


def test_gemini_omits_the_signature_when_there_is_none():
    """A call from another provider has no signature and never can; sending a
    fabricated one would be worse than omitting it."""
    from app.agents.providers.gemini_provider import _to_contents

    contents = _to_contents([
        {"role": "user", "content": "go"},
        {"role": "assistant", "content": "",
         "tool_calls": [ToolCall(id="c1", name="list_files", arguments={})]},
    ])

    model_turn = next(c for c in contents if c.role == "model")
    fc_part = next(p for p in model_turn.parts if p.function_call is not None)
    assert fc_part.thought_signature is None
