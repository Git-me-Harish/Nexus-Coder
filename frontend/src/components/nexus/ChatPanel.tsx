"use client";

import { useEffect, useRef, useState } from "react";
import { Send, User, Sparkles, AlertCircle, Loader2 } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { useAuthStore } from "@/stores/authStore";
import { api, handleUnauthorized, tryRefresh } from "@/lib/nexus/client";
import MarkdownRenderer from "./MarkdownRenderer";
import QuizInterface from "./QuizInterface";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

/** Heuristic — does the assistant output look like a quiz? */
function looksLikeQuiz(text: string): boolean {
  return /\*\*Q\d/i.test(text) && /Answer Key/i.test(text);
}

export default function ChatPanel() {
  const {
    activeSession, messages, appendMessage, setMessages,
    isStreaming, streamingText, streamingPhase, streamingWorker,
    streamingModel, streamingTokensUsed, streamingTokensBudget,
    startStream, appendToken, finishStream, failStream, resetStream,
    setFiles, updateActiveSession, setShowModelConfig,
  } = useAppStore();

  const [input, setInput] = useState("");
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
                  onClick: () => setShowModelConfig(true),
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
            Initializing {streamingWorker} worker…
          </div>
        )}
      </div>

      {/* Input */}
      <div className="px-3 sm:px-6 pb-3 sm:pb-4 pt-2 border-t border-[var(--nexus-border)] bg-[var(--nexus-bg)]/40 safe-bottom">
        <div className="relative">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (!isStreaming) send();
              }
            }}
            placeholder={inputPlaceholder(activeSession.mode, activeSession.currentPhase)}
            rows={3}
            className="w-full px-3 sm:px-4 py-2.5 sm:py-3 pr-12 sm:pr-14 rounded-xl bg-[var(--nexus-surface)] border border-[var(--nexus-border)] focus:border-[color-mix(in_srgb,var(--nexus-purple)_50%,transparent)] focus:ring-2 focus:ring-[color-mix(in_srgb,var(--nexus-purple)_20%,transparent)] text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] resize-none transition"
            disabled={isStreaming}
          />
          <button
            onClick={isStreaming ? stop : send}
            disabled={!isStreaming && !input.trim()}
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