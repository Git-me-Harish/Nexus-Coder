"use client";

import { create } from "zustand";
import type { Mode, Phase } from "@/lib/nexus/constants";
import { DEFAULT_MODEL_ID, PHASE_ROUTING } from "@/lib/nexus/constants";

/** Which stage of the backend reasoning graph is currently running.
 *  Mirrors the `stage` SSE event in app/api/v1/routes/agent_stream.py.
 *  "acting" means the agent is executing real tools -- writing files to the
 *  project and running commands in the sandbox. */
export type AgentStage = "planning" | "answering" | "reviewing" | "revising" | "acting";

/** One real tool execution: a file written, a command run. `ok` is the actual
 *  outcome (a non-zero exit code, a rejected path), not a prediction. */
export interface ToolActivity {
  id: string;
  name: string;
  summary: string;
  step: number;
  status: "running" | "ok" | "error";
  preview?: string;
}

/** The review stage's verdict on a draft answer. */
export interface Critique {
  approved: boolean;
  issues: string[];
  phaseComplete: boolean;
  reason: string;
  /** True while the agent is rewriting a rejected draft. */
  revising: boolean;
}

export interface Project {
  id: string;
  name: string;
  description?: string | null;
  mode: Mode;
  status: string;
  starred?: boolean;
  pinned?: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface Session {
  id: string;
  projectId: string;
  mode: Mode;
  currentPhase: Phase;
  baseModelId: string;
  tokensUsed: number;
  tokensBudget: number;
  status: string;
  title?: string | null;
  starred?: boolean;
  pinned?: boolean;
  sandboxStatus?: string;
  sandboxPreviewUrl?: string | null;
  githubRepoUrl?: string | null;
  decisionDocUrl?: string | null;
  // Confirmation gates for the artifact phases (IDEA.md/PLAN.md, written by
  // the agent via write_file) -- mirrors how Specification.confirmedAt
  // already gates specification->implementation. See
  // backend/app/services/session_service.py confirm_idea/confirm_plan.
  ideaConfirmedAt?: string | null;
  planConfirmedAt?: string | null;
  // Set once via the one-time Implementation-phase picker; null until then.
  buildDepth?: "prototype" | "mvp" | "production" | null;
  createdAt: string;
  updatedAt: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  phase?: string | null;
  modelId?: string | null;
  tokensIn?: number | null;
  tokensOut?: number | null;
  latencyMs?: number | null;
  createdAt: string;
}

export interface SessionFile {
  id: string;
  filePath: string;
  content: string;
  language?: string | null;
  version: number;
  updatedAt: string;
}

export interface Spec {
  id: string;
  version: number;
  dimensions: Record<string, unknown>;
  isCurrent: boolean;
  confirmedAt?: string | null;
}

interface AppState {
  // Navigation
  view: "auth" | "landing" | "dashboard" | "session" | "profile" | "reset";
  // Projects & sessions
  projects: Project[];
  activeProject: Project | null;
  sessions: Session[];
  activeSession: Session | null;
  messages: Message[];
  files: SessionFile[];
  specs: Spec[];
  // UI
  rightPanel: "spec" | "files" | "usage" | "learning" | "preview" | "tests" | null;
  showSpecModal: boolean;
  showModelSwitcher: boolean;
  // Streaming
  isStreaming: boolean;
  streamingText: string;
  streamingPhase: Phase | null;
  streamingWorker: string | null;
  streamingModel: string | null;
  streamingModelId: string | null;
  streamingTokensUsed: number;
  streamingTokensBudget: number;
  // Reasoning pipeline (see backend app/agents/graph.py): the agent plans
  // before it answers and reviews before it finishes, and these surface that
  // to the user instead of leaving them watching a spinner.
  streamingStage: AgentStage | null;
  streamingReasoning: string;
  streamingCritique: Critique | null;
  streamingTools: ToolActivity[];
  lastError: string | null;
  // Actions
  setView: (v: AppState["view"]) => void;
  setProjects: (p: Project[]) => void;
  setActiveProject: (p: Project | null) => void;
  updateProject: (id: string, patch: Partial<Project>) => void;
  removeProject: (id: string) => void;
  setSessions: (s: Session[]) => void;
  setActiveSession: (s: Session | null) => void;
  updateSession: (id: string, patch: Partial<Session>) => void;
  removeSession: (id: string) => void;
  setMessages: (m: Message[]) => void;
  appendMessage: (m: Message) => void;
  setFiles: (f: SessionFile[]) => void;
  setSpecs: (s: Spec[]) => void;
  setRightPanel: (p: AppState["rightPanel"]) => void;
  setShowSpecModal: (b: boolean) => void;
  setShowModelSwitcher: (b: boolean) => void;
  // Mobile UI
  mobileSidebarOpen: boolean;
  setMobileSidebarOpen: (b: boolean) => void;
  mobileRightPanelOpen: boolean;
  setMobileRightPanelOpen: (b: boolean) => void;
  // Desktop sidebar collapse (mobile keeps its own drawer, unaffected)
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (b: boolean) => void;
  startStream: (modelId: string, modelName: string, phase: Phase, worker: string, tokensUsed: number, tokensBudget: number) => void;
  appendToken: (delta: string) => void;
  appendReasoning: (delta: string) => void;
  setStreamingStage: (stage: AgentStage | null) => void;
  setStreamingCritique: (c: Critique | null) => void;
  /** A tool started executing -- shown immediately, before its outcome is known. */
  startToolActivity: (t: Omit<ToolActivity, "status">) => void;
  /** That tool finished; `ok` is what actually happened. */
  finishToolActivity: (id: string, ok: boolean, preview?: string) => void;
  /** Drop what has streamed so far for one scope and re-render from empty --
   *  a provider died mid-answer and we fell back, or a draft was rejected and
   *  is being replaced by its revision. Without this the user reads the
   *  abandoned text with the replacement appended to it. */
  clearStreamScope: (scope: "token" | "reasoning") => void;
  finishStream: () => void;
  failStream: (err: string) => void;
  resetStream: () => void;
  updateActiveSession: (patch: Partial<Session>) => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  view: "auth",
  projects: [],
  activeProject: null,
  sessions: [],
  activeSession: null,
  messages: [],
  files: [],
  specs: [],
  rightPanel: null,
  showSpecModal: false,
  showModelSwitcher: false,
  isStreaming: false,
  streamingText: "",
  streamingPhase: null,
  streamingWorker: null,
  streamingModel: null,
  streamingModelId: null,
  streamingTokensUsed: 0,
  streamingTokensBudget: 0,
  streamingStage: null,
  streamingReasoning: "",
  streamingCritique: null,
  streamingTools: [],
  lastError: null,

