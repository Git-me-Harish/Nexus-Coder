"use client";

import { useEffect, useState } from "react";
import {
  BookOpen, Pencil, GraduationCap, CheckCircle2, ArrowRight, Sparkles,
  TrendingUp, Award, ChevronRight, RotateCcw,
} from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { api } from "@/lib/nexus/client";
import { LEARNING_TOPICS, topicsByCategory, type LearningTopicDef } from "@/lib/nexus/learning/topics";
import type { LearningStage } from "@/lib/nexus/learning/engine";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

interface Topic {
  id: string;
  topicSlug: string;
  topicLabel: string;
  stage: LearningStage;
  difficulty: string;
  quizScore: number | null;
  startedAt: string;
  completedAt: string | null;
}

const STAGE_META: Record<LearningStage, { label: string; icon: any; color: string }> = {
  explain:   { label: "Explain",   icon: BookOpen,       color: "var(--mode-dev-text)" },
  practice:  { label: "Practice",  icon: Pencil,         color: "var(--mode-problem-text)" },
  quiz:      { label: "Quiz",      icon: GraduationCap,  color: "var(--mode-learning-text)" },
  completed: { label: "Completed", icon: CheckCircle2,   color: "var(--nexus-success)" },
};

export default function LearningPanel() {
  const { activeSession, setRightPanel } = useAppStore();
  const [topics, setTopics] = useState<Topic[]>([]);
  const [showPicker, setShowPicker] = useState(false);
  const [loading, setLoading] = useState(true);
  const [knowledgeSummary, setKnowledgeSummary] = useState<{ totalTopics: number; avgMastery: number; mastered: number } | null>(null);

  useEffect(() => {
    if (!activeSession) return;
    let cancelled = false;
    api.learning.listTopics(activeSession.id).then(({ topics }) => {
      if (!cancelled) {
        setTopics(topics);
        setShowPicker(topics.length === 0 || topics.every(t => t.stage === "completed"));
      }
    }).finally(() => { if (!cancelled) setLoading(false); });
    api.knowledge.get().then(({ summary }) => {
      if (!cancelled) setKnowledgeSummary(summary);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [activeSession?.id]);

  // Listen for quiz-submitted events to refresh mastery + topics
  useEffect(() => {
    const handler = () => {
      if (!activeSession) return;
      api.learning.listTopics(activeSession.id).then(({ topics }) => {
        setTopics(topics);
        setShowPicker(topics.length === 0 || topics.every(t => t.stage === "completed"));
      });
      api.knowledge.get().then(({ summary }) => setKnowledgeSummary(summary)).catch(() => {});
    };
    window.addEventListener("nexus:learning-updated", handler);
    return () => window.removeEventListener("nexus:learning-updated", handler);
  }, [activeSession?.id]);

  const activeTopic = topics.find((t) => t.stage !== "completed");

  /** Triggers the agent to generate content for the current stage by sending a chat message */
  async function triggerStageContent(topic: Topic) {
    if (!activeSession) return;
    const prompts: Record<LearningStage, string> = {
      explain: `Explain ${topic.topicLabel} at ${topic.difficulty} level. Give me a clear walkthrough with a real-world analogy and inline code examples.`,
      practice: `Give me a practice exercise on ${topic.topicLabel} at ${topic.difficulty} level. Provide a starter code block and 2-3 success criteria. Don't show the solution yet.`,
      quiz: `Quiz me on ${topic.topicLabel} at ${topic.difficulty} level. Ask 3 multiple-choice questions (A/B/C/D) with an answer key at the end.`,
      completed: "",
    };
    const prompt = prompts[topic.stage as LearningStage];
    if (!prompt) return;

    // Send the message via the messages API, then trigger the agent stream
    try {
      await api.messages.send(activeSession.id, prompt);
      // Dispatch a custom event the ChatPanel listens for to start streaming
      window.dispatchEvent(new CustomEvent("nexus:trigger-stream", { detail: { sessionId: activeSession.id } }));
    } catch (err: any) {
      toast.error(err?.message ?? "Failed to start stage");
    }
  }

  async function startTopic(slug: string) {
    if (!activeSession) return;
    try {
      const { topic } = await api.learning.startTopic(activeSession.id, slug);
      setTopics((prev) => [topic, ...prev]);
      setShowPicker(false);
      toast.success(`Started: ${topic.topicLabel}`);
      // Refresh activeSession so ChatPanel's QuizInterface can see the topic ID
      refreshActiveSession();
      // Auto-trigger the Explain stage
      setTimeout(() => triggerStageContent(topic), 300);
    } catch (err: any) {
      toast.error(err?.message ?? "Failed to start topic");
    }
  }

  async function advanceTopic(topicId: string) {
    if (!activeSession) return;
    try {
      const { topic } = await api.learning.advanceTopic(activeSession.id, topicId);
      setTopics((prev) => prev.map((t) => (t.id === topicId ? topic : t)));
      toast.success(`Stage: ${STAGE_META[topic.stage as LearningStage].label}`);
      // Refresh activeSession so the new stage + topicId propagate
      refreshActiveSession();
      // Auto-trigger content for the new stage (unless completed)
      if (topic.stage !== "completed") {
        setTimeout(() => triggerStageContent(topic), 300);
      }
    } catch (err: any) {
      toast.error(err?.message ?? "Failed to advance stage");
    }
  }

  /** Re-fetches the active session from the server so learningTopics + phase are fresh */
  async function refreshActiveSession() {
    if (!activeSession) return;
    try {
      const { session: fresh } = await api.sessions.get(activeSession.id);
      useAppStore.getState().setActiveSession(fresh);
    } catch {}
  }

  if (!activeSession) return null;
  if (loading) return <div className="p-4 text-xs text-[var(--muted-foreground)]">Loading…</div>;

  return (
    <div className="h-full flex flex-col overflow-y-auto">
      <div className="px-4 py-3 border-b border-[var(--nexus-border)]">
        <h3 className="text-sm font-semibold text-[var(--foreground)]">Learning Mode</h3>
        <p className="text-[11px] text-[var(--muted-foreground)]">Explain → Practice → Quiz · adaptive difficulty</p>
      </div>

      <div className="px-4 py-4 space-y-4">
        {/* Mastery summary */}
        {knowledgeSummary && knowledgeSummary.totalTopics > 0 && (
          <div className="p-3 rounded-xl bg-[var(--nexus-surface)]/60 border border-[var(--nexus-border)]">
            <div className="flex items-center gap-2 mb-2">
              <Award className="w-4 h-4 text-[var(--nexus-amber)]" />
              <span className="text-xs font-semibold text-[var(--foreground)]">Your mastery</span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <div className="text-lg font-bold text-[var(--foreground)]">{knowledgeSummary.totalTopics}</div>
                <div className="text-[10px] text-[var(--muted-foreground)]">topics</div>
              </div>
              <div>
                <div className="text-lg font-bold text-[var(--mode-dev-text)]">{knowledgeSummary.avgMastery}%</div>
                <div className="text-[10px] text-[var(--muted-foreground)]">avg score</div>
              </div>
              <div>
                <div className="text-lg font-bold text-[var(--nexus-success)]">{knowledgeSummary.mastered}</div>
                <div className="text-[10px] text-[var(--muted-foreground)]">mastered</div>
              </div>
            </div>
          </div>
        )}

        {/* Active topic card */}
        {activeTopic && (
          <ActiveTopicCard topic={activeTopic} onAdvance={() => advanceTopic(activeTopic.id)} />
        )}

        {/* Topic picker */}
        {showPicker && <TopicPicker onPick={startTopic} />}

        {/* Recent topics */}
        {!showPicker && topics.length > 0 && (
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--muted-foreground)] mb-2">
              Recent topics
            </div>
            <div className="space-y-1.5">
              {topics.slice(0, 6).map((t) => (
                <div key={t.id} className="px-2.5 py-2 rounded-md bg-[var(--nexus-surface)]/40 border border-[var(--nexus-border)]">
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="text-xs font-medium text-[var(--foreground)] truncate flex-1">{t.topicLabel}</span>
                    {t.stage === "completed" && t.quizScore != null && (
                      <span className={cn(
                        "text-[10px] font-semibold ml-2",
                        t.quizScore >= 80 ? "text-[var(--nexus-success)]" :
                        t.quizScore >= 50 ? "text-[var(--nexus-amber)]" :
                        "text-[var(--nexus-error)]"
                      )}>
                        {t.quizScore}%
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-[var(--muted-foreground)]">
                    <span className="capitalize">{t.difficulty}</span>
                    <span>·</span>
                    <span className="capitalize">{t.stage}</span>
                  </div>
                </div>
              ))}
            </div>
            <button
              onClick={() => setShowPicker(true)}
              className="mt-3 w-full py-2 rounded-lg text-xs font-medium bg-gradient-to-r from-[var(--nexus-purple)] to-[var(--nexus-purple-dim)] text-white hover:opacity-90 transition flex items-center justify-center gap-1.5"
            >
              <Sparkles className="w-3.5 h-3.5" />
              Start new topic
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function ActiveTopicCard({ topic, onAdvance }: { topic: Topic; onAdvance: () => void }) {
  const stages: LearningStage[] = ["explain", "practice", "quiz", "completed"];
  const currentIdx = stages.indexOf(topic.stage);

  return (
    <div className="p-3 rounded-xl bg-gradient-to-br from-[color-mix(in_srgb,var(--nexus-purple)_12%,transparent)] to-[color-mix(in_srgb,var(--nexus-violet)_6%,transparent)] border border-[color-mix(in_srgb,var(--nexus-purple)_30%,transparent)]">
      <div className="flex items-center gap-2 mb-1">
        <GraduationCap className="w-4 h-4 text-[var(--nexus-purple)]" />
        <span className="text-xs font-semibold text-[var(--foreground)] truncate flex-1">{topic.topicLabel}</span>
        <span className="px-1.5 py-0.5 rounded text-[9px] font-medium uppercase bg-[color-mix(in_srgb,var(--nexus-purple)_20%,transparent)] text-[var(--mode-dev-text)] border border-[color-mix(in_srgb,var(--nexus-purple)_30%,transparent)]">
          {topic.difficulty}
        </span>
      </div>

      {/* Stage stepper */}
      <div className="flex items-center gap-1 my-3">
        {stages.map((s, i) => {
          const Icon = STAGE_META[s].icon;
          const isCurrent = s === topic.stage;
          const isCompleted = currentIdx > i;
          return (
            <div key={s} className="flex items-center flex-1 last:flex-none">
              <div className={cn(
                "w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-semibold shrink-0",
                isCurrent ? "bg-[var(--nexus-purple)] text-white" :
                isCompleted ? "bg-[var(--nexus-success)] text-white" :
                "bg-[var(--nexus-surface-2)] text-[var(--muted-foreground)] border border-[var(--nexus-border)]"
              )}>
                <Icon className="w-3 h-3" />
              </div>
              {i < stages.length - 1 && (
                <div className={cn("flex-1 h-px mx-1", isCompleted ? "bg-[var(--nexus-success)]" : "bg-[var(--nexus-border)]")} />
              )}
            </div>
          );
        })}
      </div>

      <div className="text-[10px] text-[var(--muted-foreground)] mb-2 capitalize">
        Current stage: <span className="text-[var(--foreground)] font-medium">{topic.stage}</span>
      </div>

      {topic.stage !== "completed" && (
        <button
          onClick={onAdvance}
          className="w-full py-1.5 rounded-md text-[11px] font-medium bg-[var(--nexus-surface-2)] border border-[var(--nexus-border)] hover:border-[color-mix(in_srgb,var(--nexus-purple)_40%,transparent)] text-[var(--foreground)] transition flex items-center justify-center gap-1.5"
        >
          Advance to {STAGE_META[stages[currentIdx + 1] ?? stages[3]].label}
          <ArrowRight className="w-3 h-3" />
        </button>
      )}
    </div>
  );
}

function TopicPicker({ onPick }: { onPick: (slug: string) => void }) {
  const [query, setQuery] = useState("");
  const byCat = topicsByCategory();
  const filtered = query
    ? LEARNING_TOPICS.filter((t) => t.label.toLowerCase().includes(query.toLowerCase()) || t.description.toLowerCase().includes(query.toLowerCase()))
    : LEARNING_TOPICS;

  const filteredByCat: Record<string, LearningTopicDef[]> = {};
  for (const t of filtered) {
    if (!filteredByCat[t.category]) filteredByCat[t.category] = [];
    filteredByCat[t.category].push(t);
  }

  return (
    <div>
      <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--muted-foreground)] mb-2">
        Pick a topic
      </div>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search topics…"
        className="w-full px-2.5 py-1.5 mb-3 rounded-md bg-[var(--nexus-bg)] border border-[var(--nexus-border)] text-xs text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[color-mix(in_srgb,var(--nexus-purple)_40%,transparent)]"
      />
      <div className="space-y-3 max-h-[60vh] overflow-y-auto pr-1">
        {Object.entries(filteredByCat).map(([cat, list]) => (
          <div key={cat}>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--mode-dev-text)] mb-1.5 sticky top-0 bg-[var(--nexus-surface)]/90 backdrop-blur-sm py-1">
              {cat}
            </div>
            <div className="space-y-1">
              {list.map((t) => (
                <button
                  key={t.slug}
                  onClick={() => onPick(t.slug)}
                  className="w-full text-left px-2.5 py-2 rounded-md bg-[var(--nexus-surface)]/40 border border-[var(--nexus-border)] hover:border-[color-mix(in_srgb,var(--nexus-purple)_40%,transparent)] hover:bg-[var(--nexus-surface-2)] transition group"
                >
                  <div className="text-xs font-medium text-[var(--foreground)] mb-0.5 flex items-center gap-1.5">
                    <span className="truncate flex-1">{t.label}</span>
                    <ChevronRight className="w-3 h-3 text-[var(--muted-foreground)] group-hover:text-[var(--nexus-purple)] transition shrink-0" />
                  </div>
                  <div className="text-[10px] text-[var(--muted-foreground)] line-clamp-2">{t.description}</div>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
