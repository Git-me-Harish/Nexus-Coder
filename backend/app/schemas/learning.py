from datetime import datetime

from app.schemas.base import CamelModel


class StartTopicRequest(CamelModel):
    topic_slug: str


class SubmitQuizRequest(CamelModel):
    answers: dict[int, str]
    quiz_text: str


class LearningTopicOut(CamelModel):
    id: str
    session_id: str
    topic_slug: str
    topic_label: str
    stage: str
    difficulty: str
    quiz_score: float | None
    started_at: datetime
    completed_at: datetime | None


class MasteryOut(CamelModel):
    topic_slug: str
    mastery_score: float
    attempts: int
    difficulty: str
    last_reviewed_at: str | None


class SubmitQuizResponse(CamelModel):
    topic: LearningTopicOut
    score: int
    mastery: MasteryOut
    passed: bool
