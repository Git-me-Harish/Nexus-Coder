// Nexus — domain constants
// Phase enums, mode definitions, model registry, spec dimensions.
// Source of truth for UI + agent routing.

export type Mode = "development" | "problem_solving" | "learning";

export type DevPhase =
  | "ideation"
  | "planning"
  | "specification"
  | "implementation"
  | "debug"
  | "review"
  | "completed";

export type ProblemPhase = "discussion";
export type LearningPhase = "explain" | "practice" | "quiz";

export type Phase = DevPhase | ProblemPhase | LearningPhase;

export const DEV_PHASES: DevPhase[] = [
  "ideation",
  "planning",
  "specification",
  "implementation",
  "debug",
  "review",
];

export const PHASE_META: Record<Phase, { label: string; tagline: string; icon: string }> = {
  ideation:       { label: "Ideation",        tagline: "Brainstorm approaches", icon: "Lightbulb" },
  planning:       { label: "Planning",        tagline: "Architect the build",   icon: "Map" },
  specification:  { label: "Specification",   tagline: "Lock the spec",         icon: "FileCheck2" },
  implementation: { label: "Implementation",  tagline: "Write the code",        icon: "Code2" },
  debug:          { label: "Debug",           tagline: "Diagnose & fix",        icon: "Bug" },
  review:         { label: "Review",          tagline: "Audit & ship",          icon: "ShieldCheck" },
  completed:      { label: "Completed",       tagline: "Shipped",               icon: "CheckCircle2" },
  discussion:     { label: "Discussion",      tagline: "Open debate",           icon: "MessagesSquare" },
  explain:        { label: "Explain",         tagline: "Concept walkthrough",   icon: "BookOpen" },
  practice:       { label: "Practice",        tagline: "Hands-on exercise",     icon: "Pencil" },
  quiz:           { label: "Quiz",            tagline: "Test mastery",          icon: "GraduationCap" },
};

// Model Registry

export interface ModelDef {
  id: string;
  provider: "anthropic" | "openai" | "groq" | "gemini" | "nexus";
  displayName: string;
  contextWindow: number;
  inputCostPer1k: number;
  outputCostPer1k: number;
  capabilityTier: "fast" | "balanced" | "powerful";
  phaseSuitability: Phase[];
  description: string;
  available: boolean;
}

/**
 * Static fallback catalog, rendered only until `GET /api/models` responds.
 *
 * THE BACKEND IS THE SOURCE OF TRUTH (backend/app/agents/constants.py MODELS).
 * That endpoint returns these same fields plus a real per-tenant `available`
 * flag, and the model switcher renders from it -- see TopBar.tsx.
 *
 * This list existed as a full second copy of the catalog and had already
 * drifted badly: it offered `groq-llama-3-70b` and `gemini-1-5-pro`, ids the
 * backend has never heard of. Picking one sent an unresolvable slug to the
 * router, which fell through to its "assume anthropic" default and 404'd at
 * the provider. Keep this in sync when the backend catalog changes, or better,
 * don't add entries here at all -- add them to the backend and let them arrive
 * over the wire.
 */
