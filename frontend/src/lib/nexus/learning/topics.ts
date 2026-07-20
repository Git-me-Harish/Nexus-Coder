// Nexus — Learning mode topic catalog
//
// Curated topics across languages, frameworks, and concepts. Each topic has a
// slug, label, category, and a one-line "what you'll learn" description.
// The tutor/quiz workers use these to ground their prompts.

export interface LearningTopicDef {
  slug: string;
  label: string;
  category: "Languages" | "Frontend" | "Backend" | "Databases" | "AI/ML" | "DevOps" | "Concepts";
  description: string;
  /** Tags used for "related concepts" similarity (simplified — no embeddings at MVP) */
  tags: string[];
}

export const LEARNING_TOPICS: LearningTopicDef[] = [
  // ─── Languages ──────────────────────────────────────────────────────────
  { slug: "python-decorators", label: "Python Decorators", category: "Languages", description: "How @syntax wraps functions — caching, auth, logging.", tags: ["python", "functions", "metaprogramming"] },
  { slug: "python-async", label: "Python Async/Await", category: "Languages", description: "Coroutines, event loops, and when not to use async.", tags: ["python", "concurrency", "async"] },
  { slug: "typescript-generics", label: "TypeScript Generics", category: "Languages", description: "<T> — type variables, constraints, inference.", tags: ["typescript", "types", "generics"] },
  { slug: "typescript-utility-types", label: "TypeScript Utility Types", category: "Languages", description: "Partial, Pick, Omit, Record — built-in type transformers.", tags: ["typescript", "types"] },
  { slug: "rust-ownership", label: "Rust Ownership", category: "Languages", description: "Borrow checker, lifetimes, and why Rust is memory-safe.", tags: ["rust", "memory", "systems"] },
  { slug: "go-goroutines", label: "Go Goroutines & Channels", category: "Languages", description: "Lightweight threads and CSP-style concurrency.", tags: ["go", "concurrency"] },

  // ─── Frontend ───────────────────────────────────────────────────────────
  { slug: "react-hooks", label: "React Hooks", category: "Frontend", description: "useState, useEffect, useMemo, useCallback, useRef.", tags: ["react", "frontend", "state"] },
  { slug: "react-context", label: "React Context", category: "Frontend", description: "Prop drilling escape hatch — when to use, when to avoid.", tags: ["react", "state", "frontend"] },
  { slug: "nextjs-app-router", label: "Next.js App Router", category: "Frontend", description: "Server Components, layouts, route handlers, streaming.", tags: ["nextjs", "react", "ssr"] },
  { slug: "css-grid-flexbox", label: "CSS Grid & Flexbox", category: "Frontend", description: "Two layout systems, when to use which.", tags: ["css", "layout", "frontend"] },
  { slug: "tailwind-css", label: "Tailwind CSS", category: "Frontend", description: "Utility-first CSS — config, tokens, responsive prefixes.", tags: ["css", "tailwind", "frontend"] },

  // ─── Backend ────────────────────────────────────────────────────────────
  { slug: "fastapi-basics", label: "FastAPI Fundamentals", category: "Backend", description: "Path/query params, Pydantic models, dependency injection.", tags: ["python", "fastapi", "api"] },
  { slug: "rest-api-design", label: "REST API Design", category: "Backend", description: "Resources, status codes, versioning, pagination.", tags: ["api", "rest", "http"] },
  { slug: "graphql-vs-rest", label: "GraphQL vs REST", category: "Backend", description: "Trade-offs, when each shines, schema design.", tags: ["api", "graphql", "rest"] },
  { slug: "jwt-auth", label: "JWT Authentication", category: "Backend", description: "Tokens, refresh rotation, family detection, revocation.", tags: ["auth", "security", "jwt"] },
  { slug: "rate-limiting", label: "Rate Limiting", category: "Backend", description: "Sliding window, token bucket, per-tenant quotas.", tags: ["backend", "scaling", "redis"] },

  // ─── Databases ──────────────────────────────────────────────────────────
  { slug: "sql-indexes", label: "SQL Indexes", category: "Databases", description: "B-tree, GIN, when to index, composite vs single.", tags: ["sql", "postgres", "performance"] },
  { slug: "postgres-rls", label: "PostgreSQL RLS", category: "Databases", description: "Row-Level Security policies for multi-tenant SaaS.", tags: ["postgres", "security", "multi-tenant"] },
  { slug: "database-normalization", label: "Database Normalization", category: "Databases", description: "1NF, 2NF, 3NF — and when to denormalize.", tags: ["sql", "design"] },
  { slug: "redis-caching", label: "Redis Caching", category: "Databases", description: "Cache-aside, write-through, TTL, invalidation.", tags: ["redis", "caching", "performance"] },

  // ─── AI/ML ──────────────────────────────────────────────────────────────
  { slug: "llm-prompting", label: "LLM Prompt Engineering", category: "AI/ML", description: "System prompts, few-shot, chain-of-thought, structured output.", tags: ["ai", "llm", "prompting"] },
  { slug: "rag-basics", label: "RAG (Retrieval-Augmented Generation)", category: "AI/ML", description: "Embeddings, vector search, chunking, reranking.", tags: ["ai", "rag", "embeddings"] },
  { slug: "agent-architectures", label: "Agent Architectures", category: "AI/ML", description: "Orchestrator-worker, plan-and-execute, ReAct, HITL gates.", tags: ["ai", "agents", "langgraph"] },
  { slug: "vector-databases", label: "Vector Databases", category: "AI/ML", description: "pgvector, Pinecone, HNSW vs IVF, similarity metrics.", tags: ["ai", "vectors", "postgres"] },

  // ─── DevOps ─────────────────────────────────────────────────────────────
  { slug: "docker-basics", label: "Docker Fundamentals", category: "DevOps", description: "Images, containers, layers, multi-stage builds.", tags: ["docker", "devops", "containers"] },
  { slug: "k8s-basics", label: "Kubernetes Basics", category: "DevOps", description: "Pods, deployments, services, ingress.", tags: ["kubernetes", "devops"] },
  { slug: "ci-cd", label: "CI/CD Pipelines", category: "DevOps", description: "GitHub Actions, build/test/deploy, env promotion.", tags: ["devops", "ci", "automation"] },

  // ─── Concepts ───────────────────────────────────────────────────────────
  { slug: "system-design", label: "System Design Principles", category: "Concepts", description: "Scaling, sharding, caching, CAP theorem, trade-offs.", tags: ["architecture", "scaling", "design"] },
  { slug: "design-patterns", label: "Design Patterns", category: "Concepts", description: "Singleton, Factory, Observer, Strategy — when to use.", tags: ["architecture", "patterns", "oop"] },
  { slug: "big-o", label: "Big-O Notation", category: "Concepts", description: "Time/space complexity, common classes, analysis.", tags: ["algorithms", "complexity"] },
  { slug: "clean-code", label: "Clean Code Principles", category: "Concepts", description: "Naming, functions, comments, SRP, DRY, YAGNI.", tags: ["craftsmanship", "quality"] },
];

export function getTopic(slug: string): LearningTopicDef | undefined {
  return LEARNING_TOPICS.find((t) => t.slug === slug);
}

export function topicsByCategory(): Record<string, LearningTopicDef[]> {
  const out: Record<string, LearningTopicDef[]> = {};
  for (const t of LEARNING_TOPICS) {
    if (!out[t.category]) out[t.category] = [];
    out[t.category].push(t);
  }
  return out;
}

/** Simplified "related topics" — shared tags = similarity score, no embeddings. */
export function relatedTopics(slug: string, limit = 5): LearningTopicDef[] {
  const topic = getTopic(slug);
  if (!topic) return [];
  return LEARNING_TOPICS
    .filter((t) => t.slug !== slug)
    .map((t) => ({
      topic: t,
      score: t.tags.filter((tag) => topic.tags.includes(tag)).length,
    }))
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((x) => x.topic);
}
