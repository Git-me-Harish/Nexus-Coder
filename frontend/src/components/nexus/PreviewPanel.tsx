"use client";

import { useState } from "react";
import { Play, Square, RefreshCw, AlertTriangle, ExternalLink } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { api, API_BASE_URL, ApiError } from "@/lib/nexus/client";
import { cn } from "@/lib/utils";

/**
 * Live preview: starts a real, network-enabled container running the
 * generated app (backend/app/agents/preview.py) and renders it in an
 * iframe, proxied through the backend so the browser only ever talks to
 * one authenticated origin. Only Python (FastAPI/Flask) and static
 * HTML/CSS/JS apps are supported -- the agent's build sandbox has no
 * network, so a Node project's dependencies were never installed anywhere,
 * and that shows up here as an explicit message, not a silent blank frame.
 */
export default function PreviewPanel() {
  const { activeSession } = useAppStore();
  const [status, setStatus] = useState<"idle" | "starting" | "running" | "error">("idle");
  const [proxyUrl, setProxyUrl] = useState<string | null>(null);
  const [kind, setKind] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  if (!activeSession) return null;

  async function start() {
    if (!activeSession) return;
    setStatus("starting");
    setErrorMessage(null);
    try {
      const { proxyPath, kind: appKind } = await api.preview.start(activeSession.id);
      setProxyUrl(`${API_BASE_URL}${proxyPath}`);
      setKind(appKind);
      setStatus("running");
    } catch (e: any) {
      setStatus("error");
      setErrorMessage(e instanceof ApiError ? e.message : e?.message ?? "Failed to start the preview");
    }
  }

  async function stop() {
    if (!activeSession) return;
    try {
      await api.preview.stop(activeSession.id);
    } catch {
      // Stopping is best-effort from the UI's perspective -- the backend's
      // idle reaper will clean it up regardless.
    }
    setStatus("idle");
    setProxyUrl(null);
    setKind(null);
  }

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-3 border-b border-[var(--nexus-border)]/60 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-[var(--foreground)]">Live Preview</h3>
          <p className="text-[11px] text-[var(--muted-foreground)]">
            {kind ? `Running as ${kind}` : "Runs the generated app for real"}
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          {status === "running" && proxyUrl && (
            <button
              onClick={() => setReloadKey((k) => k + 1)}
              className="p-1.5 rounded-md text-[var(--muted-foreground)] hover:text-white hover:bg-[var(--nexus-surface-2)] transition"
              title="Reload"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          )}
          {status === "running" && proxyUrl && (
            <button
              onClick={() => window.open(proxyUrl, "_blank")}
              className="p-1.5 rounded-md text-[var(--muted-foreground)] hover:text-white hover:bg-[var(--nexus-surface-2)] transition"
              title="Open in new tab"
            >
              <ExternalLink className="w-3.5 h-3.5" />
            </button>
          )}
          <button
            onClick={status === "running" ? stop : start}
            disabled={status === "starting"}
            className={cn(
              "flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition disabled:opacity-50",
              status === "running"
                ? "bg-[color-mix(in_srgb,var(--nexus-error)_20%,transparent)] text-[var(--nexus-error)] hover:bg-[color-mix(in_srgb,var(--nexus-error)_30%,transparent)]"
                : "bg-[var(--nexus-purple)] text-white hover:opacity-90"
            )}
          >
            {status === "starting" ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : status === "running" ? (
              <Square className="w-3.5 h-3.5" />
            ) : (
              <Play className="w-3.5 h-3.5" />
            )}
            {status === "running" ? "Stop" : status === "starting" ? "Starting…" : "Start"}
          </button>
        </div>
      </div>

      <div className="flex-1 min-h-0">
        {status === "idle" && (
          <div className="h-full flex items-center justify-center px-6 text-center text-xs text-[var(--muted-foreground)]">
            Click Start to run the app the agent built, in a real container.
          </div>
        )}
        {status === "starting" && (
          <div className="h-full flex items-center justify-center gap-2 text-xs text-[var(--muted-foreground)]">
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            Starting the preview container…
          </div>
        )}
        {status === "error" && (
          <div className="h-full flex flex-col items-center justify-center gap-2 px-6 text-center">
            <AlertTriangle className="w-5 h-5 text-[var(--nexus-amber)]" />
            <p className="text-xs text-[var(--foreground)] max-w-sm">{errorMessage}</p>
          </div>
        )}
        {status === "running" && proxyUrl && (
          <iframe
            key={reloadKey}
            src={proxyUrl}
            className="w-full h-full border-0 bg-white"
            title="Live preview"
            sandbox="allow-scripts allow-forms allow-same-origin allow-popups"
          />
        )}
      </div>
    </div>
  );
}
