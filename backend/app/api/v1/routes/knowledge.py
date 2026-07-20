from fastapi import APIRouter

from app.agents import learning_engine
from app.agents.topics import get_topic, related_topics
from app.api.deps import CurrentAuth, TenantDb

router = APIRouter(prefix="/me", tags=["knowledge"])


@router.get("/knowledge")
async def get_knowledge(auth: CurrentAuth, db: TenantDb):
    profile = await learning_engine.get_knowledge_profile(db, auth.user_id)

    enriched = []
    for p in profile:
        topic_def = get_topic(p["topicSlug"]) or {}
        enriched.append({
            **p,
            "label": topic_def.get("label", p["topicSlug"]),
            "category": topic_def.get("category"),
            "description": topic_def.get("description"),
            "related": [{"slug": r["slug"], "label": r["label"]} for r in related_topics(p["topicSlug"], 3)],
        })

    total = len(enriched)
    summary = {
        "totalTopics": total,
        "avgMastery": round(sum(e["masteryScore"] for e in enriched) / total) if total else 0,
        "mastered": sum(1 for e in enriched if e["masteryScore"] >= 80),
        "inProgress": sum(1 for e in enriched if 50 <= e["masteryScore"] < 80),
        "struggling": sum(1 for e in enriched if e["masteryScore"] < 50),
    }
    return {"profile": enriched, "summary": summary}