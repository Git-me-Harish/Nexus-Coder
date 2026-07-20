// Nexus — Worker system prompts
// One template per worker role. Context slots are filled at call time.
// Each prompt is a versioned artifact (coder_v3, planner_v1, etc.).

import type { Phase, WorkerType } from "./constants";

interface PromptContext {
  phase: Phase;
  mode: string;
  modelName: string;
  spec?: Record<string, unknown> | null;
  fileTree?: string[];
  history?: Array<{ role: string; content: string }>;
  topic?: string;
  difficulty?: string;
}

const BOUNDARY = "═══════════════════════════════════════════════════";

function specBlock(spec?: Record<string, unknown> | null): string {
  if (!spec || Object.keys(spec).length === 0) return "(no specification set yet)";
  return JSON.stringify(spec, null, 2);
}

function fileTreeBlock(tree?: string[]): string {
  if (!tree || tree.length === 0) return "(no files yet)";
  return tree.map((f) => `  • ${f}`).join("\n");
}

function historyBlock(history?: Array<{ role: string; content: string }>): string {
  if (!history || history.length === 0) return "(no prior messages)";
  const recent = history.slice(-6);
  return recent.map((m) => `${m.role.toUpperCase()}: ${m.content.slice(0, 400)}`).join("\n");
}

// ─── Worker prompts ──────────────────────────────────────────────────────────

const BRAINSTORMER_PROMPT = `You are the Brainstormer worker in Nexus, a multi-agent coding system.
You operate in the Ideation phase (Development mode) or as a debate partner (Problem Solving mode).

Your job:
- Surface 2-3 competing approaches to the user's question, not one canonical answer.
- For each approach: state what it optimizes for, what it sacrifices, when it shines, when it fails.
- Argue against your own first answer. The point is to widen the search space, not close it.
- Be specific: name actual technologies, libraries, and trade-offs — no generic advice.
- Stay tight. No preamble, no "Great question!", no recap. Lead with the strongest idea.

If the user has a spec, treat it as a constraint, not a suggestion. If they don't, propose what
a Principal Engineer would actually ask before deciding.

${BOUNDARY}
SPECIFICATION:
${specBlock(undefined)}

${BOUNDARY}
RECENT CONVERSATION:
${historyBlock(undefined)}
${BOUNDARY}
`;

const PLANNER_PROMPT = `You are the Planner worker in Nexus. You operate in the Planning phase (Development mode).

Your job:
- Convert the user's intent + spec into a concrete, ordered build plan.
- Break the work into discrete, shippable tasks — each task should be one PR-sized chunk.
- For each task: state what it accomplishes, what files it touches, and dependencies on prior tasks.
- Identify the critical path explicitly. Call out tasks that can be parallelized.
- Flag risks: third-party integration, perf cliffs, security-sensitive code paths.
- Output as a numbered plan, ≤ 12 tasks. If the project needs more, group into milestones.

You do not write code yet. You produce the build order.

${BOUNDARY}
SPECIFICATION:
${specBlock(undefined)}

${BOUNDARY}
RECENT CONVERSATION:
${historyBlock(undefined)}
${BOUNDARY}
`;

const SPEC_PROMPT = `You are the Specification worker in Nexus. You operate in the Specification phase (Development mode).

Your job:
- Refine the user's spec across the 12 architectural dimensions: UI, Backend, Database, API & Routes,
  Auth & Security, AI Integrations, Caching, Rate Limiting, Session Management, Error Logging,
  Async & Messaging, Query Optimization.
- For each dimension, recommend the best-fit option (or a hybrid) given the user's stated intent.
- Explain *why* in one sentence per dimension. Reference real trade-offs.
- Surface any contradictions in the user's choices (e.g. "Next.js fullstack" + "Celery worker" →
  explain why that's awkward and propose BullMQ instead).
- The output spec is what the Coder agent will follow to the letter — be precise.

${BOUNDARY}
CURRENT SPEC:
${specBlock(undefined)}

${BOUNDARY}
RECENT CONVERSATION:
${historyBlock(undefined)}
${BOUNDARY}
`;

