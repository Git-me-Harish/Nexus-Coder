"""
Internal consistency of the model catalog.

These do NOT check that a model id is still live at its provider -- only a
network call can do that, and the catalog docstring points at each
provider's model-list endpoint for it. What they do catch is the failure
that actually shipped: a model id referenced from PHASE_ROUTING or
FALLBACK_MODEL_FOR_PROVIDER that no longer exists in MODELS.

That class of bug is invisible until runtime and lands in the worst place:
a dangling FALLBACK_MODEL_FOR_PROVIDER entry fails only on the fallback
path, i.e. precisely when the primary provider is already down.
"""
import pytest

from app.agents.constants import (
    DEFAULT_FALLBACK_ORDER,
    DEFAULT_MODEL_ID,
    FALLBACK_MODEL_FOR_PROVIDER,
    MODELS,
    PHASE_ROUTING,
    PHASE_TO_WORKER,
    DEV_PHASES,
    get_model,
)
from app.agents.providers.router import _PROVIDERS

CATALOG_IDS = {m["id"] for m in MODELS}


def test_model_ids_are_unique():
    ids = [m["id"] for m in MODELS]
    assert len(ids) == len(set(ids)), f"duplicate model ids: {sorted(set(i for i in ids if ids.count(i) > 1))}"


@pytest.mark.parametrize("phase,model_id", sorted(PHASE_ROUTING.items()))
def test_phase_routing_points_at_a_real_model(phase, model_id):
    assert model_id in CATALOG_IDS, f"PHASE_ROUTING[{phase!r}] = {model_id!r} is not in MODELS"


@pytest.mark.parametrize("provider,model_id", sorted(FALLBACK_MODEL_FOR_PROVIDER.items()))
def test_fallback_model_is_a_real_model_from_that_provider(provider, model_id):
    entry = get_model(model_id)
    assert entry is not None, f"FALLBACK_MODEL_FOR_PROVIDER[{provider!r}] = {model_id!r} is not in MODELS"
    # Falling back to provider X while naming a model that belongs to Y sends
    # a slug that provider cannot resolve -- the exact bug the fallback map
    # was added to fix.
    assert entry["provider"] == provider, (
        f"FALLBACK_MODEL_FOR_PROVIDER[{provider!r}] names {model_id!r}, "
        f"which belongs to provider {entry['provider']!r}"
    )


def test_default_model_is_in_the_catalog():
    assert DEFAULT_MODEL_ID in CATALOG_IDS


def test_every_real_provider_has_a_fallback_model():
    """DEFAULT_FALLBACK_ORDER walks these providers on failure; one without a
    fallback model would be skipped or sent a foreign slug."""
    for provider in DEFAULT_FALLBACK_ORDER:
        assert provider in FALLBACK_MODEL_FOR_PROVIDER, f"{provider} has no fallback model"


def test_fallback_order_matches_implemented_providers():
    """A provider in the fallback chain with no implementation is silently
    skipped; an implemented one missing from the chain is never reached."""
    assert set(DEFAULT_FALLBACK_ORDER) == set(_PROVIDERS)


def test_every_catalog_model_has_an_implemented_provider():
    for model in MODELS:
        provider = model["provider"]
        # "nexus" is the virtual auto-pick model, resolved to a real provider
        # by the router at call time -- it has no backend of its own.
        if provider == "nexus":
            continue
        assert provider in _PROVIDERS, f"{model['id']} claims provider {provider!r}, which has no implementation"


def test_every_phase_has_routing_and_a_worker():
    for phase in DEV_PHASES:
        assert phase in PHASE_ROUTING, f"phase {phase!r} has no model routing"
        assert phase in PHASE_TO_WORKER, f"phase {phase!r} has no worker label"


@pytest.mark.parametrize("model", MODELS, ids=[m["id"] for m in MODELS])
def test_catalog_entries_are_well_formed(model):
    for field in ("id", "provider", "displayName", "contextWindow",
                  "inputCostPer1k", "outputCostPer1k", "capabilityTier", "phaseSuitability"):
        assert field in model, f"{model.get('id')} is missing {field}"
    assert model["contextWindow"] > 0
    # Output is priced above input for every provider in this catalog; an
    # inverted pair means the two columns were transposed on entry, which
    # would quietly under-report cost in the usage ledger.
    assert 0 < model["inputCostPer1k"] <= model["outputCostPer1k"]
    assert model["capabilityTier"] in {"fast", "balanced", "powerful"}
    unknown_phases = set(model["phaseSuitability"]) - set(PHASE_TO_WORKER)
    assert not unknown_phases, f"{model['id']} lists unknown phases: {sorted(unknown_phases)}"
