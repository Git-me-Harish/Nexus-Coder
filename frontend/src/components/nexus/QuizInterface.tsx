"use client";

import { useState } from "react";
import { CheckCircle2, XCircle, RotateCcw, Award, TrendingUp } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { useAuthStore } from "@/stores/authStore";
import { api } from "@/lib/nexus/client";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

interface Props {
  quizText: string;       // The assistant's quiz output (with answer key)
  topicId: string;        // Active learning topic ID
}

interface ParsedQuestion {
  number: number;
  text: string;
  options: Record<string, string>;
  correctAnswer?: string;
}

function parseQuiz(text: string): { questions: ParsedQuestion[]; answerKey: Record<number, string> } {
  const questions: ParsedQuestion[] = [];
  const answerKey: Record<number, string> = {};

  // Match questions: "**Q1.** text" followed by options "- A) ... - B) ..."
  const qRegex = /\*\*Q(\d+)\.\*\*\s*(.+?)(?=\*\*Q\d|Answer Key|$)/gs;
  let qMatch: RegExpExecArray | null;
  while ((qMatch = qRegex.exec(text)) !== null) {
    const num = parseInt(qMatch[1]);
    const body = qMatch[2];
    // Split into question text + options
    const lines = body.split("\n").map((l) => l.trim()).filter(Boolean);
    const questionText = lines[0] ?? "";
    const options: Record<string, string> = {};
    for (const line of lines.slice(1)) {
      const optMatch = line.match(/^[-•]?\s*([ABCD])\)\s*(.+)/);
      if (optMatch) options[optMatch[1]] = optMatch[2].trim();
    }
    questions.push({ number: num, text: questionText, options });
  }

  // Match answer key: "Answer Key:" section with "1. A" patterns
  const keyMatch = text.match(/Answer Key:?\s*([\s\S]*?)$/i);
  if (keyMatch) {
    const keySection = keyMatch[1];
    for (let i = 1; i <= 3; i++) {
      const re = new RegExp(`(?:Q?${i}[.):]\\s*|^\\s*${i}[.):]\\s*)([ABCD])`, "im");
      const m = keySection.match(re);
      if (m) answerKey[i] = m[1].toUpperCase();
    }
  }

  return { questions, answerKey };
}

