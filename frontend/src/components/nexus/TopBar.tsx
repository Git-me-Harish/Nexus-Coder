"use client";

import { useState, useEffect } from "react";
import { ChevronDown, Check, Zap, Activity, Settings2, Download, GitBranch, PanelRight, X, GraduationCap, KeyRound, Play, FlaskConical } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { useAuthStore } from "@/stores/authStore";
import { MODELS, PHASE_META, getModel, type ModelDef, type Phase } from "@/lib/nexus/constants";
import { api } from "@/lib/nexus/client";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { navigate } from "@/hooks/use-hash-router";
import { MobileSidebarTrigger } from "./ResponsiveSidebar";
import Avatar from "./Avatar";

/** What the backend returns per model: the full catalog entry, with
 * `available` reflecting a real per-tenant credential check (see
 * backend/app/api/v1/routes/models.py) rather than the static `true` baked
 * into the client-side fallback catalog. */
type LiveModel = ModelDef;

export default function TopBar() {
  const {
    activeSession, activeProject, setShowSpecModal, setShowModelSwitcher,
    setRightPanel, rightPanel, updateActiveSession, isStreaming,
    streamingModelId, streamingTokensUsed, streamingTokensBudget,
    setMobileRightPanelOpen, mobileRightPanelOpen,
  } = useAppStore();
  const { user } = useAuthStore();

  const [modelOpen, setModelOpen] = useState(false);
  const [liveModels, setLiveModels] = useState<LiveModel[]>([]);

  useEffect(() => {
    if (!modelOpen) return;
    api.models.list()
      .then((d) => setLiveModels(d.models ?? []))
      .catch(() => {}); // keep prior state -- switcher still usable, just possibly stale
  }, [modelOpen]);

  /** The backend's catalog is authoritative; the static import is only a
   *  first-paint fallback. Rendering the static list was how ids the backend
   *  no longer serves stayed selectable in the switcher. */
  const switchableModels: ModelDef[] = liveModels.length > 0 ? liveModels : MODELS;

  function isModelLive(modelId: string): boolean {
    const live = liveModels.find((m) => m.id === modelId);
    // Before the first fetch resolves, don't falsely mark everything dead.
    return live ? live.available : true;
  }

  function providerLabelFor(modelId: string): string {
    const model = switchableModels.find((m) => m.id === modelId) ?? getModel(modelId);
    if (!model) return "";
    if (model.provider === "nexus") return "auto-routes to a configured provider";
    return isModelLive(modelId) ? "configured · ready" : "no API key configured";
  }

  if (!activeSession) return null;

  const phase = activeSession.currentPhase as Phase;
  const phaseMeta = PHASE_META[phase];
  const model = getModel(activeSession.baseModelId);
  const pct = Math.min(100, (activeSession.tokensUsed / activeSession.tokensBudget) * 100);
  const streamPct = isStreaming && streamingTokensBudget > 0
    ? Math.min(100, (streamingTokensUsed / streamingTokensBudget) * 100)
    : 0;

  async function switchModel(modelId: string) {
    if (!activeSession) return;
    try {
      const { session } = await api.sessions.switchModel(activeSession.id, modelId);
      updateActiveSession({ baseModelId: modelId });
      setModelOpen(false);
      toast.success(`Switched to ${getModel(modelId)?.displayName ?? modelId}`);
    } catch (err) {
      toast.error("Model switch failed");
    }
  }

  function toggleRightPanel(p: NonNullable<ReturnType<typeof useAppStore.getState>["rightPanel"]>) {
    const next = rightPanel === p ? null : p;
    setRightPanel(next);
    // On mobile, open the slide-over when a panel is selected
    if (typeof window !== "undefined" && window.innerWidth < 1024) {
      setMobileRightPanelOpen(next !== null);
    }
  }

  return (
    <header className="sticky top-0 z-30 h-14 bg-[var(--nexus-bg)]/80 backdrop-blur-xl border-b border-[var(--nexus-border)] flex items-center gap-2 sm:gap-3 px-3 sm:px-4">
      {/* Mobile hamburger */}
      <MobileSidebarTrigger />

      {/* Breadcrumb — truncated on mobile */}
      <div className="flex items-center gap-2 text-sm min-w-0 flex-1 sm:flex-initial">
        <span className="text-[var(--muted-foreground)] truncate max-w-[100px] sm:max-w-[180px]">{activeProject?.name}</span>
        <span className="hidden sm:inline text-[var(--muted-foreground)]">/</span>
        <span className="text-[var(--foreground)] font-medium truncate max-w-[120px] sm:max-w-[180px]">
          {activeSession.title ?? activeSession.id.slice(0, 8)}
        </span>
      </div>

      <div className="hidden md:block h-5 w-px bg-[var(--nexus-border)]" />

      {/* Phase pill — hidden on mobile (PhaseStepper below shows it) */}
      {phaseMeta && (
        <div className="hidden md:flex items-center gap-1.5">
          <span className="phase-pill phase-pill-active">
            <span className="w-1.5 h-1.5 rounded-full bg-current" />
            {phaseMeta.label}
          </span>
          <span className="hidden lg:inline text-xs text-[var(--muted-foreground)]">{phaseMeta.tagline}</span>
        </div>
      )}

      <div className="flex-1 hidden md:block" />

      {/* Token meter — compact on mobile */}
      <div className="hidden sm:flex items-center gap-2 text-xs">
        <Zap className={cn("w-3.5 h-3.5", pct >= 80 ? "text-[var(--nexus-amber)]" : "text-[var(--muted-foreground)]")} />
        <div className="w-20 lg:w-28 h-1.5 rounded-full bg-[var(--nexus-surface-2)] overflow-hidden">
          <div
            className={cn(
              "h-full transition-all duration-500",
              pct >= 95 ? "bg-[var(--nexus-error)]" : pct >= 80 ? "bg-[var(--nexus-amber)]" : "bg-gradient-to-r from-[var(--nexus-purple)] to-[var(--nexus-violet)]"
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="text-[var(--muted-foreground)] tabular-nums hidden lg:inline">
          {(activeSession.tokensUsed / 1000).toFixed(1)}k / {(activeSession.tokensBudget / 1000).toFixed(0)}k
        </span>
      </div>

      {/* Streaming indicator */}
      {isStreaming && (
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-[color-mix(in_srgb,var(--nexus-purple)_15%,transparent)] border border-[color-mix(in_srgb,var(--nexus-purple)_30%,transparent)] text-[var(--mode-dev-text)] text-xs">
          <Activity className="w-3 h-3 nexus-pulse" />
          <span className="hidden sm:inline">{streamingModelId ?? "streaming"}</span>
        </div>
      )}

      {/* Right panel toggles — compact on mobile */}
      {activeSession.mode === "development" && (
        <>
          <button
            onClick={() => toggleRightPanel("spec")}
            className={cn(
              "px-2 sm:px-2.5 py-1.5 rounded-md text-xs border transition flex items-center gap-1.5",
              rightPanel === "spec"
                ? "bg-[color-mix(in_srgb,var(--nexus-purple)_15%,transparent)] border-[color-mix(in_srgb,var(--nexus-purple)_40%,transparent)] text-[var(--mode-dev-text)]"
                : "border-[var(--nexus-border)] text-[var(--muted-foreground)] hover:bg-[var(--nexus-surface-2)] hover:text-[var(--foreground)]"
            )}
          >
            <Settings2 className="w-3.5 h-3.5" />
            <span className="hidden lg:inline">Spec</span>
          </button>
          <button
            onClick={() => toggleRightPanel("files")}
            className={cn(
              "px-2 sm:px-2.5 py-1.5 rounded-md text-xs border transition flex items-center gap-1.5",
              rightPanel === "files"
                ? "bg-[color-mix(in_srgb,var(--nexus-purple)_15%,transparent)] border-[color-mix(in_srgb,var(--nexus-purple)_40%,transparent)] text-[var(--mode-dev-text)]"
                : "border-[var(--nexus-border)] text-[var(--muted-foreground)] hover:bg-[var(--nexus-surface-2)] hover:text-[var(--foreground)]"
            )}
          >
            <GitBranch className="w-3.5 h-3.5" />
            <span className="hidden lg:inline">Files</span>
          </button>
          <button
            onClick={() => toggleRightPanel("tests")}
            className={cn(
              "px-2 sm:px-2.5 py-1.5 rounded-md text-xs border transition flex items-center gap-1.5",
              rightPanel === "tests"
                ? "bg-[color-mix(in_srgb,var(--nexus-purple)_15%,transparent)] border-[color-mix(in_srgb,var(--nexus-purple)_40%,transparent)] text-[var(--mode-dev-text)]"
                : "border-[var(--nexus-border)] text-[var(--muted-foreground)] hover:bg-[var(--nexus-surface-2)] hover:text-[var(--foreground)]"
            )}
          >
            <FlaskConical className="w-3.5 h-3.5" />
            <span className="hidden lg:inline">Tests</span>
          </button>
          <button
            onClick={() => toggleRightPanel("preview")}
            className={cn(
              "px-2 sm:px-2.5 py-1.5 rounded-md text-xs border transition flex items-center gap-1.5",
              rightPanel === "preview"
                ? "bg-[color-mix(in_srgb,var(--nexus-purple)_15%,transparent)] border-[color-mix(in_srgb,var(--nexus-purple)_40%,transparent)] text-[var(--mode-dev-text)]"
                : "border-[var(--nexus-border)] text-[var(--muted-foreground)] hover:bg-[var(--nexus-surface-2)] hover:text-[var(--foreground)]"
            )}
          >
            <Play className="w-3.5 h-3.5" />
            <span className="hidden lg:inline">Preview</span>
          </button>
        </>
      )}
      {activeSession.mode === "learning" && (
        <button
          onClick={() => toggleRightPanel("learning")}
          className={cn(
            "px-2 sm:px-2.5 py-1.5 rounded-md text-xs border transition flex items-center gap-1.5",
            rightPanel === "learning"
              ? "bg-[color-mix(in_srgb,var(--nexus-teal)_15%,transparent)] border-[color-mix(in_srgb,var(--nexus-teal)_40%,transparent)] text-[var(--mode-learning-text)]"
              : "border-[var(--nexus-border)] text-[var(--muted-foreground)] hover:bg-[var(--nexus-surface-2)] hover:text-[var(--foreground)]"
          )}
        >
          <GraduationCap className="w-3.5 h-3.5" />
          <span className="hidden lg:inline">Topics</span>
        </button>
      )}
      <button
        onClick={() => toggleRightPanel("usage")}
        className={cn(
          "px-2 sm:px-2.5 py-1.5 rounded-md text-xs border transition flex items-center gap-1.5",
          rightPanel === "usage"
            ? "bg-[color-mix(in_srgb,var(--nexus-purple)_15%,transparent)] border-[color-mix(in_srgb,var(--nexus-purple)_40%,transparent)] text-[var(--mode-dev-text)]"
            : "border-[var(--nexus-border)] text-[var(--muted-foreground)] hover:bg-[var(--nexus-surface-2)] hover:text-[var(--foreground)]"
        )}
      >
        <Download className="w-3.5 h-3.5" />
        <span className="hidden lg:inline">Usage</span>
      </button>

      {/* Model selector */}
      <div className="relative shrink-0">
        <button
          onClick={() => setModelOpen(!modelOpen)}
          className="flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-1.5 rounded-md bg-[var(--nexus-surface-2)] border border-[var(--nexus-border)] hover:border-[color-mix(in_srgb,var(--nexus-purple)_40%,transparent)] transition text-sm"
        >
          <span className="w-2 h-2 rounded-full bg-gradient-to-br from-[var(--nexus-violet)] to-[var(--nexus-purple)]" />
          <span className="text-[var(--foreground)] font-medium hidden sm:inline">{model?.displayName ?? activeSession.baseModelId}</span>
          <span className="text-[var(--foreground)] font-medium sm:hidden">Model</span>
          <ChevronDown className="w-3.5 h-3.5 text-[var(--muted-foreground)]" />
        </button>
        {modelOpen && (
          <>
            <div className="fixed inset-0 z-30" onClick={() => setModelOpen(false)} />
            <div className="absolute right-0 top-full z-40 mt-1 flex max-h-[80vh] w-72 flex-col overflow-hidden rounded-xl border border-[var(--nexus-border)] bg-[var(--nexus-surface)] shadow-2xl sm:w-80">
              <div className="px-3 py-2 border-b border-[var(--nexus-border)] text-[10px] font-semibold uppercase tracking-wider text-[var(--muted-foreground)] shrink-0">
                Switch Model
              </div>
              <div className="overflow-y-auto py-1">
                {switchableModels.map((m) => {
                  const live = isModelLive(m.id);
                  return (
                    <button
                      key={m.id}
                      onClick={() => switchModel(m.id)}
                      className={cn(
                        "w-full text-left px-3 py-2.5 hover:bg-[var(--nexus-surface-2)] transition flex items-start gap-2",
                        m.id === activeSession.baseModelId && "bg-[color-mix(in_srgb,var(--nexus-purple)_10%,transparent)]"
                      )}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className={cn(
                            "w-1.5 h-1.5 rounded-full shrink-0",
                            live ? "bg-[var(--nexus-success)]" : "bg-[var(--nexus-amber)]"
                          )} title={live ? "Provider configured" : "Fallback to ZAI"} />
                          <span className="text-sm font-medium text-[var(--foreground)]">{m.displayName}</span>
                          <span className={cn(
                            "px-1.5 py-0.5 rounded text-[9px] font-medium uppercase",
                            m.capabilityTier === "powerful" ? "bg-[color-mix(in_srgb,var(--nexus-amber)_20%,transparent)] text-[var(--mode-problem-text)]" :
                            m.capabilityTier === "balanced" ? "bg-[color-mix(in_srgb,var(--nexus-purple)_20%,transparent)] text-[var(--mode-dev-text)]" :
                            "bg-[color-mix(in_srgb,var(--nexus-success)_20%,transparent)] text-[var(--mode-learning-text)]"
                          )}>
                            {m.capabilityTier}
                          </span>
                        </div>
                        <div className="text-xs text-[var(--muted-foreground)] line-clamp-2">{m.description}</div>
                        <div className="text-[10px] text-[var(--muted-foreground)] mt-0.5 flex items-center gap-1.5">
                          <span>{m.provider} · {(m.contextWindow / 1000).toFixed(0)}k ctx · ${m.inputCostPer1k.toFixed(4)}/1k in</span>
                          <span className="opacity-50">·</span>
                          <span className={live ? "text-[var(--mode-learning-text)]" : "text-[var(--mode-problem-text)]"}>
                            {providerLabelFor(m.id)}
                          </span>
                        </div>
                      </div>
                      {m.id === activeSession.baseModelId && (
                        <Check className="w-4 h-4 text-[var(--nexus-purple)] mt-0.5 shrink-0" />
                      )}
                    </button>
                  );
                })}
              </div>
              <button
                onClick={() => { setModelOpen(false); navigate("profile"); }}
                className="flex shrink-0 items-center gap-2 border-t border-[var(--nexus-border)] px-3 py-2.5 text-xs text-[var(--muted-foreground)] transition hover:bg-[var(--nexus-surface-2)] hover:text-[var(--foreground)]"
              >
                <KeyRound className="h-3.5 w-3.5" />
                Configure Models — manage your provider API keys
              </button>
            </div>
          </>
        )}
      </div>

      {/* Profile — theme, API keys, GitHub connection all live on the
          profile page now, not in a popup here. */}
      <button
        onClick={() => navigate("profile")}
        className="shrink-0 rounded-full transition hover:opacity-90"
        title="Profile & settings"
        aria-label="Profile & settings"
      >
        <Avatar src={user?.avatarUrl} name={user?.name ?? user?.email} className="h-7 w-7" textClassName="text-[10px]" />
      </button>
    </header>
  );
}