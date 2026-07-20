// Nexus — Learning mode client-side helpers
//
// The stateful, DB-backed mastery calculation (rolling average, adaptive
// difficulty persistence) now lives in the Python backend —
// app/agents/learning_engine.py — since it's the source of truth and the
// frontend has no direct DB access post-migration. This file keeps only
// the pure, stateless pieces the UI needs synchronously: types and the
// stage-machine helper used for local optimistic UI transitions before
// the server response confirms them.
//
// Mirror these constants exactly if you change the backend's
// PROMOTION_THRESHOLD / DEMOTION_THRESHOLD / STAGE_ORDER — see
// app/agents/learning_engine.py for the authoritative values.

export type LearningStage = "explain" | "practice" | "quiz" | "completed";
export type Difficulty = "beginner" | "intermediate" | "advanced";

export const STAGE_ORDER: LearningStage[] = ["explain", "practice", "quiz", "completed"];

export function nextStage(stage: LearningStage): LearningStage | null {
  const idx = STAGE_ORDER.indexOf(stage);
  if (idx < 0 || idx === STAGE_ORDER.length - 1) return null;
  return STAGE_ORDER[idx + 1];
}

export interface MasteryInfo {
  topicSlug: string;
  masteryScore: number;
  attempts: number;
  difficulty: Difficulty;
  lastReviewedAt: string | null;
}
