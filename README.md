<div align="center">

<img src="frontend/public/logo.png" alt="Nexus Logo" width="180"/>

# Nexus

### AI-Powered Full-Stack Development Platform

*A modern full-stack application combining a Next.js frontend with a Python FastAPI backend, LangGraph agents, PostgreSQL, and enterprise-grade authentication.*

</div>

---

## Overview

Nexus is a production-oriented AI platform that separates frontend and backend responsibilities while preserving the existing user experience.

The frontend remains a modern **Next.js + TypeScript** application, while the backend has been completely migrated to a dedicated **FastAPI** service powered by **LangGraph**, **PostgreSQL**, and a scalable service-oriented architecture.

---

# Project Structure

```text
nexus-fullstack/
├── backend/
│   ├── FastAPI
│   ├── LangGraph Agents
│   ├── PostgreSQL
│   ├── SQLAlchemy
│   ├── Authentication
│   └── REST APIs
│
├── frontend/
│   ├── Next.js
│   ├── React
│   ├── TypeScript
│   ├── Zustand
│   ├── Tailwind CSS
│   └── shadcn/ui
│
└── docker-compose.yml
```

---

# Architecture

```text
                +----------------------+
                |      Frontend        |
                |  Next.js + React UI  |
                +----------+-----------+
                           |
                           |
                    REST + SSE
                           |
                           ▼
                +----------------------+
                |   FastAPI Backend    |
                |  LangGraph Agents    |
                +----------+-----------+
                           |
          +----------------+----------------+
          |                |                |
          ▼                ▼                ▼
 Authentication      AI Services      Learning Engine
          |                |                |
          +----------------+----------------+
                           |
                           ▼
                     PostgreSQL
```

## The agent loop

A turn is not a single model call. On the phases that produce artifacts
(implementation, debug, review) the agent plans, then acts with real tools,
then reviews its own work against what actually happened:

```text
  START ─(plan-worthy phase?)─┬─> planner ──┐
                              └─────────────┴─> executor ──> critic ─┬─> executor (revise)
                                                  │   ▲              └─> END
                                       tool calls │   │ real results
                                                  ▼   │
                                        ┌──────────────────────┐
                                        │  write_file  read_file│
                                        │  list_files  run_command
                                        └──────────┬───────────┘
                                                   ▼
                                     workspace on disk + Docker sandbox
                                     (offline, non-root, read-only rootfs)
```

- **planner** — emits a structured plan (goal / steps / risks / success
  criteria) that the executor follows and the critic scores against.
- **executor** — a ReAct loop. Its tool calls really execute: files land on
  disk and in Postgres, commands run in a container and return real exit
  codes and stderr, which the model must react to. Bounded by
  `MAX_TOOL_STEPS`.
- **critic** — judges the result against the plan, the phase's exit
  criteria, and the **tool trace**, so "the tests pass" is checked against
  whether a command actually ran rather than taken on faith. It also decides
  whether the phase is finished, which is what advances the session.

Conversational phases (ideation, discussion, explain…) are deliberately a
single call with no tools — a model handed tools answers differently even
when it uses none.

## Enabling code execution

Off by default. With it on, the agent can run the code it writes, which is
what lets it prove the tests pass instead of asserting they would.

```bash
docker build -t nexus-sandbox:latest backend/sandbox/
# then in backend/.env
SANDBOX_ENABLED=true
```

Execution **only ever happens inside Docker** — network disabled, non-root,
read-only root filesystem, CPU/memory/PID/output/time limits, and the
session's workspace as the sole writable mount. If Docker is unavailable the
tool returns an error; there is deliberately no fallback that runs
model-written code on the host. `GET /health` reports whether the sandbox is
actually usable.

---

# Frontend Migration

The frontend user interface has intentionally remained almost entirely unchanged.

### Removed

- Prisma
- Next.js Route Handlers
- Server-side authentication
- Internal LLM provider implementations

The following directories were removed:

```text
prisma/
src/app/api/
src/lib/db.ts
src/lib/nexus/auth.ts
src/lib/nexus/providers/
```

---

### Updated

The following files were updated to communicate directly with the FastAPI backend:

- `src/lib/nexus/client.ts`
- `src/stores/authStore.ts`
- `src/lib/nexus/learning/engine.ts`

---

### Preserved

Everything else remains unchanged, including:

- UI Components
- Pages
- Zustand Stores
- Tailwind Styling
- shadcn/ui Components
- Streaming Chat Interface
- Application State Management

The frontend behavior and user experience remain identical to the original implementation.

---

# Authentication Improvements

The migration introduces a production-ready authentication flow.

### Previous Implementation

- 15-minute access tokens
- No refresh token support
- Users were forced to log in again after expiration

### Current Implementation

- Rotating refresh tokens
- Automatic token renewal
- Transparent retry on `401 Unauthorized`
- No interruption to the user experience

---

# Technology Stack

## Frontend

- Next.js
- React
- TypeScript
- Zustand
- Tailwind CSS
- shadcn/ui

## Backend

- Python
- FastAPI
- LangGraph
- SQLAlchemy
- Alembic
- PostgreSQL
- Redis

## AI

- Anthropic
- OpenAI

## Infrastructure

- Docker
- Docker Compose

---

# Running the Project

## Docker

```bash
cd nexus-fullstack

cp backend/.env.example backend/.env
```

Configure:

- JWT_SECRET
- ANTHROPIC_API_KEY
- OPENAI_API_KEY

Start everything:

```bash
docker compose up --build
```

---

### Services

| Service | URL |
|----------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |

---

## Apply Database Migrations

```bash
docker compose exec backend alembic revision --autogenerate -m "initial schema"

docker compose exec backend alembic upgrade head
```

---

# Local Development

## Backend

```bash
cd backend

docker compose -f ../docker-compose.yml up -d postgres redis

pip install -r requirements-dev.txt

uvicorn app.main:app --reload
```

---

## Frontend

```bash
cd frontend

cp .env.local.example .env.local

npm install

npm run dev
```

---

# Verification

The project has been validated through multiple checks before delivery.

✅ Python syntax validation

✅ FastAPI import verification

✅ OpenAPI schema generation

✅ SQLAlchemy model validation

✅ Database relationship verification

✅ End-to-end authentication flow

✅ Project & session workflow testing

✅ API response contract validation

✅ TypeScript compilation (`tsc --noEmit`)

The three existing frontend type warnings (`ChatPanel.tsx`, `QuizInterface.tsx`, and `TopBar.tsx`) were already present before migration and are unrelated to the backend changes.

---

# Current Limitations

The only major planned enhancement is **sandboxed code execution**.

Although the API already exposes `sandboxStatus` fields throughout the application, an isolated execution environment has intentionally **not** been implemented yet. Running LLM-generated code securely requires dedicated infrastructure and is planned as a future enhancement rather than being rushed into this migration.

---

# Highlights

- Full Backend Migration to Python
- LangGraph Agent Architecture
- Enterprise Authentication
- Automatic Token Refresh
- PostgreSQL Persistence
- Redis Integration
- Streaming AI Responses (SSE)
- Docker Ready
- Production-Oriented Architecture
- Clean Separation Between Frontend & Backend

---

<div align="center">

**Built with ❤️ using Next.js, FastAPI, LangGraph, PostgreSQL, and modern AI technologies.**

</div>