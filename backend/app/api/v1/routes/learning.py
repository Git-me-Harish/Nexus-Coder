from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import select

from app.agents import learning_engine
from app.agents.topics import get_topic
from app.api.deps import CurrentAuth, TenantDb
from app.core.exceptions import api_error
from app.models.learning import LearningTopic, UserKnowledgeProfile
from app.schemas.learning import StartTopicRequest, SubmitQuizRequest
from app.services import session_service

router = APIRouter(prefix="/sessions", tags=["learning"])


def _serialize(t: LearningTopic) -> dict:
    return {
        "id": t.id, "sessionId": t.session_id, "topicSlug": t.topic_slug, "topicLabel": t.topic_label,
        "stage": t.stage, "difficulty": t.difficulty, "quizScore": t.quiz_score,
        "startedAt": t.started_at.isoformat(), "completedAt": t.completed_at.isoformat() if t.completed_at else None,
    }


@router.get("/{session_id}/learning/start")
async def list_topics(session_id: str, auth: CurrentAuth, db: TenantDb):
    topics = (await db.execute(
        select(LearningTopic).where(LearningTopic.session_id == session_id, LearningTopic.user_id == auth.user_id)
        .order_by(LearningTopic.started_at.desc())
    )).scalars().all()
    return {"topics": [_serialize(t) for t in topics]}


@router.post("/{session_id}/learning/start")
async def start_topic(session_id: str, payload: StartTopicRequest, auth: CurrentAuth, db: TenantDb):
    session = await session_service.get_session(db, auth.tenant_id, session_id)
    if session.mode != "learning":
        raise api_error(400, "WRONG_MODE", "Learning topics can only be started in learning sessions.")

    topic_def = get_topic(payload.topic_slug)
    if topic_def is None:
        raise api_error(400, "UNKNOWN_TOPIC", f"Unknown topic: {payload.topic_slug}")

    profile = (await db.execute(
        select(UserKnowledgeProfile).where(
            UserKnowledgeProfile.user_id == auth.user_id, UserKnowledgeProfile.topic_slug == payload.topic_slug
        )
    )).scalar_one_or_none()
    difficulty = "intermediate"
    if profile:
        difficulty = learning_engine.recommend_difficulty(profile.mastery_score, profile.attempts, "intermediate")

    topic = LearningTopic(
        session_id=session.id, user_id=auth.user_id, topic_slug=payload.topic_slug,
        topic_label=topic_def["label"], stage="explain", difficulty=difficulty,
    )
    db.add(topic)
    session.current_phase = "explain"
    await db.commit()
    await db.refresh(topic)
    return {"topic": _serialize(topic)}


@router.post("/{session_id}/learning/{topic_id}/advance")
async def advance_topic(session_id: str, topic_id: str, auth: CurrentAuth, db: TenantDb):
    topic = (await db.execute(
        select(LearningTopic).where(
            LearningTopic.id == topic_id, LearningTopic.session_id == session_id, LearningTopic.user_id == auth.user_id
        )
    )).scalar_one_or_none()
    if topic is None:
        raise api_error(404, "NOT_FOUND")

    target = learning_engine.next_stage(topic.stage)
    if target is None:
        raise api_error(400, "ALREADY_COMPLETED")

    topic.stage = target
    session = await session_service.get_session(db, auth.tenant_id, session_id)
    session.current_phase = "explain" if target == "completed" else target
    await db.commit()
    await db.refresh(topic)
    return {"topic": _serialize(topic)}


@router.post("/{session_id}/learning/{topic_id}/submit-quiz")
async def submit_quiz(session_id: str, topic_id: str, payload: SubmitQuizRequest, auth: CurrentAuth, db: TenantDb):
    topic = (await db.execute(
        select(LearningTopic).where(
            LearningTopic.id == topic_id, LearningTopic.session_id == session_id, LearningTopic.user_id == auth.user_id
        )
    )).scalar_one_or_none()
    if topic is None:
        raise api_error(404, "NOT_FOUND")
    if topic.stage != "quiz":
        raise api_error(400, "WRONG_STAGE", "Can only submit quiz during the quiz stage.")

    score = learning_engine.grade_quiz(payload.quiz_text, payload.answers)
    topic.quiz_score = score
    topic.stage = "completed"
    topic.completed_at = datetime.now(timezone.utc)
    await db.flush()

    mastery = await learning_engine.recompute_mastery(db, auth.user_id, topic.topic_slug, score)

    session = await session_service.get_session(db, auth.tenant_id, session_id)
    session.current_phase = "explain"
    await db.commit()
    await db.refresh(topic)

    return {"topic": _serialize(topic), "score": score, "mastery": mastery, "passed": score >= 70}