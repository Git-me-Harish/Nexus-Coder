from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import AgentSession
from app.models.usage import TokenUsageLedger

_COST_PER_1K_TOKENS = {"anthropic": 0.006, "openai": 0.005, "zai": 0.002}


def estimate_cost_usd(provider: str, tokens_in: int, tokens_out: int) -> float:
    rate = _COST_PER_1K_TOKENS.get(provider, 0.005)
    return round((tokens_in + tokens_out) / 1000 * rate, 6)


async def record_usage(
    db: AsyncSession, *, tenant_id: str, session_id: str, user_id: str,
    model_id: str, provider: str, tokens_in: int, tokens_out: int,
) -> None:
    db.add(TokenUsageLedger(
        tenant_id=tenant_id, session_id=session_id, user_id=user_id,
        model_id=model_id, provider=provider, tokens_in=tokens_in, tokens_out=tokens_out,
        cost_usd=estimate_cost_usd(provider, tokens_in, tokens_out),
    ))
    session = await db.get(AgentSession, session_id)
    if session is not None:
        session.tokens_used += tokens_in + tokens_out
    await db.commit()


async def get_usage(db: AsyncSession, tenant_id: str, user_id: str, session_id: str | None = None) -> dict:
    ledger_stmt = select(TokenUsageLedger).where(TokenUsageLedger.tenant_id == tenant_id)
    if session_id:
        ledger_stmt = ledger_stmt.where(TokenUsageLedger.session_id == session_id)
    recent = (await db.execute(ledger_stmt.order_by(TokenUsageLedger.created_at.desc()).limit(200))).scalars().all()

    by_model: dict[str, dict] = {}
    for u in recent:
        entry = by_model.setdefault(u.model_id, {"tokensIn": 0, "tokensOut": 0, "costUsd": 0.0, "calls": 0})
        entry["tokensIn"] += u.tokens_in
        entry["tokensOut"] += u.tokens_out
        entry["costUsd"] += float(u.cost_usd)
        entry["calls"] += 1

    sessions = (await db.execute(
        select(AgentSession).where(AgentSession.tenant_id == tenant_id, AgentSession.user_id == user_id)
        .order_by(AgentSession.updated_at.desc()).limit(30)
    )).scalars().all()

    total_used = sum(s.tokens_used for s in sessions)
    total_budget = sum(s.tokens_budget for s in sessions)

    return {
        "summary": {
            "totalUsed": total_used, "totalBudget": total_budget,
            "percentUsed": (total_used / total_budget * 100) if total_budget > 0 else 0,
            "sessions": len(sessions),
        },
        "byModel": [{"modelId": k, **v} for k, v in by_model.items()],
        "sessions": [
            {"id": s.id, "tokensUsed": s.tokens_used, "tokensBudget": s.tokens_budget,
             "baseModelId": s.base_model_id, "mode": s.mode, "currentPhase": s.current_phase,
             "title": s.title, "updatedAt": s.updated_at.isoformat()}
            for s in sessions
        ],
        "recent": [
            {"id": u.id, "modelId": u.model_id, "tokensIn": u.tokens_in, "tokensOut": u.tokens_out,
             "costUsd": float(u.cost_usd), "recordedAt": u.created_at.isoformat()}
            for u in recent
        ],
    }
