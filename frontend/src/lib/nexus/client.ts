"use client";

import { useAuthStore } from "@/stores/authStore";
import { sudoHeader } from "@/stores/sudoStore";
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

/**
 * Multipart upload. Cannot go through `req`: authHeaders() always sets
 * Content-Type: application/json, and for a FormData body the browser has to
 * set that header itself so it can include the multipart boundary.
 */
async function upload<T>(path: string, file: File, _retried = false): Promise<T> {
  const token = useAuthStore.getState().token;
  // Rebuilt per attempt: a FormData body is a one-shot stream, so the retry
  // below cannot reuse the one already sent.
  const body = new FormData();
  body.append("file", file);

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body,
  });

  if (res.status === 401 && !_retried) {
    if (await tryRefresh()) return upload<T>(path, file, true);
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: { message: "Upload failed" } }));
    throw new ApiError(res.status, err?.error?.message ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
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
    updateProfile: (data: { name?: string; bio?: string; company?: string; location?: string }) =>
      req<any>("/api/auth/me", { method: "PATCH", body: JSON.stringify(data) }),
    updatePreferences: (data: { theme?: string; defaultMode?: string; defaultModelId?: string }) =>
      req<any>("/api/auth/preferences", { method: "PATCH", body: JSON.stringify(data) }),
    changePassword: (data: { currentPassword?: string; newPassword: string }) =>
      req<{ token: string; refreshToken: string; user: any; tenant: any }>("/api/auth/change-password", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    // Always resolves with the same generic message whether or not the
    // address has an account — the backend deliberately doesn't say, so the
    // UI must not imply otherwise.
    forgotPassword: (email: string) =>
      req<{ ok: boolean; message: string; expiresInMinutes: number }>("/api/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email }),
      }),
    resetPassword: (token: string, newPassword: string) =>
      req<{ token: string; refreshToken: string; user: any; tenant: any }>("/api/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ token, newPassword }),
      }),
    /** Re-confirm the password to unlock API-key management for a few minutes. */
    sudo: (password: string) =>
      req<{ token: string; expiresInMinutes: number }>("/api/auth/sudo", {
        method: "POST",
        body: JSON.stringify({ password }),
      }),
    uploadAvatar: (file: File) => upload<{ avatarUrl: string }>("/api/auth/me/avatar", file),
    deleteAvatar: () => req<{ avatarUrl: string | null }>("/api/auth/me/avatar", { method: "DELETE" }),
    // "Continue with GitHub" -- sign in / sign up, distinct from the
    // account-linking flow under api.github.* (which needs an existing session).
    githubAuthorizeUrl: () => req<{ url: string }>("/api/auth/github/authorize"),
    githubExchange: (code: string) =>
      req<{ token: string; refreshToken: string; user: any; tenant: any }>("/api/auth/github/exchange", {
        method: "POST",
        body: JSON.stringify({ code }),
      }),
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
    update: (id: string, patch: { title?: string; starred?: boolean; pinned?: boolean; status?: string; buildDepth?: string }) =>
      req<{ session: any }>(`/api/sessions/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
    delete: (id: string) =>
      req<{ ok: boolean }>(`/api/sessions/${id}`, { method: "DELETE" }),
    switchModel: (id: string, modelId: string) =>
      req<{ session: any; from: string; to: string }>(`/api/sessions/${id}/model`, {
        method: "POST",
        body: JSON.stringify({ modelId }),
      }),
    confirmIdea: (id: string) =>
      req<{ session: any }>(`/api/sessions/${id}/idea/confirm`, { method: "PATCH" }),
    confirmPlan: (id: string) =>
      req<{ session: any }>(`/api/sessions/${id}/plan/confirm`, { method: "PATCH" }),
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
    exportZipUrl: (sessionId: string) => `${API_BASE_URL}/api/sessions/${sessionId}/export/zip`,
  },
  tests: {
    run: (sessionId: string, name: string, code: string) =>
      req<{ result: { filePath: string; passed: boolean; exitCode: number; output: string } }>(
        `/api/sessions/${sessionId}/tests`,
        { method: "POST", body: JSON.stringify({ name, code }) }
      ),
  },
  github: {
    authorizeUrl: () => req<{ url: string }>("/api/integrations/github/authorize"),
    status: () => req<{ connected: boolean; githubLogin: string | null }>("/api/integrations/github/status"),
    disconnect: () => req<{ ok: boolean }>("/api/integrations/github/disconnect", { method: "DELETE" }),
    push: (sessionId: string) =>
      req<{ repoUrl: string }>(`/api/sessions/${sessionId}/github/push`, { method: "POST" }),
  },
  preview: {
    start: (sessionId: string) =>
      req<{ proxyPath: string; kind: string }>(`/api/sessions/${sessionId}/preview/start`, { method: "POST" }),
    stop: (sessionId: string) =>
      req<{ ok: boolean }>(`/api/sessions/${sessionId}/preview`, { method: "DELETE" }),
  },
  models: {
    list: () => req<{ models: any[] }>("/api/models"),
  },
  providers: {
    status: () => req<{ providers: any[] }>("/api/providers/status"),
  },
  // Every route here is behind step-up auth on the server and answers 403
  // SUDO_REQUIRED without a live elevation, so each call carries the
  // X-Sudo-Token header (see stores/sudoStore.ts).
  credentials: {
    list: () => req<{ credentials: any[] }>("/api/providers/credentials", { headers: sudoHeader() }),
    save: (provider: string, apiKey: string) =>
      req<{ credential: any }>(`/api/providers/credentials/${provider}`, {
        method: "PUT",
        headers: sudoHeader(),
        body: JSON.stringify({ apiKey }),
      }),
    validate: (provider: string) =>
      req<{ credential: any }>(`/api/providers/credentials/${provider}/validate`, {
        method: "POST",
        headers: sudoHeader(),
      }),
    remove: (provider: string) =>
      req<{ ok: boolean }>(`/api/providers/credentials/${provider}`, {
        method: "DELETE",
        headers: sudoHeader(),
      }),
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