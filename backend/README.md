# Nexus Backend — Python/FastAPI migration

Replaces the Next.js/Prisma/SQLite backend entirely. The Next.js app becomes
a pure frontend that talks to this service over REST + SSE. Nothing in
`src/app/(pages)` or `src/components` needs to change — only `src/lib/nexus/client.ts`,
which should point at `NEXT_PUBLIC_API_URL` instead of local route handlers.

## What changed vs. the TS version, and why

| Concern | Before | Now | Why |
|---|---|---|---|
| Database | SQLite (file, single-writer) | Postgres + asyncpg | Concurrent multi-tenant writes; SQLite serializes all writers process-wide |
| Tenant isolation | App-layer `where: tenantId` only | App-layer filter **+** Postgres RLS (`0002_enable_row_level_security.py`) | A missed `WHERE` in a future route no longer leaks cross-tenant data |
| Password hashing | Salted HMAC-SHA256 (fast hash) | Argon2id (`argon2-cffi`) | HMAC is brute-forceable at scale; Argon2id is deliberately slow/memory-hard |
| JWT | Homegrown HMAC scheme | PyJWT with `iss`, `exp`, `iat` validation | Standard library validation instead of hand-rolled claim checks |
| Refresh tokens | `RefreshToken` model existed, unused | Rotated on every refresh, reuse triggers family-wide revocation | Detects stolen-token replay |
| Agent orchestration | Static `workerForPhase()` lookup | Real LangGraph `StateGraph` (`app/agents/graph.py`) | The schema already modeled `langgraphThreadId` — this makes it real, and gives you a place to add cycles (self-critique, retries) later without restructuring |
| Provider fallback | ZAI-specific fallback | Generic `route_and_stream()` fallback chain, provider-agnostic | Easier to add/remove providers |
| Rate limiting | None | Redis fixed-window middleware | Basic abuse protection |
| Code execution sandbox | Fields existed (`sandboxStatus`), no implementation | Still not implemented — see **Sandbox** section below | This is a security-critical piece that needs its own focused build, not a rushed bolt-on |

## Setup

```bash
cp .env.example .env
# fill in JWT_SECRET (python -c "import secrets; print(secrets.token_urlsafe(48))"),
# ANTHROPIC_API_KEY, OPENAI_API_KEY

docker compose up -d postgres redis
pip install -r requirements-dev.txt

# Generate the initial schema migration from the models (there is no
# hand-written 0001 — let alembic autogenerate it against your live models):
alembic revision --autogenerate -m "initial schema"
alembic upgrade head

# Wire up the RLS migration:
# open alembic/versions/0002_enable_row_level_security.py and replace
# down_revision with the revision id alembic just generated for 0001, then:
alembic upgrade head

uvicorn app.main:app --reload
```

Docs at `http://localhost:8000/docs` (disabled automatically when `ENV=production`).

### RLS: one more wiring step

`0002_enable_row_level_security.py` enables RLS but the app doesn't yet set
`app.current_tenant_id` per-connection. Add this to `get_db()` in
`app/db/session.py` once you're ready to turn RLS from "installed" to "active":

```python
async def get_db():
    async with AsyncSessionLocal() as session:
        # tenant_id would come from a contextvar set in verify_tenant_membership
        await session.execute(text("SET LOCAL app.current_tenant_id = :tid"), {"tid": tenant_id})
        yield session
```

This is deliberately left as a follow-up rather than done here because it
requires deciding how tenant_id flows from the auth dependency into the DB
session dependency (contextvar vs. explicit parameter) — worth a five-minute
conversation rather than a silent architectural decision.

## Sandbox execution — not implemented, and here's what it needs

The old schema had `sandboxStatus`/`sandboxPreviewUrl` fields with no backing
code. This migration doesn't implement it either, on purpose: it's the
highest-risk component in the whole system (executing LLM-generated code)
and deserves a dedicated pass rather than being rushed in alongside auth/DB
work. When you build it:

- Run generated code in an ephemeral container per execution, never a
  shared/reused one.
- No network access from inside the sandbox unless the task explicitly
  needs it (and then, egress-allowlisted, not open).
- Hard CPU/memory/pids limits and a wall-clock timeout (`SANDBOX_*` env
  vars are already scaffolded in `config.py` for this).
- Non-root user inside the container image, read-only root filesystem,
  writable only under `/workspace`.
- Firecracker microVMs (via `firecracker-containerd`) or gVisor (`runsc`)
  as the container runtime if you want kernel-level isolation beyond
  standard Docker namespaces — worth it given you're running untrusted,
  model-generated code, not your own.
- Resource quotas enforced by the orchestrator (Docker `--cpus`/`--memory`
  or a Kubernetes `ResourceQuota`), not just requested — a compromised or
  buggy sandbox shouldn't be able to starve the host.

## What's intentionally lighter than the rest

- `route_next()` in `app/agents/graph.py` always returns `END` — each API
  turn is one graph pass, with `advance-phase` as an explicit, separate
  endpoint rather than an autonomous phase transition. If you want the
  agent to decide on its own when a phase is complete, that's a real
  design decision (autonomy vs. predictability) worth making deliberately,
  not defaulting into.
- `MemorySaver` is the LangGraph checkpointer — fine for dev, but thread
  state won't survive a process restart. Swap for
  `langgraph.checkpoint.postgres.AsyncPostgresSaver` before this goes to
  staging; the interface is a drop-in swap in `build_graph()`.
- Cost table in `usage_service.py` is placeholder pricing — replace with
  actual per-model rates before this feeds anything billing-facing.
- No test suite yet. `requirements-dev.txt` has pytest/pytest-asyncio
  ready; the service-layer functions are written to be testable in
  isolation (no framework coupling) specifically so tests can be added
  without refactoring.

## Frontend wiring

In `src/lib/nexus/client.ts`, point every fetch at
`process.env.NEXT_PUBLIC_API_URL` instead of relative `/api/...` paths, and
switch the SSE consumption in the chat UI from same-origin `fetch` +
`ReadableStream` to an `EventSource`/`fetch`-based SSE client pointed at
`POST /api/v1/sessions/{id}/messages` (still POST-initiated SSE via
`sse-starlette`, so your existing streaming UI logic — which already
handles token-by-token deltas — needs minimal changes, mainly the base URL
and CORS credentials mode).
