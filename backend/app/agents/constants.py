"""
Full port of the frontend's src/lib/nexus/constants.ts — phase metadata,
model registry, spec dimensions, plan limits, approval gates. Kept as a
faithful 1:1 port (including field names before camelCase serialization)
so the existing frontend components that render this data need zero changes.

KNOWN LIMITATION: the model `id` values below (e.g. "claude-sonnet-4-6",
"gpt-4o", "gemini-1-5-pro") are the app's own display-oriented catalog
IDs, inherited as-is from the original TS constants.ts -- they are NOT
guaranteed to be the exact model slug string each provider's API expects
today (providers frequently require dated slugs, e.g.
"claude-sonnet-4-5-20250929"). This was already true before this pass;
rather than guess at current exact slugs and risk being confidently
wrong, this is flagged here as a real gap: verify/update these against
each provider's current model list before relying on non-Anthropic-default
models in production.
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
    {"id": "claude-sonnet-4-6", "provider": "anthropic", "displayName": "Claude Sonnet 4.6",
     "contextWindow": 200000, "inputCostPer1k": 0.003, "outputCostPer1k": 0.015,
     "capabilityTier": "balanced", "phaseSuitability": ["planning", "specification", "implementation", "debug"],
     "description": "Reasoning + code — default workhorse for specs and implementation.", "available": True},
    {"id": "claude-opus-4-6", "provider": "anthropic", "displayName": "Claude Opus 4.6",
     "contextWindow": 200000, "inputCostPer1k": 0.015, "outputCostPer1k": 0.075,
     "capabilityTier": "powerful", "phaseSuitability": ["implementation"],
     "description": "Highest-quality code generation for complex builds. Pro tier only.", "available": True},
    {"id": "claude-haiku-4-5", "provider": "anthropic", "displayName": "Claude Haiku 4.5",
     "contextWindow": 200000, "inputCostPer1k": 0.001, "outputCostPer1k": 0.005,
     "capabilityTier": "fast", "phaseSuitability": ["ideation", "review"],
     "description": "Fast iteration for ideation and checklist-driven review.", "available": True},
    {"id": "gpt-4o", "provider": "openai", "displayName": "GPT-4o",
     "contextWindow": 128000, "inputCostPer1k": 0.005, "outputCostPer1k": 0.015,
     "capabilityTier": "balanced", "phaseSuitability": ["planning", "specification", "debug"],
     "description": "OpenAI flagship — strong structured output and tool use.", "available": True},
    {"id": "groq-llama-3-70b", "provider": "groq", "displayName": "Llama 3 70B (Groq)",
     "contextWindow": 32000, "inputCostPer1k": 0.00059, "outputCostPer1k": 0.00079,
     "capabilityTier": "fast", "phaseSuitability": ["ideation", "review"],
     "description": "Ultra-fast inference — best for high-volume ideation loops.", "available": True},
    {"id": "gemini-1-5-pro", "provider": "gemini", "displayName": "Gemini 1.5 Pro",
     "contextWindow": 2000000, "inputCostPer1k": 0.00125, "outputCostPer1k": 0.005,
     "capabilityTier": "powerful", "phaseSuitability": ["implementation", "debug"],
     "description": "Massive context — full project file trees in a single call.", "available": True},
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


PHASE_ROUTING: dict[str, str] = {
    "ideation": "claude-haiku-4-5", "planning": "claude-sonnet-4-6",
    "specification": "claude-sonnet-4-6", "implementation": "claude-sonnet-4-6",
    "debug": "claude-sonnet-4-6", "review": "claude-haiku-4-5",
    "discussion": "claude-sonnet-4-6", "explain": "claude-sonnet-4-6",
    "practice": "claude-sonnet-4-6", "quiz": "claude-haiku-4-5",
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

APPROVAL_REQUIRED_TRANSITIONS = [("specification", "implementation")]


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


# Legacy alias used by app/agents/graph.py's simplified 4-phase demo flow.
PHASE_TRANSITIONS = {
    "ideation": "specification", "specification": "implementation",
    "implementation": "review", "review": None,
}
MODEL_REGISTRY = {m["id"]: {"provider": m["provider"], "context_window": m["contextWindow"]} for m in MODELS}

# Real providers with an actual backend implementation, in priority order
# for both (a) generic fallback when a provider fails mid-stream and
# (b) the "nexus-prime" virtual model's auto-pick-whatever's-configured
# behavior (see app/agents/providers/router.py). "nexus" itself is not a
# real provider -- nexus-prime resolves to one of these at call time.
DEFAULT_FALLBACK_ORDER = ["anthropic", "openai", "groq", "gemini"]

# When falling back to a different provider, the original model_id (e.g.
# "claude-sonnet-4-6") is meaningless to that provider's API -- this maps
# each fallback provider to a comparable model. Missing from the initial
# migration: the router fell back to a different provider while still
# sending the original provider's model_id, which would fail immediately.
FALLBACK_MODEL_FOR_PROVIDER: dict[str, str] = {
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-4o",
    "groq": "groq-llama-3-70b",
    "gemini": "gemini-1-5-pro",
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