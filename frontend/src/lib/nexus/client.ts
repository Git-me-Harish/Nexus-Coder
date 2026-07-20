"use client";

import { useAuthStore } from "@/stores/authStore";
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export function handleUnauthorized() {
  useAuthStore.getState().clear();
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("nexus:logout"));
  }
}

function authHeaders(): HeadersInit {
  const token = useAuthStore.getState().token;
  return token ? { Authorization: `Bearer ${token}`, "Content-Type": "application/json" } : { "Content-Type": "application/json" };
}

let refreshInFlight: Promise<boolean> | null = null;
export async function tryRefresh(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    const refreshToken = useAuthStore.getState().refreshToken;
    if (!refreshToken) return false;
    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refreshToken }),
      });
      if (!res.ok) {
        handleUnauthorized();
        return false;
      }
      const data = await res.json();
      useAuthStore.getState().setSession({
        user: data.user,
        tenant: data.tenant,
        token: data.token,
        refreshToken: data.refreshToken,
      });
      return true;
    } catch {
      return false;
    }
  })();

  const result = await refreshInFlight;
  refreshInFlight = null;
  return result;
}

async function req<T>(path: string, init?: RequestInit, _retried = false): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { ...authHeaders(), ...(init?.headers ?? {}) },
  });

  if (res.status === 401 && !_retried && !path.startsWith("/api/auth/")) {
    const refreshed = await tryRefresh();
    if (refreshed) return req<T>(path, init, true);
    // tryRefresh already called handleUnauthorized on genuine failure;
    // fall through to throw below so the caller's catch block still runs.
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: { message: "Request failed" } }));
    const message = err?.error?.message ?? `HTTP ${res.status}`;
    if (res.status === 401 && _retried) handleUnauthorized();
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

export const api = {
  auth: {
    register: (email: string, password: string, name?: string) =>
      req<{ token: string; refreshToken: string; user: any; tenant: any }>("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password, name }),
      }),
    login: (email: string, password: string) =>
      req<{ token: string; refreshToken: string; user: any; tenant: any }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
    me: () => req<{ user: any; tenant: any; preferences: any }>("/api/auth/me"),
  },
  projects: {
    list: () => req<{ projects: any[] }>("/api/projects"),
    create: (data: { name: string; description?: string; mode?: string }) =>
      req<{ project: any }>("/api/projects", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, patch: { name?: string; description?: string; starred?: boolean; pinned?: boolean; status?: string }) =>
      req<{ project: any }>(`/api/projects/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
    delete: (id: string) =>
      req<{ ok: boolean }>(`/api/projects/${id}`, { method: "DELETE" }),
  },
  sessions: {
    list: (projectId?: string) =>
      req<{ sessions: any[] }>(`/api/sessions${projectId ? `?projectId=${projectId}` : ""}`),
    create: (data: { projectId: string; mode: string; title?: string; baseModelId?: string }) =>
      req<{ session: any }>("/api/sessions", { method: "POST", body: JSON.stringify(data) }),
    get: (id: string) => req<{ session: any }>(`/api/sessions/${id}`),
    advancePhase: (id: string, target?: string) =>
      req<{ session: any }>(`/api/sessions/${id}`, { method: "POST", body: JSON.stringify({ target }) }),
    update: (id: string, patch: { title?: string; starred?: boolean; pinned?: boolean; status?: string }) =>
      req<{ session: any }>(`/api/sessions/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
    delete: (id: string) =>
      req<{ ok: boolean }>(`/api/sessions/${id}`, { method: "DELETE" }),
    switchModel: (id: string, modelId: string) =>
      req<{ session: any; from: string; to: string }>(`/api/sessions/${id}/model`, {
        method: "POST",
        body: JSON.stringify({ modelId }),
      }),
  },
  messages: {
    list: (sessionId: string) => req<{ messages: any[] }>(`/api/sessions/${sessionId}/messages`),
    send: (sessionId: string, content: string) =>
      req<{ message: any }>(`/api/sessions/${sessionId}/messages`, {
        method: "POST",
        body: JSON.stringify({ content }),
      }),
  },
  spec: {
    get: (sessionId: string) => req<{ specs: any[]; current: any | null }>(`/api/sessions/${sessionId}/spec`),
    save: (sessionId: string, dimensions: Record<string, unknown>) =>
      req<{ spec: any }>(`/api/sessions/${sessionId}/spec`, {
        method: "PUT",
        body: JSON.stringify({ dimensions }),
      }),
    confirm: (sessionId: string) =>
      req<{ spec: any }>(`/api/sessions/${sessionId}/spec`, {
        method: "PATCH",
        body: JSON.stringify({ action: "confirm" }),
      }),
  },
  files: {
    list: (sessionId: string) => req<{ files: any[] }>(`/api/sessions/${sessionId}/files`),
  },
  models: {
    list: () => req<{ models: any[] }>("/api/models"),
  },
  providers: {
    status: () => req<{ providers: any[] }>("/api/providers/status"),
  },
  credentials: {
    list: () => req<{ credentials: any[] }>("/api/providers/credentials"),
    save: (provider: string, apiKey: string) =>
      req<{ credential: any }>(`/api/providers/credentials/${provider}`, {
        method: "PUT",
        body: JSON.stringify({ apiKey }),
      }),
    validate: (provider: string) =>
      req<{ credential: any }>(`/api/providers/credentials/${provider}/validate`, { method: "POST" }),
    remove: (provider: string) =>
      req<{ ok: boolean }>(`/api/providers/credentials/${provider}`, { method: "DELETE" }),
  },
  learning: {
    listTopics: (sessionId: string) =>
      req<{ topics: any[] }>(`/api/sessions/${sessionId}/learning/start`),
    startTopic: (sessionId: string, topicSlug: string) =>
      req<{ topic: any }>(`/api/sessions/${sessionId}/learning/start`, {
        method: "POST",
        body: JSON.stringify({ topicSlug }),
      }),
    advanceTopic: (sessionId: string, topicId: string) =>
      req<{ topic: any }>(`/api/sessions/${sessionId}/learning/${topicId}/advance`, {
        method: "POST",
      }),
    submitQuiz: (sessionId: string, topicId: string, answers: Record<number, string>, quizText: string) =>
      req<{ topic: any; score: number; mastery: any; passed: boolean }>(
        `/api/sessions/${sessionId}/learning/${topicId}/submit-quiz`,
        { method: "POST", body: JSON.stringify({ answers, quizText }) }
      ),
  },
  knowledge: {
    get: () => req<{ profile: any[]; summary: any }>("/api/me/knowledge"),
  },
  usage: {
    summary: (sessionId?: string) =>
      req<{ summary: any; byModel: any[]; sessions: any[]; recent: any[] }>(
        `/api/usage${sessionId ? `?sessionId=${sessionId}` : ""}`
      ),
  },
  streamUrl: (sessionId: string) => `${API_BASE_URL}/api/sessions/${sessionId}/agent/stream`,
};