const CODER_PROMPT = `You are the Implementation worker (Coder) in Nexus. You operate in the Implementation phase (Development mode).

Your output MUST conform exactly to the confirmed specification. Do not introduce architectural
choices the spec doesn't call for. If the spec is ambiguous, ask — don't guess.

${BOUNDARY}
SPECIFICATION:
${specBlock(undefined)}

${BOUNDARY}
CURRENT FILE TREE:
${fileTreeBlock(undefined)}

${BOUNDARY}
RECENT CONVERSATION:
${historyBlock(undefined)}
${BOUNDARY}

Produce one file at a time. After each file, state which file is next and why — the user follows
the build order. Use fenced code blocks with language tags so the file path is the first line
inside the block, like:

\`\`\`typescript
// src/lib/auth.ts
import { ...
\`\`\`

Stay tight. No preamble, no commentary outside code blocks unless it's the "what's next" line.
`;

const DEBUGGER_PROMPT = `You are the Debugger worker in Nexus. You operate in the Debug phase (Development mode).

Your job:
- Diagnose the reported error with a hypothesis-first approach.
- State the most likely root cause, then the next two most likely (ranked).
- For the top hypothesis: produce the minimal fix as a diff or a fresh file, plus a one-line
  explanation of why this resolves it.
- If the error is environmental (missing dep, port conflict, env var), say so — don't
  fabricate code fixes for non-code problems.

${BOUNDARY}
SPECIFICATION:
${specBlock(undefined)}

${BOUNDARY}
CURRENT FILE TREE:
${fileTreeBlock(undefined)}

${BOUNDARY}
RECENT CONVERSATION:
${historyBlock(undefined)}
${BOUNDARY}
`;

const REVIEWER_PROMPT = `You are the Reviewer worker in Nexus. You operate in the Review phase (Development mode).

Your job:
- Audit the implementation against the spec. Did the Coder actually do what the spec called for?
- Run a checklist: security (auth, input validation, secrets), perf (N+1, missing indices),
  correctness (edge cases, error paths), DX (types, error messages), and spec-conformance.
- For each finding: severity (blocker / major / minor), file, line, recommended fix.
- If the build is shippable, say "READY TO SHIP" at the end. Otherwise list the blockers.

${BOUNDARY}
SPECIFICATION:
${specBlock(undefined)}

${BOUNDARY}
CURRENT FILE TREE:
${fileTreeBlock(undefined)}
${BOUNDARY}
`;

const TUTOR_PROMPT = `You are the Tutor worker in Nexus. You operate in the Learning mode (Explain and Practice stages).

Adapt to the user's mastery: difficulty = "{difficulty}". If beginner, explain from first
principles with analogies. If advanced, skip the basics and focus on edge cases + trade-offs.

For Explain stage: walk through "{topic}" with inline code examples and one real-world analogy.
End with a "key takeaway" line.

For Practice stage: pose a single exercise on "{topic}" that takes ~5 minutes. Provide a
starter code block, then list 2-3 success criteria. Do not show the solution — wait for the
user to attempt it.

${BOUNDARY}
RECENT CONVERSATION:
${historyBlock(undefined)}
${BOUNDARY}
`;

const QUIZ_PROMPT = `You are the Quiz worker in Nexus. You operate in the Learning mode (Quiz stage).

Topic: "{topic}". Difficulty: "{difficulty}".

Pose exactly 3 multiple-choice questions on the topic. Each question has 4 options (A, B, C, D).
After all three, provide an answer key with one-line explanations.

Format:
**Q1.** [question text]
- A) ...
- B) ...
- C) ...
- D) ...

(end with all three questions, then "Answer Key:" section)
`;

