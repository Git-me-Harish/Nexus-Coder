"""
Faithful port of src/lib/nexus/learning/engine.ts — stage machine, rolling
mastery average, adaptive difficulty tiers, and quiz grading regex.
"""
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learning import LearningTopic, UserKnowledgeProfile

STAGE_ORDER = ["explain", "practice", "quiz", "completed"]
DIFFICULTY_TIERS = ["beginner", "intermediate", "advanced"]
MASTERY_WINDOW = 5
PROMOTION_THRESHOLD = 80
DEMOTION_THRESHOLD = 50


def next_stage(stage: str) -> str | None:
    idx = STAGE_ORDER.index(stage) if stage in STAGE_ORDER else -1
    if idx < 0 or idx == len(STAGE_ORDER) - 1:
        return None
    return STAGE_ORDER[idx + 1]


def recommend_difficulty(current_mastery: float, attempts: int, current_difficulty: str) -> str:
    if attempts < 2:
        return current_difficulty
    idx = DIFFICULTY_TIERS.index(current_difficulty) if current_difficulty in DIFFICULTY_TIERS else 1
    if current_mastery >= PROMOTION_THRESHOLD and idx < len(DIFFICULTY_TIERS) - 1:
        return DIFFICULTY_TIERS[idx + 1]
    if current_mastery < DEMOTION_THRESHOLD and idx > 0:
        return DIFFICULTY_TIERS[idx - 1]
    return current_difficulty


async def recompute_mastery(db: AsyncSession, user_id: str, topic_slug: str, new_score: float) -> dict:
    result = await db.execute(
        select(LearningTopic.quiz_score)
        .where(LearningTopic.user_id == user_id, LearningTopic.topic_slug == topic_slug, LearningTopic.stage == "completed")
        .order_by(LearningTopic.completed_at.desc())
        .limit(MASTERY_WINDOW - 1)
    )
    recent_scores = [row[0] or 0 for row in result.all()]
    scores = [new_score, *recent_scores]
    mastery_score = sum(scores) / len(scores)
    attempts = len(scores)

    profile_result = await db.execute(
        select(UserKnowledgeProfile).where(
            UserKnowledgeProfile.user_id == user_id, UserKnowledgeProfile.topic_slug == topic_slug
        )
    )
    existing = profile_result.scalar_one_or_none()
    prior_mastery = existing.mastery_score if existing else 0
    current_difficulty = (
        "advanced" if prior_mastery >= PROMOTION_THRESHOLD
        else "beginner" if prior_mastery < DEMOTION_THRESHOLD and attempts > 1
        else "intermediate"
    )
    new_difficulty = recommend_difficulty(mastery_score, attempts, current_difficulty)

    now = datetime.now(timezone.utc)
    if existing:
        existing.mastery_score = mastery_score
        existing.attempts = attempts
        existing.updated_at = now
    else:
        db.add(UserKnowledgeProfile(
            user_id=user_id, topic_slug=topic_slug, mastery_score=mastery_score,
        ))
    await db.flush()

    return {
        "topicSlug": topic_slug, "masteryScore": mastery_score, "attempts": attempts,
        "difficulty": new_difficulty, "lastReviewedAt": now.isoformat(),
    }


async def get_knowledge_profile(db: AsyncSession, user_id: str) -> list[dict]:
    result = await db.execute(
        select(UserKnowledgeProfile)
        .where(UserKnowledgeProfile.user_id == user_id)
        .order_by(UserKnowledgeProfile.mastery_score.desc())
    )
    out = []
    for p in result.scalars().all():
        difficulty_seed = (
            "advanced" if p.mastery_score >= PROMOTION_THRESHOLD
            else "beginner" if p.mastery_score < DEMOTION_THRESHOLD
            else "intermediate"
        )
        out.append({
            "topicSlug": p.topic_slug, "masteryScore": p.mastery_score,
            "lastReviewedAt": p.updated_at.isoformat() if p.updated_at else None,
            "difficulty": recommend_difficulty(p.mastery_score, 2, difficulty_seed),
        })
    return out


def grade_quiz(quiz_text: str, user_answers: dict[int, str]) -> int:
    key_match = re.search(r"Answer Key:?\s*([\s\S]*)$", quiz_text, re.IGNORECASE)
    if not key_match:
        return 0
    key_section = key_match.group(1)
    correct = total = 0
    for i in range(1, 4):
        pattern = rf"(?:Q?{i}[.):]\s*|^\s*{i}[.):]\s*)([ABCD])"
        m = re.search(pattern, key_section, re.IGNORECASE | re.MULTILINE)
        if m:
            total += 1
            correct_answer = m.group(1).upper()
            user_answer = str(user_answers.get(i, "")).upper()
            if user_answer == correct_answer:
                correct += 1
    return round((correct / total) * 100) if total > 0 else 0
