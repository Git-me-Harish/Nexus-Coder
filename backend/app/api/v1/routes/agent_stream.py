"""
POST a user message -> stream the agent's response over SSE, backed by
LangGraph. Event contract (all payload keys intentionally snake_case, as the
original TS stream route used):

  phase             turn starting: model, phase, worker, token budget
  stage             which reasoning stage is running -- planning | answering
                    | reviewing | revising (see app/agents/graph.py)
  reasoning         deltas of the plan stage's thinking
  token             deltas of the user-facing answer
  stream_reset      discard everything streamed so far for `scope` and
                    re-render from empty; emitted when a provider dies
                    mid-stream and we fall back, and when a rejected draft
                    is about to be replaced by its revision
  critique          the review stage's verdict on the draft
  phase_advanced    the agent judged the phase complete and it advanced
  provider_fallback / file_written / token_warning / task_complete / error / end

stage, reasoning, stream_reset, critique and phase_advanced are new with the
reasoning pipeline. The frontend ignores events it does not recognise, so an
older client degrades to plain token streaming rather than breaking.

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
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.agents import workspace
from app.agents.constants import PHASE_TO_WORKER, get_model
from app.agents.file_extraction import extract_files_from_output
from app.agents.graph import get_graph
from app.agents.prompts import build_context_digest
from app.agents.providers.base import ProviderError, ProviderNotConfiguredError
from app.api.deps import CurrentAuth, TenantDb
from app.models.message import AgentTask, Message, Specification, SessionFile
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

    return build_context_digest(
        mode=session.mode, spec_dimensions=spec_dimensions,
        prior_phase_summary=prior_summary, build_depth=session.build_depth,
    )


@router.post("/{session_id}/agent/stream")
async def stream_agent(session_id: str, payload: StreamMessageRequest, auth: CurrentAuth, db: TenantDb):
    session = await session_service.get_session(db, auth.tenant_id, auth.user_id, session_id)
    await session_service.check_token_budget(session)

    db.add(Message(session_id=session.id, user_id=auth.user_id, role="user", content=payload.user_message))
    await db.commit()

    # The DB is the single source of truth for history; the graph state's
    # `messages` is a plain overwrite field so re-sending it each turn
    # replaces rather than appends. See app/agents/state.py for the reducer
    # trap this avoids.
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
        final_state: dict = {}

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
            # "custom" carries the nodes' live token/reasoning/stage writes as
            # they are generated; "values" carries the state snapshot we need
            # after the graph settles. Draining the provider stream inside a
            # node and relying on "values" alone -- as this route used to --
            # meant nothing reached the client until the whole turn finished,
            # so there was no live output and long generations sat silent long
            # enough to risk an SSE idle-timeout.
            async for stream_mode, payload in graph.astream(
                {
                    "messages": history, "session_id": session.id, "mode": session.mode,
                    "current_phase": session.current_phase, "model_id": session.base_model_id,
                    "context_digest": context_digest,
                    # Explicit per-turn zeroing: these are overwrite fields, so
                    # this resets whatever the checkpoint holds from last turn.
                    "attempts": 0, "tokens_in": 0, "tokens_out": 0,
                    "fallback_events": [], "revision_notes": "",
                    "plan": {}, "critique": {}, "phase_output": "",
                    "should_advance_phase": False,
                    "tool_steps": 0, "tool_trace": [], "touched_paths": [],
                    "ran_command": False,
                },
                config=config, stream_mode=["custom", "values"],
            ):
                if stream_mode == "custom":
                    yield {"event": payload["event"], "data": json.dumps(payload["data"])}
                else:
                    final_state = payload
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

        full_text = final_state.get("phase_output", "")
        tokens_in = final_state.get("tokens_in", 0)
        tokens_out = final_state.get("tokens_out", 0)
        provider_used = final_state.get("provider_used", "unknown")
        answered_phase = session.current_phase

        assistant_message = Message(
            session_id=session.id, role="assistant", content=full_text,
            phase=answered_phase, model_id=session.base_model_id,
            tokens_in=tokens_in, tokens_out=tokens_out,
        )
        db.add(assistant_message)
        session.langgraph_thread_id = session.langgraph_thread_id or session.id
        session.tokens_used += tokens_in + tokens_out

        # Durable trace of the reasoning pipeline for this turn. AgentTask was
        # declared in the schema from the start but never written by anything,
        # so there was no way to inspect after the fact why the agent answered
        # as it did -- the plan, the verdict, and how many passes it took are
        # exactly what you need when a turn goes wrong.
        critique = final_state.get("critique") or {}
        tool_trace = final_state.get("tool_trace") or []
        db.add(AgentTask(
            session_id=session.id, task_type=PHASE_TO_WORKER.get(answered_phase, "coder"),
            status="completed", model_id=session.base_model_id,
            input_payload=json.dumps({"phase": answered_phase, "mode": session.mode}),
            output_payload=json.dumps({
                "plan": final_state.get("plan") or {},
                "critique": critique,
                "provider_used": provider_used,
                # What the agent actually did, not just what it said -- the
                # first thing you want when a turn goes wrong.
                "tool_trace": tool_trace,
                "tool_steps": final_state.get("tool_steps", 0),
                "ran_command": bool(final_state.get("ran_command")),
            }),
            tokens_in=tokens_in, tokens_out=tokens_out,
            iteration_count=final_state.get("attempts", 0),
            completed_at=datetime.now(timezone.utc),
        ))

        # Files reach the DB two ways now, and both still matter:
        #   - the ReAct tools wrote them through as they ran (agentic phases)
        #   - the fenced-code extractor parses them out of prose (every other
        #     phase, and any model that describes a file instead of writing it)
        # Dedupe by path so a file written both ways is announced once.
        written_files = await workspace.sync_to_db(
            db, session.id, final_state.get("touched_paths") or []
        )
        seen = {f["path"] for f in written_files}
        written_files += [
            f for f in await _upsert_session_files(db, session.id, full_text)
            if f["path"] not in seen
        ]
        await db.commit()

        for wf in written_files:
            yield {"event": "file_written", "data": json.dumps(wf)}

        await usage_service.record_usage(
            db, tenant_id=auth.tenant_id, session_id=session.id, user_id=auth.user_id,
            model_id=session.base_model_id, provider=provider_used, tokens_in=tokens_in, tokens_out=tokens_out,
        )

        # The graph decided the phase's exit criteria are met -- advance it.
        # This is what `should_advance_phase` was always supposed to do; it was
        # previously declared in the state and written by nobody, leaving phase
        # progression entirely on the user to drive by hand.
        #
        # It still goes through session_service.advance_phase rather than
        # assigning session.current_phase directly, so the specification ->
        # implementation approval gate stays enforced: the agent may believe
        # the spec is finished, but only a human confirming it unlocks the
        # implementation phase. A blocked advance is not an error here -- the
        # answer was still produced and the user simply stays put.
        if final_state.get("should_advance_phase"):
            try:
                updated = await session_service.advance_phase(
                    db, auth.tenant_id, auth.user_id, session.id, target=None
                )
                yield {"event": "phase_advanced", "data": json.dumps({
                    "from": answered_phase,
                    "to": updated.current_phase,
                    "reason": critique.get("reason", ""),
                })}
            except HTTPException as exc:
                logger.info(
                    "Phase advance from %s declined for session %s: %s",
                    answered_phase, session.id, getattr(exc, "detail", exc),
                )

        percent_used = (session.tokens_used / session.tokens_budget * 100) if session.tokens_budget else 0
        if percent_used >= 80:
            yield {"event": "token_warning", "data": json.dumps({"percent_used": round(percent_used)})}

        yield {"event": "task_complete", "data": json.dumps({"tokens_total": session.tokens_used})}
        yield {"event": "end", "data": json.dumps({})}

    return EventSourceResponse(event_generator())