export const MODELS: ModelDef[] = [
  {
    id: "claude-sonnet-5",
    provider: "anthropic",
    displayName: "Claude Sonnet 5",
    contextWindow: 1000000,
    inputCostPer1k: 0.002,
    outputCostPer1k: 0.01,
    capabilityTier: "balanced",
    phaseSuitability: ["planning", "specification", "implementation", "debug"],
    description: "Reasoning + code — default workhorse for specs and implementation.",
    available: true,
  },
  {
    id: "claude-opus-5",
    provider: "anthropic",
    displayName: "Claude Opus 5",
    contextWindow: 1000000,
    inputCostPer1k: 0.005,
    outputCostPer1k: 0.025,
    capabilityTier: "powerful",
    phaseSuitability: ["implementation"],
    description: "Highest-quality code generation for complex builds. Pro tier only.",
    available: true,
  },
  {
    id: "claude-haiku-4-5",
    provider: "anthropic",
    displayName: "Claude Haiku 4.5",
    contextWindow: 200000,
    inputCostPer1k: 0.001,
    outputCostPer1k: 0.005,
    capabilityTier: "fast",
    phaseSuitability: ["ideation", "review"],
    description: "Fast iteration for ideation and checklist-driven review.",
    available: true,
  },
  {
    id: "gpt-5.6-sol",
    provider: "openai",
    displayName: "GPT-5.6 Sol",
    contextWindow: 1050000,
    inputCostPer1k: 0.005,
    outputCostPer1k: 0.03,
    capabilityTier: "powerful",
    phaseSuitability: ["planning", "specification", "debug"],
    description: "OpenAI flagship — strong structured output and agentic tool use.",
    available: true,
  },
  {
    id: "openai/gpt-oss-120b",
    provider: "groq",
    displayName: "GPT-OSS 120B (Groq)",
    contextWindow: 131072,
    inputCostPer1k: 0.00015,
    outputCostPer1k: 0.0006,
    capabilityTier: "fast",
    phaseSuitability: ["ideation", "review"],
    description: "Ultra-fast inference — best for high-volume ideation loops.",
    available: true,
  },
  {
    id: "gemini-3.6-flash",
    provider: "gemini",
    displayName: "Gemini 3.6 Flash",
    contextWindow: 1048576,
    inputCostPer1k: 0.0015,
    outputCostPer1k: 0.0075,
    capabilityTier: "fast",
    phaseSuitability: ["implementation", "debug"],
    description: "Google's fast model — million-token context window.",
    available: true,
  },
  {
    id: "nexus-prime",
    provider: "nexus",
    displayName: "Nexus Prime",
    contextWindow: 256000,
    inputCostPer1k: 0.002,
    outputCostPer1k: 0.01,
    capabilityTier: "powerful",
    phaseSuitability: ["ideation", "planning", "specification", "implementation", "debug", "review"],
    description: "Nexus internal routing layer — auto-picks best model per phase with fallback.",
    available: true,
  },
];

export function getModel(id: string): ModelDef | undefined {
  return MODELS.find((m) => m.id === id);
}

// Default phase→model routing policy

/** Mirrors backend/app/agents/constants.py DEFAULT_MODEL_ID. */
export const DEFAULT_MODEL_ID = "claude-sonnet-5";

export const PHASE_ROUTING: Record<string, string> = {
  ideation: "claude-haiku-4-5",
  planning: DEFAULT_MODEL_ID,
  specification: DEFAULT_MODEL_ID,
  implementation: DEFAULT_MODEL_ID,
  debug: DEFAULT_MODEL_ID,
  review: "claude-haiku-4-5",
  discussion: DEFAULT_MODEL_ID,
  explain: DEFAULT_MODEL_ID,
  practice: DEFAULT_MODEL_ID,
  quiz: "claude-haiku-4-5",
};

// Spec Builder — 12 Architectural Dimensions

export interface SpecOption {
  id: string;
  label: string;
  rationale: string;
  configPayload: Record<string, unknown>;
}

export interface SpecDimension {
  slug: string;
  label: string;
  description: string;
  icon: string;
  options: SpecOption[]; // exactly 3 curated + the "custom" implicit option 4
}