  setView: (v) => set({ view: v }),
  setProjects: (p) => set({ projects: p }),
  setActiveProject: (p) => set({ activeProject: p }),
  updateProject: (id, patch) =>
    set((st) => ({
      projects: st.projects.map((p) => (p.id === id ? { ...p, ...patch } : p)),
      activeProject: st.activeProject?.id === id ? { ...st.activeProject, ...patch } : st.activeProject,
    })),
  removeProject: (id) =>
    set((st) => ({
      projects: st.projects.filter((p) => p.id !== id),
      sessions: st.activeProject?.id === id ? [] : st.sessions,
      activeProject: st.activeProject?.id === id ? null : st.activeProject,
      activeSession: st.activeProject?.id === id ? null : st.activeSession,
    })),
  setSessions: (s) => set({ sessions: s }),
  setActiveSession: (s) =>
    set({
      activeSession: s,
      rightPanel: s?.mode === "development" ? "files" : s?.mode === "learning" ? "learning" : null,
    }),
  updateSession: (id, patch) =>
    set((st) => ({
      sessions: st.sessions.map((s) => (s.id === id ? { ...s, ...patch } : s)),
      activeSession: st.activeSession?.id === id ? { ...st.activeSession, ...patch } : st.activeSession,
    })),
  removeSession: (id) =>
    set((st) => ({
      sessions: st.sessions.filter((s) => s.id !== id),
      activeSession: st.activeSession?.id === id ? null : st.activeSession,
      messages: st.activeSession?.id === id ? [] : st.messages,
      files: st.activeSession?.id === id ? [] : st.files,
    })),
  setMessages: (m) => set({ messages: m }),
  appendMessage: (m) => set((st) => ({ messages: [...st.messages, m] })),
  setFiles: (f) => set({ files: f }),
  setSpecs: (s) => set({ specs: s }),
  setRightPanel: (p) => set({ rightPanel: p }),
  setShowSpecModal: (b) => set({ showSpecModal: b }),
  setShowModelSwitcher: (b) => set({ showModelSwitcher: b }),
  mobileSidebarOpen: false,
  setMobileSidebarOpen: (b) => set({ mobileSidebarOpen: b }),
  mobileRightPanelOpen: false,
  setMobileRightPanelOpen: (b) => set({ mobileRightPanelOpen: b }),
  sidebarCollapsed: false,
  setSidebarCollapsed: (b) => set({ sidebarCollapsed: b }),

