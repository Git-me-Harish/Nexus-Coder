"""
Full port of the frontend's src/lib/nexus/constants.ts — phase metadata,
model registry, spec dimensions, plan limits, approval gates. Kept as a
faithful 1:1 port (including field names before camelCase serialization)
so the existing frontend components that render this data need zero changes.

MODEL CATALOG ROT -- READ BEFORE EDITING MODELS BELOW.

The `id` values are sent verbatim to each provider's API, so a stale one
is not a cosmetic problem: it is a hard 404 at request time. The previous
catalog had exactly that failure -- `gemini-2.0-flash` returned "This model
is no longer available", and `llama-3.3-70b-versatile` was deprecated by
Groq in June 2026. Both were flagged here only as a "verify these someday"
note, which is not a mechanism.

Catalog last verified against each provider's published model list on
2026-09-04 (sources in each entry's comment). Providers retire models on
their own schedule, so treat every entry as perishable:

  - Anthropic: https://docs.claude.com/en/docs/about-claude/models
  - OpenAI:    https://developers.openai.com/api/docs/models
  - Groq:      GET https://api.groq.com/openai/v1/models (and /docs/deprecations)
  - Gemini:    https://ai.google.dev/gemini-api/docs/models

Each of those providers exposes a live model-list endpoint. Hardcoding a
catalog will keep rotting, so don't rely on remembering to check: run
`python scripts/verify_model_catalog.py` on a schedule. It reconciles every
id below against its provider's live list and exits non-zero on a stale one,
so the decay is found by CI rather than by a user mid-session.

Internal consistency (ids referenced from PHASE_ROUTING and
FALLBACK_MODEL_FOR_PROVIDER actually existing here) is enforced separately by
tests/test_model_catalog.py, which needs no network and no API keys.
"""
from typing import Literal, TypedDict

Mode = Literal["development", "problem_solving", "learning"]

DEV_PHASES = ["ideation", "planning", "specification", "implementation", "debug", "review"]

PHASE_META: dict[str, dict[str, str]] = {
    "ideation":       {"label": "Ideation",       "tagline": "Brainstorm approaches", "icon": "Lightbulb"},
    "planning":       {"label": "Planning",       "tagline": "Architect the build",   "icon": "Map"},
    "specification":  {"label": "Specification",  "tagline": "Lock the spec",         "icon": "FileCheck2"},
    "implementation": {"label": "Implementation", "tagline": "Write the code",        "icon": "Code2"},
    "debug":          {"label": "Debug",          "tagline": "Diagnose & fix",        "icon": "Bug"},
    "review":         {"label": "Review",         "tagline": "Audit & ship",          "icon": "ShieldCheck"},
    "completed":      {"label": "Completed",      "tagline": "Shipped",               "icon": "CheckCircle2"},
    "discussion":     {"label": "Discussion",     "tagline": "Open debate",           "icon": "MessagesSquare"},
    "explain":        {"label": "Explain",        "tagline": "Concept walkthrough",   "icon": "BookOpen"},
    "practice":       {"label": "Practice",       "tagline": "Hands-on exercise",     "icon": "Pencil"},
    "quiz":           {"label": "Quiz",           "tagline": "Test mastery",          "icon": "GraduationCap"},
}