export const SPEC_DIMENSIONS: SpecDimension[] = [
  {
    slug: "ui",
    label: "UI",
    description: "Visual style and interaction density of the frontend.",
    icon: "Palette",
    options: [
      { id: "ui-minimal",     label: "Minimal / utility",     rationale: "Fast, data-dense, few animations — think Linear or Vercel dashboards.", configPayload: { style: "minimal", motion: "sparse", density: "compact" } },
      { id: "ui-modern-saas", label: "Modern SaaS",           rationale: "Cards, soft motion, balanced whitespace — Stripe / Notion vibe.",        configPayload: { style: "modern-saas", motion: "subtle", density: "comfortable" } },
      { id: "ui-bold",        label: "Bold / expressive",     rationale: "Strong typography, custom illustration, heavy motion.",                  configPayload: { style: "bold", motion: "rich", density: "spacious" } },
    ],
  },
  {
    slug: "backend",
    label: "Backend",
    description: "Service architecture and runtime shape.",
    icon: "Server",
    options: [
      { id: "be-fastapi-monolith", label: "FastAPI monolith",          rationale: "Fast to ship, single deploy — async-first, Pydantic native.", configPayload: { framework: "fastapi", topology: "monolith", runtime: "python-3.12" } },
      { id: "be-fastapi-worker",   label: "FastAPI + worker service",  rationale: "Heavier async workloads — Celery/RQ for background jobs.",     configPayload: { framework: "fastapi", topology: "service+worker", runtime: "python-3.12" } },
      { id: "be-nextjs-fullstack", label: "Next.js full-stack",        rationale: "Single repo, frontend-backend co-located — App Router.",       configPayload: { framework: "nextjs", topology: "fullstack", runtime: "node-20" } },
    ],
  },
  {
    slug: "database",
    label: "Database",
    description: "Primary data store and tenancy model.",
    icon: "Database",
    options: [
      { id: "db-pg-rls",    label: "PostgreSQL + RLS",                 rationale: "Strong consistency, mature tooling, RLS for multi-tenancy.",   configPayload: { engine: "postgres-16", tenancy: "shared-schema-rls", extensions: ["pgvector", "pg_partman"] } },
      { id: "db-pg-schema", label: "PostgreSQL per-tenant schema",     rationale: "Stronger isolation, more ops overhead — enterprise tier.",     configPayload: { engine: "postgres-16", tenancy: "schema-per-tenant", extensions: ["pgvector"] } },
      { id: "db-mongo",     label: "MongoDB",                          rationale: "Flexible schema, document-shaped data — rapid prototyping.",   configPayload: { engine: "mongodb-7", tenancy: "shared-db" } },
    ],
  },
  {
    slug: "api_routes",
    label: "API & Routes",
    description: "API style and versioning strategy.",
    icon: "Route",
    options: [
      { id: "api-rest-versioned", label: "REST, URL-versioned",  rationale: "Industry default — /api/v1/, six-month deprecation window.", configPayload: { style: "rest", versioning: "url", schema: "openapi-3.1" } },
      { id: "api-graphql",        label: "GraphQL (Apollo)",     rationale: "Client-driven queries, single endpoint — great for varied UIs.", configPayload: { style: "graphql", server: "apollo-server", schema: "schema-first" } },
      { id: "api-rpc",            label: "tRPC (type-safe RPC)", rationale: "End-to-end types — Next.js fullstack sweet spot.",          configPayload: { style: "trpc", batching: true, subscriptions: true } },
    ],
  },
  {
    slug: "auth_security",
    label: "Auth & Security",
    description: "Authentication mechanism and session model.",
    icon: "ShieldCheck",
    options: [
      { id: "auth-jwt-oauth",      label: "JWT + OAuth",                    rationale: "Stateless, scalable — what Nexus itself uses. Refresh rotation with family detection.", configPayload: { scheme: "jwt", accessTtl: 900, refreshTtl: 2592000, oauth: ["github", "google"] } },
      { id: "auth-session-redis",  label: "Session-based + Redis",          rationale: "Simpler revocation, server-side state — good for shorter-ttl apps.",                     configPayload: { scheme: "session", store: "redis", ttl: 86400 } },
      { id: "auth-magic-link",     label: "Magic link / passwordless",     rationale: "Lowest friction, email-dependent — best for B2C onboarding.",                            configPayload: { scheme: "magic-link", transport: "email", ttl: 600 } },
    ],
  },
  {
    slug: "ai_integrations",
    label: "AI Integrations",
    description: "LLM provider strategy and fallback behavior.",
    icon: "Sparkles",
    options: [
      { id: "ai-single-provider", label: "Single provider, direct SDK",  rationale: "Simplest, fastest to ship — one provider, one model family.", configPayload: { providers: ["anthropic"], fallback: false, routing: "direct" } },
      { id: "ai-multi-provider",  label: "Multi-provider with fallback", rationale: "Resilient — primary → secondary → tertiary chain per call.", configPayload: { providers: ["anthropic", "openai", "groq"], fallback: true, routing: "phase-aware" } },
      { id: "ai-none",            label: "No AI integration",            rationale: "Plain CRUD app — no model calls required.",                  configPayload: { providers: [], fallback: false, routing: "none" } },
    ],
  },
  {
    slug: "caching",
    label: "Caching",
    description: "Cache tiers and invalidation strategy.",
    icon: "Zap",
    options: [
      { id: "cache-redis",     label: "Redis cache-aside",      rationale: "Standard pattern — read-through with explicit invalidation.", configPayload: { engine: "redis-7", pattern: "cache-aside", ttl: 3600 } },
      { id: "cache-cdn-edge",  label: "CDN edge + Redis",       rationale: "Two-tier — static at edge, dynamic in Redis.",                configPayload: { engine: "redis+cloudfront", pattern: "two-tier", ttl: 86400 } },
      { id: "cache-none",      label: "No caching",             rationale: "Read-heavy not a concern — simplicity wins.",                 configPayload: { engine: "none", pattern: "none", ttl: 0 } },
    ],
  },
  {
    slug: "rate_limiting",
    label: "Rate Limiting & Token Limits",
    description: "Request throttling and per-tenant quotas.",
    icon: "Gauge",
    options: [
      { id: "rl-redis-sliding", label: "Redis sliding window",  rationale: "Standard, accurate — per-tenant, per-endpoint windows.", configPayload: { engine: "redis", algorithm: "sliding-window", defaults: { perMin: 60, perDay: 1000 } } },
      { id: "rl-token-bucket",  label: "Token bucket + burst",  rationale: "Allows short bursts — good for interactive UIs.",       configPayload: { engine: "redis", algorithm: "token-bucket", burst: 100, sustained: 60 } },
      { id: "rl-fixed",         label: "Fixed window (simple)", rationale: "Easiest to reason about — acceptable for low-traffic MVPs.", configPayload: { engine: "memory", algorithm: "fixed-window", windowSec: 60, max: 60 } },
    ],
  },
  {
    slug: "session_management",
    label: "Session Management",
    description: "How user and agent sessions are tracked.",
    icon: "Users",
    options: [
      { id: "sm-jwt-rotation",   label: "JWT + refresh rotation",     rationale: "Short-lived access + 30-day rotating refresh. Family detection on reuse.", configPayload: { accessTtl: 900, refreshTtl: 2592000, rotation: "family" } },
      { id: "sm-server-session", label: "Server-side sessions (Redis)", rationale: "Instant revocation, server is source of truth.",                            configPayload: { store: "redis", ttl: 86400, sliding: true } },
      { id: "sm-stateless-jwt",  label: "Stateless JWT only",         rationale: "No server state — simplest, revocation is hard.",                          configPayload: { accessTtl: 3600, refresh: false, rotation: "none" } },
    ],
  },
  {
    slug: "error_logging",
    label: "Error Logging",
    description: "Structured logs, traces, and error tracking.",
    icon: "FileWarning",
    options: [
      { id: "log-otel-sentry",  label: "OpenTelemetry + Sentry",        rationale: "Industry standard — traces via OTel, exceptions via Sentry.",        configPayload: { traces: "otel", errors: "sentry", logs: "json-stdout" } },
      { id: "log-langfuse",     label: "OTel + Langfuse (agent-heavy)", rationale: "Adds agent-specific traces — tokens, cost, fallback events.",        configPayload: { traces: "otel", agentTraces: "langfuse", errors: "sentry" } },
      { id: "log-plain-json",   label: "Plain JSON stdout",             rationale: "Zero dependencies — ship logs to stdout, let infra handle the rest.", configPayload: { traces: "none", errors: "json-stdout", logs: "json-stdout" } },
    ],
  },
  {
    slug: "async_messaging",
    label: "Async & Messaging",
    description: "Background jobs and event bus.",
    icon: "Workflow",
    options: [
      { id: "async-celery-redis", label: "Celery + Redis broker",  rationale: "Python default — mature, scheduled jobs via Beat.",      configPayload: { broker: "redis", backend: "redis", framework: "celery", scheduler: "beat" } },
      { id: "async-bullmq",       label: "BullMQ (Node)",          rationale: "Next.js fullstack — Redis-backed queue, native TS.",     configPayload: { broker: "redis", framework: "bullmq", runtime: "node-20" } },
      { id: "async-none",         label: "No async jobs",          rationale: "Synchronous only — MVP doesn't need background processing.", configPayload: { broker: "none", framework: "none" } },
    ],
  },
  {
    slug: "query_optimization",
    label: "Query Optimization",
    description: "Index strategy and N+1 prevention.",
    icon: "GaugeCircle",
    options: [
      { id: "qo-eager-indices",       label: "Eager indices + DataLoader", rationale: "Pre-build indices on hot paths, batch DB calls in resolvers.", configPayload: { strategy: "eager-indices", batching: "dataloader", nPlus1: "prevented" } },
      { id: "qo-cursor-pagination",   label: "Cursor pagination everywhere", rationale: "Stable performance at scale — no OFFSET degradation.",        configPayload: { strategy: "cursor-pagination", defaultSize: 50, max: 200 } },
      { id: "qo-read-replicas",       label: "Read replicas + PgBouncer",   rationale: "For high read load — primary for writes, replicas for reads.", configPayload: { strategy: "read-replicas", pooler: "pgbouncer", replicaLag: "100ms" } },
    ],
  },
];

