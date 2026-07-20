"""
POST a user message -> stream the agent's response over SSE, backed by
LangGraph. Event contract matches the frontend's existing SSE parser
(src/components/nexus/ChatPanel.tsx) exactly — phase/token/task_complete/
error/end/provider_fallback/file_written/token_warning, with the same
(intentionally snake_case) payload keys the original TS stream route
used, so the chat UI needs zero changes.

file_written and provider_fallback were both listened for by the frontend
from the start but never emitted by the initial migration — this route
now extracts fenced-code file blocks from the assistant's output and
persists them (see app/agents/file_extraction.py), and surfaces provider
fallbacks recorded by the router (see app/agents/providers/router.py).

ProviderNotConfiguredError is caught separately from a generic ProviderError
so the frontend gets an actionable "configure a model" signal instead of a
"something went wrong, try again" that gives the user nothing to act on --
previously every single unconfigured-key case looked identical to a real
upstream failure.
"""
import json
import logging

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.agents.constants import PHASE_TO_WORKER, get_model
from app.agents.file_extraction import extract_files_from_output
from app.agents.graph import get_graph
from app.agents.prompts import build_context_digest
from app.agents.providers.base import ProviderError, ProviderNotConfiguredError
from app.api.deps import CurrentAuth, TenantDb
from app.core.exceptions import api_error
from app.models.message import Message, Specification, SessionFile
from app.schemas.session import MessageOut, SendMessageRequest, StreamMessageRequest
from app.services import session_service, usage_service

router = APIRouter(prefix="/sessions", tags=["agent"])
logger = logging.getLogger("nexus.agent_stream")


@router.get("/{session_id}/messages")
async def list_messages(session_id: str, auth: CurrentAuth, db: TenantDb):
    messages = await session_service.list_messages(db, auth.tenant_id, auth.user_id, session_id)
    return {"messages": [MessageOut.model_validate(m) for m in messages]}


@router.post("/{session_id}/messages")
async def send_message(session_id: str, payload: SendMessageRequest, auth: CurrentAuth, db: TenantDb):
    # Non-streaming send — kept for API completeness; the chat UI uses the
    # SSE endpoint below for actual agent turns.
    session = await session_service.get_session(db, auth.tenant_id, auth.user_id, session_id)
    message = Message(session_id=session.id, user_id=auth.user_id, role="user", content=payload.content)
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return {"message": MessageOut.model_validate(message)}


async def _upsert_session_files(db: "AsyncSession", session_id: str, full_text: str) -> list[dict]:
    """Persist any fenced file blocks in the assistant's output. Returns
    the list of {path, language} dicts written, for the file_written events."""
    extracted = extract_files_from_output(full_text)
    written = []
    for f in extracted:
        existing = (await db.execute(
            select(SessionFile).where(SessionFile.session_id == session_id, SessionFile.file_path == f.path)
        )).scalar_one_or_none()
        if existing:
            existing.content = f.content
            existing.language = f.language
            existing.version += 1
        else:
            db.add(SessionFile(session_id=session_id, file_path=f.path, content=f.content, language=f.language))
        written.append({"path": f.path, "language": f.language})
    return written


