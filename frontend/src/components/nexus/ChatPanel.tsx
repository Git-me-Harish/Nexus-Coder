"use client";

import { useEffect, useRef, useState } from "react";
import { Send, User, Sparkles, AlertCircle, Loader2, Brain, Check } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import type { AgentStage, Critique, ToolActivity, Session, SessionFile } from "@/stores/appStore";
import { useAuthStore } from "@/stores/authStore";
import { navigate } from "@/hooks/use-hash-router";
import { api, handleUnauthorized, tryRefresh } from "@/lib/nexus/client";
import MarkdownRenderer from "./MarkdownRenderer";
import QuizInterface from "./QuizInterface";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

/** Heuristic — does the assistant output look like a quiz? */
function looksLikeQuiz(text: string): boolean {
  return /\*\*Q\d/i.test(text) && /Answer Key/i.test(text);
}

/** What the agent is doing right now, for the pre-output spinner. The agent
 *  plans and self-reviews around the answer, so "thinking" is no longer a
 *  euphemism for "waiting" — see backend app/agents/graph.py. */
function stageLabel(stage: AgentStage | null, worker: string | null): string {
  switch (stage) {
    case "planning": return "Planning the approach…";
    case "answering": return `Working — ${worker} worker…`;
    case "reviewing": return "Reviewing its own output…";
    case "revising": return "Revising after review…";
    default: return `Initializing ${worker} worker…`;
  }
}

/** What the agent actually DID this turn: files written, commands run, and
 *  whether each one really succeeded. These are live executions, not a
 *  narration of intent -- an "error" row means a command genuinely exited
 *  non-zero or a path was genuinely rejected. */