# Exact 1:1 match with frontend src/lib/nexus/constants.ts MODELS -- the
# initial migration only ported 5 of these 7 and silently dropped the
# groq/gemini entries, which left them permanently disabled in the UI with
# no backend behind them at all. `available` here is a static placeholder;
# the real per-tenant value is computed at request time in
# app/api/v1/routes/models.py, not read from this catalog.
MODELS: list[dict] = [
    # Anthropic -- ids and per-MTok prices from the Claude models doc (2026-09-04).
    # The ids are complete as written; never append a date suffix.
    {"id": "claude-sonnet-5", "provider": "anthropic", "displayName": "Claude Sonnet 5",
     "contextWindow": 1000000, "inputCostPer1k": 0.002, "outputCostPer1k": 0.010,
     "capabilityTier": "balanced", "phaseSuitability": ["planning", "specification", "implementation", "debug"],
     "description": "Reasoning + code — default workhorse for specs and implementation.", "available": True},
    {"id": "claude-opus-5", "provider": "anthropic", "displayName": "Claude Opus 5",
     "contextWindow": 1000000, "inputCostPer1k": 0.005, "outputCostPer1k": 0.025,
     "capabilityTier": "powerful", "phaseSuitability": ["implementation"],
     "description": "Highest-quality code generation for complex builds. Pro tier only.", "available": True},
    {"id": "claude-haiku-4-5", "provider": "anthropic", "displayName": "Claude Haiku 4.5",
     "contextWindow": 200000, "inputCostPer1k": 0.001, "outputCostPer1k": 0.005,
     "capabilityTier": "fast", "phaseSuitability": ["ideation", "review"],
     "description": "Fast iteration for ideation and checklist-driven review.", "available": True},
    # OpenAI -- gpt-4o is now legacy; gpt-5.6-sol is the current flagship.
    {"id": "gpt-5.6-sol", "provider": "openai", "displayName": "GPT-5.6 Sol",
     "contextWindow": 1050000, "inputCostPer1k": 0.005, "outputCostPer1k": 0.030,
     "capabilityTier": "powerful", "phaseSuitability": ["planning", "specification", "debug"],
     "description": "OpenAI flagship — strong structured output and agentic tool use.", "available": True},
    # Groq -- llama-3.3-70b-versatile was deprecated 2026-06-17; Groq's own
    # migration note points at gpt-oss-120b as the replacement for that tier.
    {"id": "openai/gpt-oss-120b", "provider": "groq", "displayName": "GPT-OSS 120B (Groq)",
     "contextWindow": 131072, "inputCostPer1k": 0.00015, "outputCostPer1k": 0.00060,
     "capabilityTier": "fast", "phaseSuitability": ["ideation", "review"],
     "description": "Ultra-fast inference — best for high-volume ideation loops.", "available": True},
    # Gemini -- gemini-2.0-flash is retired and 404s; 3.6 Flash is the successor.
    {"id": "gemini-3.6-flash", "provider": "gemini", "displayName": "Gemini 3.6 Flash",
     "contextWindow": 1048576, "inputCostPer1k": 0.0015, "outputCostPer1k": 0.0075,
     "capabilityTier": "fast", "phaseSuitability": ["implementation", "debug"],
     "description": "Google's fast model — million-token context window.", "available": True},
    {"id": "nexus-prime", "provider": "nexus", "displayName": "Nexus Prime",
     "contextWindow": 256000, "inputCostPer1k": 0.002, "outputCostPer1k": 0.01,
     "capabilityTier": "powerful",
     "phaseSuitability": ["ideation", "planning", "specification", "implementation", "debug", "review"],
     "description": "Auto-picks whichever configured provider is available, with fallback.",
     "available": True},
]

_MODEL_INDEX = {m["id"]: m for m in MODELS}


def get_model(model_id: str) -> dict | None:
    return _MODEL_INDEX.get(model_id)


#: Default model per phase. Every value MUST be an id present in MODELS --
#: a dangling id here is silently sent to a provider and 404s at request
#: time. tests/test_model_catalog.py enforces that.
DEFAULT_MODEL_ID = "claude-sonnet-5"

PHASE_ROUTING: dict[str, str] = {
    "ideation": "claude-haiku-4-5", "planning": DEFAULT_MODEL_ID,
    "specification": DEFAULT_MODEL_ID, "implementation": DEFAULT_MODEL_ID,
    "debug": DEFAULT_MODEL_ID, "review": "claude-haiku-4-5",
    "discussion": DEFAULT_MODEL_ID, "explain": DEFAULT_MODEL_ID,
    "practice": DEFAULT_MODEL_ID, "quiz": "claude-haiku-4-5",
}

PHASE_TO_WORKER: dict[str, str] = {
    "ideation": "brainstormer", "planning": "planner", "specification": "spec",
    "implementation": "coder", "debug": "debugger", "review": "reviewer",
    "discussion": "brainstormer", "explain": "tutor", "practice": "tutor", "quiz": "quiz",
}