async def _build_context_digest(db: "AsyncSession", session) -> str:
    spec = (await db.execute(
        select(Specification).where(Specification.session_id == session.id, Specification.is_current.is_(True))
    )).scalar_one_or_none()
    spec_dimensions = json.loads(spec.dimensions) if spec and spec.dimensions else None

    prior = (await db.execute(
        select(Message)
        .where(Message.session_id == session.id, Message.role == "assistant", Message.phase.isnot(None))
        .order_by(Message.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    prior_summary = None
    if prior and prior.phase != session.current_phase:
        # Short pointer, not the full text -- keeps the digest compact.
        prior_summary = f"[{prior.phase}] {prior.content[:280]}" + ("..." if len(prior.content) > 280 else "")

    return build_context_digest(mode=session.mode, spec_dimensions=spec_dimensions, prior_phase_summary=prior_summary)


@router.post("/{session_id}/agent/stream")
async def stream_agent(session_id: str, payload: StreamMessageRequest, auth: CurrentAuth, db: TenantDb):
    session = await session_service.get_session(db, auth.tenant_id, auth.user_id, session_id)
    await session_service.check_token_budget(session)

    db.add(Message(session_id=session.id, user_id=auth.user_id, role="user", content=payload.user_message))
    await db.commit()

    history = [
        {"role": m.role, "content": m.content}
        for m in (await db.execute(
            select(Message).where(Message.session_id == session.id).order_by(Message.created_at.asc())
        )).scalars().all()
    ]
    context_digest = await _build_context_digest(db, session)

    model = get_model(session.base_model_id) or {}
    worker = PHASE_TO_WORKER.get(session.current_phase, "coder")

    async def event_generator():
        graph = get_graph()
        config = {
            "configurable": {
                "thread_id": session.langgraph_thread_id or session.id,
                "db": db,
                "tenant_id": auth.tenant_id,
            }
        }
        full_text = ""
        tokens_in = tokens_out = 0
        provider_used = "unknown"
        fallback_events_emitted = 0

        yield {
            "event": "phase",
            "data": json.dumps({
                "model_id": session.base_model_id,
                "model_name": model.get("displayName", session.base_model_id),
                "phase": session.current_phase,
                "worker": worker,
                "tokens_used": session.tokens_used,
                "tokens_budget": session.tokens_budget,
            }),
        }

        try:
            async for event in graph.astream(
                {
                    "messages": history, "session_id": session.id, "mode": session.mode,
                    "current_phase": session.current_phase, "model_id": session.base_model_id,
                    "context_digest": context_digest, "iterations": 0,
                },
                config=config, stream_mode="values",
            ):
                latest = event.get("phase_output", "")
                if latest and latest != full_text:
                    delta = latest[len(full_text):]
                    full_text = latest
                    yield {"event": "token", "data": json.dumps({"content": delta})}
                tokens_in = event.get("tokens_in", tokens_in)
                tokens_out = event.get("tokens_out", tokens_out)
                provider_used = event.get("provider_used", provider_used)

                fallback_events = event.get("fallback_events") or []
                for fb in fallback_events[fallback_events_emitted:]:
                    yield {
                        "event": "provider_fallback",
                        "data": json.dumps({
                            "requested_model": fb["requested_model"],
                            "fallback_provider": fb["fallback_provider"],
                            "fallback_model": fb["fallback_model"],
                            "reason": fb["reason"],
                        }),
                    }
                fallback_events_emitted = len(fallback_events)
        except ProviderNotConfiguredError as exc:
            logger.info("Agent run blocked for session %s: no key for %s", session.id, exc.provider)
            yield {"event": "error", "data": json.dumps({
                "code": "PROVIDER_NOT_CONFIGURED",
                "provider": exc.provider,
                "message": f"No API key configured for {exc.provider}. Open Configure Models to add one.",
            })}
            return
        except ProviderError as exc:
            logger.error("Agent run failed for session %s: %s", session.id, exc)
            yield {"event": "error", "data": json.dumps({
                "code": "AGENT_FAILED",
                "message": "The agent run failed. Please try again.",
            })}
            return

        assistant_message = Message(
            session_id=session.id, role="assistant", content=full_text,
            phase=session.current_phase, model_id=session.base_model_id,
            tokens_in=tokens_in, tokens_out=tokens_out,
        )
        db.add(assistant_message)
        session.langgraph_thread_id = session.langgraph_thread_id or session.id
        session.tokens_used += tokens_in + tokens_out

        written_files = await _upsert_session_files(db, session.id, full_text)
        await db.commit()

        for wf in written_files:
            yield {"event": "file_written", "data": json.dumps(wf)}

        await usage_service.record_usage(
            db, tenant_id=auth.tenant_id, session_id=session.id, user_id=auth.user_id,
            model_id=session.base_model_id, provider=provider_used, tokens_in=tokens_in, tokens_out=tokens_out,
        )

        percent_used = (session.tokens_used / session.tokens_budget * 100) if session.tokens_budget else 0
        if percent_used >= 80:
            yield {"event": "token_warning", "data": json.dumps({"percent_used": round(percent_used)})}

        yield {"event": "task_complete", "data": json.dumps({"tokens_total": session.tokens_used})}
        yield {"event": "end", "data": json.dumps({})}

    return EventSourceResponse(event_generator())