function ToolTrace({ tools }: { tools: ToolActivity[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <div className="ml-10 space-y-1">
      {tools.map((t) => {
        const hasDetail = Boolean(t.preview);
        return (
          <div key={t.id} className="rounded-md border border-[var(--nexus-border)] bg-[var(--nexus-surface)]/40 text-xs">
            <button
              disabled={!hasDetail}
              onClick={() => setExpanded(expanded === t.id ? null : t.id)}
              className={cn(
                "flex w-full items-center gap-2 px-2.5 py-1.5 text-left",
                hasDetail && "hover:bg-[var(--nexus-surface-2)] transition"
              )}
            >
              {t.status === "running" ? (
                <Loader2 className="w-3 h-3 shrink-0 animate-spin text-[var(--nexus-purple)]" />
              ) : t.status === "ok" ? (
                <Check className="w-3 h-3 shrink-0 text-[var(--nexus-success)]" />
              ) : (
                <AlertCircle className="w-3 h-3 shrink-0 text-[var(--nexus-error)]" />
              )}
              <code className="truncate font-mono text-[11px] text-[var(--foreground)]">{t.summary}</code>
              {hasDetail && (
                <span className="ml-auto shrink-0 text-[10px] text-[var(--muted-foreground)]">
                  {expanded === t.id ? "hide" : "output"}
                </span>
              )}
            </button>
            {expanded === t.id && t.preview && (
              <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-words border-t border-[var(--nexus-border)] px-2.5 py-1.5 font-mono text-[10px] leading-relaxed text-[var(--muted-foreground)]">
                {t.preview}
              </pre>
            )}
          </div>
        );
      })}
    </div>
  );
}

/**
 * Confirmation gates for the artifact-producing phases, and the one-time
 * build-depth picker for Implementation. Mirrors the existing Specification
 * confirm flow (SpecBuilder.tsx) but for the two workspace-file artifacts
 * (IDEA.md / PLAN.md) the agent writes with write_file rather than a
 * dedicated DB row -- see backend/app/services/session_service.py
 * confirm_idea/confirm_plan.
 */
function PhaseArtifactGate({
  session, files, confirming, onConfirmIdea, onConfirmPlan, onSetBuildDepth,
}: {
  session: Session;
  files: SessionFile[];
  confirming: boolean;
  onConfirmIdea: () => void;
  onConfirmPlan: () => void;
  onSetBuildDepth: (depth: "prototype" | "mvp" | "production") => void;
}) {
  if (session.mode !== "development") return null;
  const hasFile = (name: string) => files.some((f) => f.filePath === name);

  if (session.currentPhase === "ideation" && hasFile("IDEA.md") && !session.ideaConfirmedAt) {
    return (
      <div className="mx-3 sm:mx-6 mb-2 flex items-center justify-between gap-3 rounded-lg border border-[var(--nexus-purple)]/40 bg-[color-mix(in_srgb,var(--nexus-purple)_10%,transparent)] px-3 py-2 text-xs">
        <span className="text-[var(--foreground)]">
          <strong>IDEA.md</strong> is ready — review it in the Files panel, then confirm to unlock Planning.
        </span>
        <button
          onClick={onConfirmIdea}
          disabled={confirming}
          className="shrink-0 rounded-md bg-[var(--nexus-purple)] px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-50"
        >
          Confirm this direction
        </button>
      </div>
    );
  }

  if (session.currentPhase === "planning" && hasFile("PLAN.md") && !session.planConfirmedAt) {
    return (
      <div className="mx-3 sm:mx-6 mb-2 flex items-center justify-between gap-3 rounded-lg border border-[var(--nexus-purple)]/40 bg-[color-mix(in_srgb,var(--nexus-purple)_10%,transparent)] px-3 py-2 text-xs">
        <span className="text-[var(--foreground)]">
          <strong>PLAN.md</strong> is ready — review it in the Files panel, then confirm to unlock Specification.
        </span>
        <button
          onClick={onConfirmPlan}
          disabled={confirming}
          className="shrink-0 rounded-md bg-[var(--nexus-purple)] px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-50"
        >
          Confirm this plan
        </button>
      </div>
    );
  }

  if (session.currentPhase === "implementation" && !session.buildDepth) {
    const options: Array<{ value: "prototype" | "mvp" | "production"; label: string; hint: string }> = [
      { value: "prototype", label: "Prototype / demo", hint: "Fastest — core flow only, polish skipped" },
      { value: "mvp", label: "Functional MVP", hint: "Primary flows work for real, basic validation" },
      { value: "production", label: "Production-grade", hint: "Full validation, error handling, tests" },
    ];
    return (
      <div className="mx-3 sm:mx-6 mb-2 rounded-lg border border-[var(--nexus-purple)]/40 bg-[color-mix(in_srgb,var(--nexus-purple)_10%,transparent)] px-3 py-2.5 text-xs">
        <div className="mb-2 font-medium text-[var(--foreground)]">
          Before I start building — how should I approach this?
        </div>
        <div className="flex flex-col sm:flex-row gap-2">
          {options.map((opt) => (
            <button
              key={opt.value}
              onClick={() => onSetBuildDepth(opt.value)}
              className="flex-1 rounded-md border border-[var(--nexus-border)] bg-[var(--nexus-surface)] px-3 py-2 text-left transition hover:border-[var(--nexus-purple)] hover:bg-[var(--nexus-surface-2)]"
            >
              <div className="font-medium text-[var(--foreground)]">{opt.label}</div>
              <div className="text-[10px] text-[var(--muted-foreground)]">{opt.hint}</div>
            </button>
          ))}
        </div>
      </div>
    );
  }

  return null;
}

/** The agent's plan and self-review, shown above the answer it produced.
 *  Collapsed by default: it is useful when you want to know why the agent did
 *  what it did, and noise the rest of the time. */
function ReasoningTrace({
  stage, reasoning, critique,
}: {
  stage: AgentStage | null;
  reasoning: string;
  critique: Critique | null;
}) {
  const [open, setOpen] = useState(false);
  const rejected = critique && !critique.approved;

  return (
    <div className="ml-10 rounded-lg border border-[var(--nexus-border)] bg-[var(--nexus-surface)]/50 text-xs">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition"
      >
        <Brain className="w-3.5 h-3.5 shrink-0" />
        <span className="font-medium">
          {stage === "planning" ? "Planning…" : "Reasoning"}
        </span>
        {critique?.revising && (
          <span className="rounded bg-[color-mix(in_srgb,var(--nexus-error)_18%,transparent)] px-1.5 py-0.5 text-[10px] text-[var(--nexus-error)]">
            revising
          </span>
        )}
        {critique && !critique.revising && (
          <span
            className={cn(
              "rounded px-1.5 py-0.5 text-[10px]",
              rejected
                ? "bg-[color-mix(in_srgb,var(--nexus-error)_18%,transparent)] text-[var(--nexus-error)]"
                : "bg-[color-mix(in_srgb,var(--nexus-purple)_18%,transparent)] text-[var(--nexus-purple)]"
            )}
          >
            {rejected ? "revised" : "reviewed"}
          </span>
        )}
        <span className="ml-auto text-[10px]">{open ? "hide" : "show"}</span>
      </button>

      {open && (
        <div className="space-y-2 border-t border-[var(--nexus-border)] px-3 py-2">
          {reasoning && (
            <pre className="whitespace-pre-wrap break-words font-mono text-[11px] leading-relaxed text-[var(--muted-foreground)]">
              {reasoning}
            </pre>
          )}
          {critique && (
            <div className="text-[11px] text-[var(--muted-foreground)]">
              <span className="font-medium text-[var(--foreground)]">Self-review: </span>
              {critique.reason || (critique.approved ? "Approved." : "Rejected.")}
              {critique.issues.length > 0 && (
                <ul className="mt-1 list-disc pl-4">
                  {critique.issues.map((issue, i) => <li key={i}>{issue}</li>)}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ChatPanel() {
  const {
    activeSession, messages, appendMessage, setMessages,
    isStreaming, streamingText, streamingPhase, streamingWorker,
    streamingModel, streamingTokensUsed, streamingTokensBudget,
    streamingStage, streamingReasoning, streamingCritique, streamingTools,
    startStream, appendToken, finishStream, failStream, resetStream,
    appendReasoning, setStreamingStage, setStreamingCritique, clearStreamScope,
    startToolActivity, finishToolActivity,
    setFiles, updateActiveSession,
    files,
  } = useAppStore();

  const [input, setInput] = useState("");
  const [confirmingArtifact, setConfirmingArtifact] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streamingText]);

  // Listen for Learning mode stage-trigger events (from LearningPanel)
  useEffect(() => {
    const handler = async (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (!activeSession || detail?.sessionId !== activeSession.id) return;
      if (isStreaming) return;
      // Reload messages to pick up the just-sent user message, then stream
      try {
        const { messages: fresh } = await api.messages.list(activeSession.id);
        setMessages(fresh);
      } catch {}
      streamAgent("");  // empty string = use the last user message already in DB
    };
    window.addEventListener("nexus:trigger-stream", handler);
    return () => window.removeEventListener("nexus:trigger-stream", handler);
  }, [activeSession?.id, isStreaming]);

  if (!activeSession) {
    return (
      <div className="flex flex-1 items-center justify-center px-6 py-10">
        <div className="flex w-full max-w-xl flex-col items-center text-center">
          <img
            src="/select_chat.png"
            alt="Illustration prompting you to select or create a chat session"
            className="mb-5 w-full max-w-md object-contain"
          />
          <p className="text-sm font-medium text-[var(--muted-foreground)]">
            Select or create a session to start.
          </p>
        </div>
      </div>
    );
  }

  const needsBuildDepth =
    activeSession.mode === "development" &&
    activeSession.currentPhase === "implementation" &&
    !activeSession.buildDepth;

  async function send() {
    if (!input.trim() || !activeSession) return;
    const content = input.trim();
    setInput("");

    // Optimistic user message
    appendMessage({
      id: `tmp-${Date.now()}`,
      role: "user",
      content,
      phase: activeSession.currentPhase,
      createdAt: new Date().toISOString(),
    });

    await streamAgent(content);
  }

  async function confirmIdea() {
    if (!activeSession) return;
    setConfirmingArtifact(true);
    try {
      const { session } = await api.sessions.confirmIdea(activeSession.id);
      updateActiveSession({ ideaConfirmedAt: session.ideaConfirmedAt });
      toast.success("Idea confirmed — Planning can begin.");
    } catch (e: any) {
      toast.error(e?.message ?? "Failed to confirm the idea");
    } finally {
      setConfirmingArtifact(false);
    }
  }

  async function confirmPlan() {
    if (!activeSession) return;
    setConfirmingArtifact(true);
    try {
      const { session } = await api.sessions.confirmPlan(activeSession.id);
      updateActiveSession({ planConfirmedAt: session.planConfirmedAt });
      toast.success("Plan confirmed — Specification can begin.");
    } catch (e: any) {
      toast.error(e?.message ?? "Failed to confirm the plan");
    } finally {
      setConfirmingArtifact(false);
    }
  }

  async function setBuildDepth(depth: "prototype" | "mvp" | "production") {
    if (!activeSession) return;
    try {
      const { session } = await api.sessions.update(activeSession.id, { buildDepth: depth });
      updateActiveSession({ buildDepth: session.buildDepth });
    } catch (e: any) {
      toast.error(e?.message ?? "Failed to set build depth");
    }
  }

  async function fetchStream(userMessage: string, _retried = false): Promise<Response> {
    const res = await fetch(api.streamUrl(activeSession!.id), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${useAuthStore.getState().token ?? ""}`,
      },
      body: JSON.stringify({ userMessage }),
      signal: abortRef.current!.signal,
    });

    if (res.status === 401 && !_retried) {
      const refreshed = await tryRefresh();
      if (refreshed) return fetchStream(userMessage, true);
      handleUnauthorized();
    }
    return res;
  }

  async function streamAgent(userMessage: string) {
    if (!activeSession) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetchStream(userMessage);

      if (!res.ok || !res.body) {
        throw new Error(`HTTP ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let started = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";

        for (const evt of events) {
          const lines = evt.split("\n");
          const id = lines.find((l) => l.startsWith("id:"))?.slice(3).trim();
          const event = lines.find((l) => l.startsWith("event:"))?.slice(6).trim() ?? "message";
          const dataRaw = lines.find((l) => l.startsWith("data:"))?.slice(5).trim();
          if (!dataRaw) continue;
          let data: any;
          try { data = JSON.parse(dataRaw); } catch { continue; }

          if (event === "phase" && !started) {
            started = true;
            startStream(
              data.model_id,
              data.model_name,
              data.phase,
              data.worker,
              data.tokens_used,
              data.tokens_budget
            );
          } else if (event === "token") {
            appendToken(data.content);
          } else if (event === "stage") {
            setStreamingStage(data.stage);
          } else if (event === "reasoning") {
            appendReasoning(data.content);
          } else if (event === "stream_reset") {
            // The text streamed so far for this scope is being abandoned --
            // a provider died mid-answer and we fell back, or a rejected
            // draft is about to be replaced. Clear it so the replacement
            // renders on its own rather than appended to the dead text.
            clearStreamScope(data.scope === "reasoning" ? "reasoning" : "token");
          } else if (event === "tool_call") {
            // A real action is starting: a file write, or a command in the
            // sandbox. Shown before the outcome is known so the user can see
            // what the agent is doing while it does it.
            startToolActivity({
              id: data.id,
              name: data.name,
              summary: data.summary,
              step: data.step,
            });
          } else if (event === "tool_result") {
            finishToolActivity(data.id, data.ok, data.preview);
          } else if (event === "critique") {
            setStreamingCritique({
              approved: data.approved,
              issues: data.issues ?? [],
              phaseComplete: data.phase_complete,
              reason: data.reason ?? "",
              revising: data.revising ?? false,
            });
          } else if (event === "phase_advanced") {
            toast.success(`${data.from} complete — moving to ${data.to}`, {
              description: data.reason || undefined,
            });
          } else if (event === "provider_fallback") {
            toast.warning(`Falling back to ${data.fallback_provider} (${data.fallback_model}) — ${data.reason?.split(".")[0]}`, {
              duration: 6000,
            });
          } else if (event === "file_written") {
            // Refresh files
            try {
              const { files } = await api.files.list(activeSession.id);
              setFiles(files);
            } catch {}
          } else if (event === "token_warning") {
            toast.warning(`Token budget: ${data.percent_used}% used`);
          } else if (event === "task_complete") {
            updateActiveSession({
              tokensUsed: data.tokens_total,
            });
          } else if (event === "error") {
            failStream(data.message ?? "Agent failed");
            if (data.code === "PROVIDER_NOT_CONFIGURED") {
              toast.error(data.message ?? "No API key configured for this model.", {
                duration: 10000,
                action: {
                  label: "Configure Models",
                  onClick: () => navigate("profile"),
                },
              });
            } else {
              toast.error(data.message ?? "Agent failed");
            }
            resetStream();
            return;
          } else if (event === "end") {
            finishStream();
            // Refresh session to capture server-side updates
            try {
              const { session } = await api.sessions.get(activeSession.id);
              updateActiveSession({
                currentPhase: session.currentPhase,
                tokensUsed: session.tokensUsed,
                tokensBudget: session.tokensBudget,
              });
            } catch {}
          }
        }
      }
    } catch (err: any) {
      if (err.name !== "AbortError") {
        failStream(err?.message ?? "Stream failed");
        toast.error(err?.message ?? "Stream failed");
        resetStream();
      }
    }
  }

  function stop() {
    abortRef.current?.abort();
    if (streamingText) {
      finishStream();
    } else {
      resetStream();
    }
  }

  return (
    <div className="flex-1 flex flex-col min-w-0">
      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 sm:px-6 py-4 sm:py-6 space-y-4 sm:space-y-5">
        {messages.length === 0 && !isStreaming && (
          <EmptyState mode={activeSession.mode} />
        )}

        {messages.map((m) => (
          <MessageBubble key={m.id} role={m.role} content={m.content} phase={m.phase} modelId={m.modelId} />
        ))}

        {isStreaming && (streamingReasoning || streamingCritique) && (
          <ReasoningTrace
            stage={streamingStage}
            reasoning={streamingReasoning}
            critique={streamingCritique}
          />
        )}

        {isStreaming && streamingTools.length > 0 && (
          <ToolTrace tools={streamingTools} />
        )}

        {isStreaming && (
          <MessageBubble
            role="assistant"
            content={streamingText || "…"}
            phase={streamingPhase}
            modelId={streamingModel}
            streaming
            worker={streamingWorker}
            tokensUsed={streamingTokensUsed}
            tokensBudget={streamingTokensBudget}
          />
        )}

        {isStreaming && !streamingText && (
          <div className="flex items-center gap-2 text-xs text-[var(--muted-foreground)] ml-10">
            <Loader2 className="w-3 h-3 animate-spin" />
            {stageLabel(streamingStage, streamingWorker)}
          </div>
        )}
      </div>

      {/* Confirmation gates: IDEA.md/PLAN.md confirm, and the one-time
          build-depth picker that blocks the input below until answered. */}
      <PhaseArtifactGate
        session={activeSession}
        files={files}
        confirming={confirmingArtifact}
        onConfirmIdea={confirmIdea}
        onConfirmPlan={confirmPlan}
        onSetBuildDepth={setBuildDepth}
      />

      {/* Input */}
      <div className="px-3 sm:px-6 pb-3 sm:pb-4 pt-2 border-t border-[var(--nexus-border)] bg-[var(--nexus-bg)]/40 safe-bottom">
        <div className="relative">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (!isStreaming && !needsBuildDepth) send();
              }
            }}
            placeholder={
              needsBuildDepth
                ? "Pick a build depth above before we start…"
                : inputPlaceholder(activeSession.mode, activeSession.currentPhase)
            }
            rows={3}
            className="w-full px-3 sm:px-4 py-2.5 sm:py-3 pr-12 sm:pr-14 rounded-xl bg-[var(--nexus-surface)] border border-[var(--nexus-border)] focus:border-[color-mix(in_srgb,var(--nexus-purple)_50%,transparent)] focus:ring-2 focus:ring-[color-mix(in_srgb,var(--nexus-purple)_20%,transparent)] text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] resize-none transition disabled:opacity-60"
            disabled={isStreaming || needsBuildDepth}
          />
          <button
            onClick={isStreaming ? stop : send}
            disabled={!isStreaming && (!input.trim() || needsBuildDepth)}
            className={cn(
              "absolute right-2.5 sm:right-3 bottom-2.5 sm:bottom-3 w-8 h-8 sm:w-9 sm:h-9 rounded-lg flex items-center justify-center transition",
              isStreaming
                ? "bg-[color-mix(in_srgb,var(--nexus-error)_20%,transparent)] text-[var(--nexus-error)] hover:bg-[color-mix(in_srgb,var(--nexus-error)_30%,transparent)] border border-[color-mix(in_srgb,var(--nexus-error)_40%,transparent)]"
                : "bg-gradient-to-br from-[var(--nexus-purple)] to-[var(--nexus-purple-dim)] text-white disabled:opacity-30 hover:opacity-90 nexus-btn-glow"
            )}
            title={isStreaming ? "Stop" : "Send"}
          >
            {isStreaming ? <span className="text-xs font-bold">■</span> : <Send className="w-4 h-4" />}
          </button>
        </div>
        <div className="mt-1.5 text-[10px] text-[var(--muted-foreground)] flex items-center justify-between px-1">
          <span className="hidden sm:inline">Press Enter to send · Shift+Enter for newline</span>
          <span className="sm:hidden">Enter to send</span>
          <span className="truncate ml-2">Phase: {activeSession.currentPhase}</span>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({
  role, content, phase, modelId, streaming, worker, tokensUsed, tokensBudget,
}: {
  role: string;
  content: string;
  phase?: string | null;
  modelId?: string | null;
  streaming?: boolean;
  worker?: string | null;
  tokensUsed?: number;
  tokensBudget?: number;
}) {
  const isUser = role === "user";
  return (
    <div className={cn("flex gap-2.5 sm:gap-3 nexus-message-in", isUser ? "flex-row-reverse" : "flex-row")}>
      {/* Avatar */}
      <div className={cn(
        "w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5",
        isUser
          ? "bg-[var(--nexus-surface-2)] border border-[var(--nexus-border)]"
          : "bg-gradient-to-br from-[var(--nexus-violet)] to-[var(--nexus-purple)] shadow-[0_0_12px_color-mix(in_srgb,var(--nexus-purple)_40%,transparent)]"
      )}>
        {isUser ? <User className="w-4 h-4 text-[var(--muted-foreground)]" /> : <Sparkles className="w-4 h-4 text-white" />}
      </div>

      {/* Message body */}
      <div className={cn("flex flex-col min-w-0", isUser ? "items-end" : "items-start", "flex-1 sm:flex-initial sm:max-w-[85%] lg:max-w-3xl")}>
        {/* Header row — name + meta */}
        <div className={cn(
          "flex items-center gap-2 mb-1.5 flex-wrap",
          isUser ? "flex-row-reverse" : "flex-row"
        )}>
          <span className="text-xs font-semibold text-[var(--foreground)]">
            {isUser ? "You" : "Nexus"}
          </span>
          {!isUser && worker && (
            <span className="px-1.5 py-0.5 rounded text-[9px] font-medium uppercase tracking-wider bg-[color-mix(in_srgb,var(--nexus-purple)_15%,transparent)] text-[var(--mode-dev-text)] border border-[color-mix(in_srgb,var(--nexus-purple)_25%,transparent)]">
              {worker}
            </span>
          )}
          {!isUser && modelId && (
            <span className="text-[10px] text-[var(--muted-foreground)] hidden sm:inline">{modelId}</span>
          )}
          {phase && (
            <span className="text-[10px] text-[var(--muted-foreground)]">· {phase}</span>
          )}
          {streaming && (
            <span className="text-[10px] text-[var(--nexus-purple)] flex items-center gap-1 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--nexus-purple)] nexus-pulse" />
              streaming
            </span>
          )}
        </div>

        {/* Bubble */}
        <div className={cn(
          "rounded-2xl px-4 py-3 w-full",
          isUser
            ? "bg-[var(--nexus-surface-2)] border border-[var(--nexus-border)] text-sm text-[var(--foreground)] rounded-tr-sm"
            : "bg-[var(--nexus-surface)] border border-[var(--nexus-border)] rounded-tl-sm shadow-sm"
        )}>
          {isUser ? (
            <div className="text-sm whitespace-pre-wrap text-[var(--foreground)] leading-relaxed">{content}</div>
          ) : (
            <MarkdownRenderer content={content} className={cn(streaming && !content && "nexus-caret")} />
          )}
          {/* Inject quiz UI when the assistant output looks like a quiz and we have a topic context */}
          {!isUser && !streaming && phase === "quiz" && looksLikeQuiz(content) && (
            <QuizInterface quizText={content} topicId={useAppStore.getState().activeSession?.learningTopics?.[0]?.id ?? ""} />
          )}
        </div>

        {/* Footer — token usage while streaming */}
        {streaming && tokensBudget != null && tokensBudget > 0 && (
          <div className="mt-1.5 text-[10px] text-[var(--muted-foreground)] flex items-center gap-2">
            <span>{((tokensUsed ?? 0) / 1000).toFixed(1)}k / {(tokensBudget / 1000).toFixed(0)}k tokens</span>
            <span className="w-1 h-1 rounded-full bg-[var(--muted-foreground)] opacity-50" />
            <span>{Math.round(((tokensUsed ?? 0) / tokensBudget) * 100)}% budget</span>
          </div>
        )}
      </div>
    </div>
  );
}

function EmptyState({ mode }: { mode: string }) {
  const tips =
    mode === "development" ? [
      "Describe what you want to build — Nexus will brainstorm first.",
      "Use the Spec panel to lock architectural choices before code.",
      "Files you generate appear in the right panel for live preview.",
    ] : mode === "problem_solving" ? [
      "Pose the question — Nexus will argue multiple sides.",
      "There are no phases here, just continuous debate.",
      "Export the discussion as a decision doc when you're done.",
    ] : [
      "Tell Nexus what you want to learn.",
      "It will Explain, then give you a Practice exercise, then Quiz you.",
      "Your mastery score adapts difficulty over time.",
    ];

  return (
    <div className="max-w-2xl mx-auto text-center pt-8 sm:pt-12">
      <div className="inline-flex w-16 h-16 rounded-2xl bg-gradient-to-br from-[var(--nexus-violet)] to-[var(--nexus-purple)] items-center justify-center mb-4 shadow-[0_0_30px_color-mix(in_srgb,var(--nexus-purple)_40%,transparent)]">
        <Sparkles className="w-7 h-7 text-white" />
      </div>
      <h2 className="text-xl font-semibold text-[var(--foreground)] mb-2">Ready when you are.</h2>
      <p className="text-sm text-[var(--muted-foreground)] mb-6">
        Nexus thinks like a Principal Engineer — it brainstorms, plans, specifies, then builds.
      </p>
      <div className="space-y-1.5 text-left bg-[var(--nexus-surface)]/60 border border-[var(--nexus-border)] rounded-xl p-4">
        {tips.map((t, i) => (
          <div key={i} className="flex items-start gap-2 text-xs text-[var(--muted-foreground)]">
            <span className="w-4 h-4 rounded-full bg-[color-mix(in_srgb,var(--nexus-purple)_20%,transparent)] text-[var(--mode-dev-text)] flex items-center justify-center text-[10px] font-semibold shrink-0 mt-0.5">{i + 1}</span>
            <span>{t}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function inputPlaceholder(mode: string, phase: string): string {
  if (mode === "development") {
    if (phase === "ideation") return "Describe what you want to build…";
    if (phase === "planning") return "Ask Nexus to refine the plan…";
    if (phase === "specification") return "Refine spec dimensions or ask for recommendations…";
    if (phase === "implementation") return "Ask Nexus to write a specific file or fix…";
    if (phase === "debug") return "Paste an error or describe the bug…";
    if (phase === "review") return "Ask for a security / perf audit…";
    return "Continue…";
  }
  if (mode === "problem_solving") return "Pose the question you're wrestling with…";
  return "What do you want to learn?…";
}