PLAN_LIMITS = {
    "free":       {"monthlyTokenQuota": 500_000,    "maxConcurrentSessions": 2,   "sandboxMinutes": 0,   "seats": 1},
    "starter":    {"monthlyTokenQuota": 5_000_000,  "maxConcurrentSessions": 10,  "sandboxMinutes": 60,  "seats": 5},
    "pro":        {"monthlyTokenQuota": 50_000_000, "maxConcurrentSessions": 50,  "sandboxMinutes": 600, "seats": 25},
    "enterprise": {"monthlyTokenQuota": -1,         "maxConcurrentSessions": 200, "sandboxMinutes": -1,  "seats": -1},
}

APPROVAL_REQUIRED_TRANSITIONS = [
    ("ideation", "planning"),
    ("planning", "specification"),
    ("specification", "implementation"),
]


def requires_approval(frm: str, to: str) -> bool:
    return (frm, to) in APPROVAL_REQUIRED_TRANSITIONS


_NEXT_PHASE_MAP = {
    "ideation": "planning", "planning": "specification", "specification": "implementation",
    "implementation": "debug", "debug": "review", "review": "completed",
    "explain": "practice", "practice": "quiz", "quiz": "explain",
}


def next_phase(current: str) -> str | None:
    return _NEXT_PHASE_MAP.get(current)


def initial_phase_for_mode(mode: str) -> str:
    return {"development": "ideation", "problem_solving": "discussion", "learning": "explain"}.get(mode, "ideation")


# NOTE: a second, conflicting phase map (`PHASE_TRANSITIONS`) used to live
# here for graph.py's old simplified demo flow. It claimed ideation ->
# specification, silently skipping Planning, and disagreed with
# _NEXT_PHASE_MAP above -- which map you got depended on which module you
# imported from. The graph no longer carries its own notion of phase order:
# `next_phase()` above is the single source of truth, and phase advancement
# goes through session_service.advance_phase so the spec-confirmation
# approval gate is always enforced.
MODEL_REGISTRY = {m["id"]: {"provider": m["provider"], "context_window": m["contextWindow"]} for m in MODELS}

# Real providers with an actual backend implementation, in priority order
# for both (a) generic fallback when a provider fails mid-stream and
# (b) the "nexus-prime" virtual model's auto-pick-whatever's-configured
# behavior (see app/agents/providers/router.py). "nexus" itself is not a
# real provider -- nexus-prime resolves to one of these at call time.
DEFAULT_FALLBACK_ORDER = ["anthropic", "openai", "groq", "gemini"]

# When falling back to a different provider, the original model_id (e.g.
# "claude-sonnet-5") is meaningless to that provider's API -- this maps
# each fallback provider to a comparable model. Missing from the initial
# migration: the router fell back to a different provider while still
# sending the original provider's model_id, which would fail immediately.
# Every value MUST be an id present in MODELS -- enforced by
# tests/test_model_catalog.py, because a stale entry here fails only on the
# fallback path, i.e. exactly when the primary provider is already down.
FALLBACK_MODEL_FOR_PROVIDER: dict[str, str] = {
    "anthropic": DEFAULT_MODEL_ID,
    "openai": "gpt-5.6-sol",
    "groq": "openai/gpt-oss-120b",
    "gemini": "gemini-3.6-flash",
}

# The 12 spec-builder dimension slugs the frontend renders (src/lib/nexus/
# constants.ts SPEC_DIMENSIONS). The frontend owns the full option catalog
# (labels, descriptions, curated choices per dimension) since it's pure
# render data with no server dependency -- this list exists purely so the
# backend can validate that a saved spec's dimension keys are one of the
# real dimensions, matching validation.ts's putSpecSchema (see
# app/schemas/spec.py). Keep in sync if dimensions are added/removed.
SPEC_DIMENSION_SLUGS = [
    "ui", "backend", "database", "api_routes", "auth_security",
    "ai_integrations", "caching", "rate_limiting", "session_management",
    "error_logging", "async_messaging", "query_optimization",
]