export default function QuizInterface({ quizText, topicId }: Props) {
  const { activeSession } = useAppStore();
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [submitted, setSubmitted] = useState(false);
  const [result, setResult] = useState<{ score: number; passed: boolean; mastery: any } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const { questions, answerKey } = parseQuiz(quizText);

  if (questions.length === 0) {
    return null; // Quiz text didn't parse — let the user read it as plain markdown
  }

  async function submit() {
    if (!activeSession) return;
    if (Object.keys(answers).length < questions.length) {
      toast.warning("Answer all questions before submitting.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.learning.submitQuiz(activeSession.id, topicId, answers, quizText);
      setResult({ score: res.score, passed: res.passed, mastery: res.mastery });
      setSubmitted(true);
      if (res.passed) toast.success(`Quiz passed — ${res.score}%`);
      else toast.warning(`Quiz score: ${res.score}% — keep practicing`);
      // Trigger a refresh of the LearningPanel + mastery summary
      window.dispatchEvent(new CustomEvent("nexus:learning-updated"));
    } catch (err: any) {
      toast.error(err?.message ?? "Failed to submit quiz");
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    setAnswers({});
    setSubmitted(false);
    setResult(null);
  }

  return (
    <div className="my-3 p-4 rounded-xl bg-[var(--nexus-surface)] border border-[color-mix(in_srgb,var(--nexus-purple)_30%,transparent)]">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[var(--nexus-teal)] to-[var(--nexus-purple)] flex items-center justify-center">
          <Award className="w-4 h-4 text-white" />
        </div>
        <div className="flex-1">
          <div className="text-sm font-semibold text-[var(--foreground)]">Quiz — pick your answers</div>
          <div className="text-[10px] text-[var(--muted-foreground)]">{questions.length} questions · auto-graded on submit</div>
        </div>
      </div>

      {/* Result banner */}
      {submitted && result && (
        <div className={cn(
          "mb-4 p-3 rounded-lg border flex items-center gap-3",
          result.passed
            ? "bg-[color-mix(in_srgb,var(--nexus-success)_12%,transparent)] border-[color-mix(in_srgb,var(--nexus-success)_30%,transparent)]"
            : "bg-[color-mix(in_srgb,var(--nexus-amber)_12%,transparent)] border-[color-mix(in_srgb,var(--nexus-amber)_30%,transparent)]"
        )}>
          {result.passed
            ? <CheckCircle2 className="w-6 h-6 text-[var(--nexus-success)] shrink-0" />
            : <XCircle className="w-6 h-6 text-[var(--nexus-amber)] shrink-0" />}
          <div className="flex-1">
            <div className="text-sm font-semibold text-[var(--foreground)]">
              Score: {result.score}% {result.passed ? "— Passed!" : "— Retry recommended"}
            </div>
            <div className="text-[10px] text-[var(--muted-foreground)]">
              Mastery: {result.mastery?.masteryScore?.toFixed(0)}% across {result.mastery?.attempts} attempt{result.mastery?.attempts !== 1 ? "s" : ""}
              {result.mastery?.difficulty && ` · next difficulty: ${result.mastery.difficulty}`}
            </div>
          </div>
          <button
            onClick={reset}
            className="px-2.5 py-1 rounded-md text-xs border border-[var(--nexus-border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--nexus-surface-2)] transition flex items-center gap-1.5"
          >
            <RotateCcw className="w-3 h-3" />
            Retry
          </button>
        </div>
      )}

      {/* Questions */}
      <div className="space-y-4">
        {questions.map((q) => {
          const userAnswer = answers[q.number];
          const correctAnswer = answerKey[q.number];
          const isCorrect = submitted && userAnswer === correctAnswer;
          const isWrong = submitted && userAnswer && userAnswer !== correctAnswer;
          return (
            <div key={q.number}>
              <div className="text-xs font-medium text-[var(--foreground)] mb-2">
                {q.number}. {q.text}
              </div>
              <div className="space-y-1.5">
                {Object.entries(q.options).map(([letter, text]) => {
                  const selected = userAnswer === letter;
                  const showCorrect = submitted && letter === correctAnswer;
                  const showWrong = submitted && selected && letter !== correctAnswer;
                  return (
                    <button
                      key={letter}
                      onClick={() => !submitted && setAnswers((a) => ({ ...a, [q.number]: letter }))}
                      disabled={submitted}
                      className={cn(
                        "w-full text-left px-3 py-2 rounded-md border text-xs transition flex items-center gap-2",
                        submitted
                          ? showCorrect
                            ? "bg-[color-mix(in_srgb,var(--nexus-success)_12%,transparent)] border-[color-mix(in_srgb,var(--nexus-success)_40%,transparent)] text-[var(--foreground)]"
                            : showWrong
                            ? "bg-[color-mix(in_srgb,var(--nexus-error)_12%,transparent)] border-[color-mix(in_srgb,var(--nexus-error)_40%,transparent)] text-[var(--foreground)]"
                            : "bg-[var(--nexus-surface)]/40 border-[var(--nexus-border)] text-[var(--muted-foreground)]"
                          : selected
                            ? "bg-[color-mix(in_srgb,var(--nexus-purple)_12%,transparent)] border-[color-mix(in_srgb,var(--nexus-purple)_40%,transparent)] text-[var(--foreground)]"
                            : "bg-[var(--nexus-surface)]/40 border-[var(--nexus-border)] text-[var(--muted-foreground)] hover:border-[color-mix(in_srgb,var(--nexus-purple)_30%,transparent)] hover:text-[var(--foreground)]"
                      )}
                    >
                      <span className={cn(
                        "w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-semibold shrink-0",
                        submitted && showCorrect ? "bg-[var(--nexus-success)] text-white" :
                        submitted && showWrong ? "bg-[var(--nexus-error)] text-white" :
                        selected ? "bg-[var(--nexus-purple)] text-white" :
                        "bg-[var(--nexus-surface-2)] text-[var(--muted-foreground)] border border-[var(--nexus-border)]"
                      )}>
                        {letter}
                      </span>
                      <span className="flex-1">{text}</span>
                      {submitted && showCorrect && <CheckCircle2 className="w-3.5 h-3.5 text-[var(--nexus-success)] shrink-0" />}
                      {submitted && showWrong && <XCircle className="w-3.5 h-3.5 text-[var(--nexus-error)] shrink-0" />}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Submit button */}
      {!submitted && (
        <button
          onClick={submit}
          disabled={submitting || Object.keys(answers).length < questions.length}
          className="mt-4 w-full py-2 rounded-lg text-xs font-medium bg-gradient-to-r from-[var(--nexus-purple)] to-[var(--nexus-purple-dim)] text-white disabled:opacity-40 hover:opacity-90 transition flex items-center justify-center gap-1.5"
        >
          {submitting ? "Grading…" : `Submit quiz (${Object.keys(answers).length}/${questions.length} answered)`}
        </button>
      )}
    </div>
  );
}
