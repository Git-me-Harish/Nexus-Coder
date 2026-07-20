"use client";

import { create } from "zustand";
import type { Mode, Phase } from "@/lib/nexus/constants";
import { PHASE_ROUTING } from "@/lib/nexus/constants";

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
  view: "auth" | "landing" | "dashboard" | "session";
  // Projects & sessions
  projects: Project[];
  activeProject: Project | null;
  sessions: Session[];
  activeSession: Session | null;
  messages: Message[];
  files: SessionFile[];
  specs: Spec[];
  // UI
  rightPanel: "spec" | "files" | "usage" | "learning" | null;
  showSpecModal: boolean;
  showModelSwitcher: boolean;
  showModelConfig: boolean;
  // Streaming
  isStreaming: boolean;
  streamingText: string;
  streamingPhase: Phase | null;
  streamingWorker: string | null;
  streamingModel: string | null;
  streamingModelId: string | null;
  streamingTokensUsed: number;
  streamingTokensBudget: number;
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
  setShowModelConfig: (b: boolean) => void;
  // Mobile UI
  mobileSidebarOpen: boolean;
  setMobileSidebarOpen: (b: boolean) => void;
  mobileRightPanelOpen: boolean;
  setMobileRightPanelOpen: (b: boolean) => void;
  startStream: (modelId: string, modelName: string, phase: Phase, worker: string, tokensUsed: number, tokensBudget: number) => void;
  appendToken: (delta: string) => void;
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
  showModelConfig: false,
  isStreaming: false,
  streamingText: "",
  streamingPhase: null,
  streamingWorker: null,
  streamingModel: null,
  streamingModelId: null,
  streamingTokensUsed: 0,
  streamingTokensBudget: 0,
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
  setShowModelConfig: (b) => set({ showModelConfig: b }),
  mobileSidebarOpen: false,
  setMobileSidebarOpen: (b) => set({ mobileSidebarOpen: b }),
  mobileRightPanelOpen: false,
  setMobileRightPanelOpen: (b) => set({ mobileRightPanelOpen: b }),

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
      lastError: null,
    }),
  appendToken: (delta) =>
    set((st) => ({ streamingText: st.streamingText + delta })),
  finishStream: () =>
    set((st) => ({
      isStreaming: false,
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
      lastError: null,
    }),
  updateActiveSession: (patch) =>
    set((st) => (st.activeSession ? { activeSession: { ...st.activeSession, ...patch } } : {})),
}));

export function pickModelForPhase(phase: Phase, baseModelId?: string | null): string {
  if (baseModelId) return baseModelId;
  return PHASE_ROUTING[phase] ?? "claude-sonnet-4-6";
}