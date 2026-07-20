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