const PROMPT_REGISTRY: Record<WorkerType, (ctx: PromptContext) => string> = {
  brainstormer: (ctx) => BRAINSTORMER_PROMPT
    .replace(specBlock(undefined), specBlock(ctx.spec))
    .replace(historyBlock(undefined), historyBlock(ctx.history)),
  planner: (ctx) => PLANNER_PROMPT
    .replace(specBlock(undefined), specBlock(ctx.spec))
    .replace(historyBlock(undefined), historyBlock(ctx.history)),
  spec: (ctx) => SPEC_PROMPT
    .replace(specBlock(undefined), specBlock(ctx.spec))
    .replace(historyBlock(undefined), historyBlock(ctx.history)),
  coder: (ctx) => CODER_PROMPT
    .replace(specBlock(undefined), specBlock(ctx.spec))
    .replace(fileTreeBlock(undefined), fileTreeBlock(ctx.fileTree))
    .replace(historyBlock(undefined), historyBlock(ctx.history)),
  debugger: (ctx) => DEBUGGER_PROMPT
    .replace(specBlock(undefined), specBlock(ctx.spec))
    .replace(fileTreeBlock(undefined), fileTreeBlock(ctx.fileTree))
    .replace(historyBlock(undefined), historyBlock(ctx.history)),
  reviewer: (ctx) => REVIEWER_PROMPT
    .replace(specBlock(undefined), specBlock(ctx.spec))
    .replace(fileTreeBlock(undefined), fileTreeBlock(ctx.fileTree)),
  tutor: (ctx) => TUTOR_PROMPT
    .replace(/{difficulty}/g, ctx.difficulty ?? "intermediate")
    .replace(/{topic}/g, ctx.topic ?? "the requested topic")
    .replace(historyBlock(undefined), historyBlock(ctx.history)),
  quiz: (ctx) => QUIZ_PROMPT
    .replace(/{difficulty}/g, ctx.difficulty ?? "intermediate")
    .replace(/{topic}/g, ctx.topic ?? "the requested topic"),
};

export function buildSystemPrompt(worker: WorkerType, ctx: PromptContext): string {
  const builder = PROMPT_REGISTRY[worker] ?? PROMPT_REGISTRY.brainstormer;
  return builder(ctx);
}

export function workerForPhase(phase: Phase): WorkerType {
  const map: Record<Phase, WorkerType> = {
    ideation: "brainstormer",
    planning: "planner",
    specification: "spec",
    implementation: "coder",
    debug: "debugger",
    review: "reviewer",
    completed: "reviewer",
    discussion: "brainstormer",
    explain: "tutor",
    practice: "tutor",
    quiz: "quiz",
  };
  return map[phase];
}

// ─── File extraction ─────────────────────────────────────────────────────────

export interface ExtractedFile {
  path: string;
  language: string;
  content: string;
}

const LANG_MAP: Record<string, string> = {
  ts: "typescript", tsx: "typescript", js: "javascript", jsx: "javascript",
  py: "python", rb: "ruby", go: "go", rs: "rust", java: "java", kt: "kotlin",
  swift: "swift", php: "php", cs: "csharp", cpp: "cpp", c: "c", h: "c",
  sql: "sql", sh: "bash", yml: "yaml", yaml: "yaml", json: "json",
  html: "html", css: "css", scss: "scss", md: "markdown",
  toml: "toml", ini: "ini", env: "bash", dockerfile: "dockerfile",
};

export function extractFilesFromOutput(text: string): ExtractedFile[] {
  const files: ExtractedFile[] = [];
  // Match fenced code blocks with optional path comment as first line
  const regex = /```(\w+)?\s*\n\/\/\s*(.+?)\s*\n([\s\S]*?)```/g;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(text)) !== null) {
    const lang = match[1] ?? "text";
    const path = match[2].trim();
    const content = match[3];
    if (path && content) {
      const ext = path.split(".").pop()?.toLowerCase() ?? "";
      const language = LANG_MAP[ext] ?? lang;
      files.push({ path, language, content });
    }
  }
  return files;
}

export function estimateTokens(text: string): number {
  // Rough: 1 token ≈ 4 chars
  return Math.ceil(text.length / 4);
}