// ─── Agent worker types ──────────────────────────────────────────────────────

export type WorkerType = "brainstormer" | "planner" | "spec" | "coder" | "debugger" | "reviewer" | "tutor" | "quiz";

export const PHASE_TO_WORKER: Record<string, WorkerType> = {
  ideation: "brainstormer",
  planning: "planner",
  specification: "spec",
  implementation: "coder",
  debug: "debugger",
  review: "reviewer",
  discussion: "brainstormer",
  explain: "tutor",
  practice: "tutor",
  quiz: "quiz",
};

// ─── Plan limits ─────────────────────────────────────────────────────────────

export const PLAN_LIMITS = {
  free:       { monthlyTokenQuota: 500_000,    maxConcurrentSessions: 2,   sandboxMinutes: 0,   seats: 1 },
  starter:    { monthlyTokenQuota: 5_000_000,  maxConcurrentSessions: 10,  sandboxMinutes: 60,  seats: 5 },
  pro:        { monthlyTokenQuota: 50_000_000, maxConcurrentSessions: 50,  sandboxMinutes: 600, seats: 25 },
  enterprise: { monthlyTokenQuota: -1,         maxConcurrentSessions: 200, sandboxMinutes: -1,  seats: -1 },
};

// ─── Approval gates ──────────────────────────────────────────────────────────

export const APPROVAL_REQUIRED_TRANSITIONS: Array<[string, string]> = [
  ["specification", "implementation"],
];

export function requiresApproval(from: string, to: string): boolean {
  return APPROVAL_REQUIRED_TRANSITIONS.some(([f, t]) => f === from && t === to);
}

export function nextPhase(current: Phase): Phase | null {
  if (current === "ideation") return "planning";
  if (current === "planning") return "specification";
  if (current === "specification") return "implementation";
  if (current === "implementation") return "debug";
  if (current === "debug") return "review";
  if (current === "review") return "completed";
  if (current === "explain") return "practice";
  if (current === "practice") return "quiz";
  if (current === "quiz") return "explain";
  return null;
}