  startStream: (modelId, modelName, phase, worker, tokensUsed, tokensBudget) =>
    set({
      isStreaming: true,
      streamingText: "",
      streamingPhase: phase,
      streamingWorker: worker,
      streamingModel: modelName,
      streamingModelId: modelId,
      streamingTokensUsed: tokensUsed,
      streamingTokensBudget: tokensBudget,
      streamingStage: null,
      streamingReasoning: "",
      streamingCritique: null,
      streamingTools: [],
      lastError: null,
    }),
  appendToken: (delta) =>
    set((st) => ({ streamingText: st.streamingText + delta })),
  appendReasoning: (delta) =>
    set((st) => ({ streamingReasoning: st.streamingReasoning + delta })),
  setStreamingStage: (stage) => set({ streamingStage: stage }),
  setStreamingCritique: (c) => set({ streamingCritique: c }),
  startToolActivity: (t) =>
    set((st) => ({ streamingTools: [...st.streamingTools, { ...t, status: "running" }] })),
  finishToolActivity: (id, ok, preview) =>
    set((st) => ({
      streamingTools: st.streamingTools.map((t) =>
        t.id === id ? { ...t, status: ok ? "ok" : "error", preview } : t
      ),
    })),
  clearStreamScope: (scope) =>
    set(scope === "reasoning" ? { streamingReasoning: "" } : { streamingText: "" }),
  finishStream: () =>
    set((st) => ({
      isStreaming: false,
      streamingStage: null,
      messages: [
        ...st.messages,
        {
          id: `stream-${Date.now()}`,
          role: "assistant",
          content: st.streamingText,
          phase: st.streamingPhase,
          modelId: st.streamingModelId,
          createdAt: new Date().toISOString(),
        },
      ],
      streamingText: "",
    })),
  failStream: (err) =>
    set({ isStreaming: false, lastError: err }),
  resetStream: () =>
    set({
      isStreaming: false,
      streamingText: "",
      streamingPhase: null,
      streamingWorker: null,
      streamingModel: null,
      streamingModelId: null,
      streamingStage: null,
      streamingReasoning: "",
      streamingCritique: null,
      streamingTools: [],
      lastError: null,
    }),
  updateActiveSession: (patch) =>
    set((st) => (st.activeSession ? { activeSession: { ...st.activeSession, ...patch } } : {})),
}));

export function pickModelForPhase(phase: Phase, baseModelId?: string | null): string {
  if (baseModelId) return baseModelId;
  return PHASE_ROUTING[phase] ?? DEFAULT_MODEL_ID;
}