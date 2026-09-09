"""
The Nexus agent graph: plan -> ReAct loop -> critique -> (revise | finish).

WHAT CHANGED AND WHY
--------------------
This was previously a single `run_phase` node -- one LLM call per turn
wearing a phase-specific system prompt -- with a `route_next` that returned
END unconditionally. Nothing in it planned, checked its own work, or decided
anything; "planning" and "implementation" were the same one-shot completion
with different wording, and phase advancement happened entirely outside the
graph via the `/sessions/{id}/phase` endpoint the user had to click.

The graph now actually reasons:

      START ─(needs planning?)─┬─> plan ──┐
                               └──────────┴─> execute ─(needs critique?)─┬─> critique ─┬─> execute (revise)
                                                                         │             └─> END
                                                                         └─> END

  - `plan` produces a structured plan (goal / steps / risks / success
    criteria) that the execution stage must follow and the critic scores
    against. Its tokens stream to the UI as `reasoning` events, so the user
    can watch it think rather than staring at a spinner.
  - `execute` is a ReAct loop, not a single call. On the agentic phases the
    model is given real tools and its calls are actually executed -- files
    land on disk and in the DB, commands run in a Docker sandbox, and real
    exit codes and stderr come back as observations it must react to. It
    loops until it stops asking for tools or hits MAX_TOOL_STEPS.
  - `critique` judges the result against the plan's success criteria, the
    phase's exit criteria, AND the tool trace -- so "the tests pass" is
    checked against whether a command actually ran and what it returned,
    rather than taken on faith. It also decides whether the phase itself is
    finished, which is what makes phase advancement real.
  - a rejected draft loops back into `execute` with the critic's specific
    defects injected, bounded by MAX_ATTEMPTS.

The two loops are bounded independently and for different reasons:
MAX_TOOL_STEPS caps acting within one answer (a model stuck re-running a
failing command), MAX_ATTEMPTS caps re-answering after review (a critic that
never approves). Both cost the user real money while they spin.

STREAMING
---------
Nodes emit tokens through LangGraph's injected `StreamWriter` (consumed via
`stream_mode=["custom", "values"]` in agent_stream.py). The old node drained
its whole provider stream before returning a dict, so `stream_mode="values"`
could only surface the finished text -- the UI got one giant delta at the end
instead of live tokens, and long generations risked SSE idle-timeouts with no
bytes on the wire. Writing to the stream writer as chunks arrive is what
makes the streaming actually stream.

(langgraph 0.2.62 has no `langgraph.config.get_stream_writer`; the injected
`writer` parameter is the supported mechanism on this version.)

COST
----
A planned + critiqued turn is 3 LLM calls instead of 1 (up to 4 with a
revision pass). That is the price of the behavior, so it is spent
selectively: PLANNED_PHASES and CRITIQUED_PHASES below restrict it to the
phases where structure pays for itself, and conversational phases
(ideation, discussion, explain, ...) stay a single call. All stages use the
session's own model; if you want a cheaper critic, that is the one knob to
turn -- see _CRITIC_MODEL_OVERRIDE.
"""
import logging

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import StreamWriter

from app.agents.prompts import (
    build_critic_input,
    build_critic_prompt,
    build_planner_prompt,
    build_revision_directive,
    parse_json_object,
    system_prompt_for_phase,
)
from app.agents.providers.base import (
    AgentMessage,
    ProviderError,
    ToolCall,
    ToolResult,
    ToolSpec,
)
from app.agents.providers.router import route_and_stream
from app.agents.state import NexusAgentState
from app.agents.tools import (
    DOC_TOOL_SPECS,
    FULL_TOOL_SPECS,
    ToolContext,
    execute_tool_calls,
    summarize_call,
)

logger = logging.getLogger("nexus.graph")

#: Hard ceiling on execute→critique cycles in a single turn. One revision
#: pass is where nearly all the value is; beyond that the critic tends to
#: relitigate taste while the user waits and pays.
MAX_ATTEMPTS = 2

#: Phases where an explicit plan earns its extra call. Conversational phases
#: (discussion/explain/practice/quiz) are excluded -- planning a chat reply
#: just adds latency and cost. Ideation is IN this set: it now converges on
#: and writes a confirmed IDEA.md rather than staying purely conversational,
#: so it earns the same plan->critique structure as the other artifact phases.
PLANNED_PHASES = frozenset({"ideation", "planning", "specification", "implementation", "debug", "review"})

#: Phases where self-critique earns its extra call: the ones producing an
#: artifact that can be objectively wrong.
CRITIQUED_PHASES = frozenset({"ideation", "planning", "specification", "implementation", "debug", "review"})

#: Which tools (if any) each phase's execute step is handed. A phase absent
#: from this map (discussion/explain/practice/quiz) gets none at all --
#: conversational phases should not be handed anything to call.
#:
#: Ideation/planning/specification get DOC_TOOL_SPECS only (write_file/
#: read_file/list_files, no run_command): they produce workspace artifacts
#: (IDEA.md/PLAN.md/SPEC.md) but there is no code yet to execute. Handing them
#: run_command would just invite probing an empty container. Implementation/
#: debug/review get the full set, run_command included, because verifying
#: real behavior is the entire point of those phases.
PHASE_TOOLS: dict[str, list] = {
    "ideation": DOC_TOOL_SPECS,
    "planning": DOC_TOOL_SPECS,
    "specification": DOC_TOOL_SPECS,
    "implementation": FULL_TOOL_SPECS,
    "debug": FULL_TOOL_SPECS,
    "review": FULL_TOOL_SPECS,
}

#: Ceiling on reason->act->observe cycles within a single turn. High enough
#: for a real build-test-fix loop, low enough that a model stuck retrying a
#: failing command cannot burn the session budget unattended.
MAX_TOOL_STEPS = 12

#: Set to a model id to run plan/critique on something cheaper than the
#: session's model. None = use the session's model everywhere, which keeps
#: the critic as capable as the writer (a weak critic on strong output is
#: worse than no critic -- it rejects on noise).
_CRITIC_MODEL_OVERRIDE: str | None = None


def _accumulate(state: NexusAgentState, meta: dict) -> dict:
    """
    Fold one LLM call's telemetry into the turn's running totals.

    Absolute values, computed from `state`, NOT a reducer -- see the module
    docstring in app/agents/state.py for why an accumulating reducer would
    silently keep climbing across turns instead of resetting.
    """
    return {
        "tokens_in": state.get("tokens_in", 0) + meta["tokens_in"],
        "tokens_out": state.get("tokens_out", 0) + meta["tokens_out"],
        "provider_used": meta["provider_used"] or state.get("provider_used", "unknown"),
        "fallback_events": list(state.get("fallback_events") or []) + meta["fallback_events"],
    }


async def _stream_llm(
    *,
    state: NexusAgentState,
    config: RunnableConfig,
    writer: StreamWriter | None,
    system_prompt: str,
    messages: list[AgentMessage],
    model_id: str,
    event: str | None,
    tools: list[ToolSpec] | None = None,
) -> tuple[str, list[ToolCall], dict]:
    """
    Run one provider call, streaming deltas to `writer` as they arrive.

    `event` is the custom-stream event name to publish each delta under
    (`reasoning` for the plan stage, `token` for user-facing output, None to
    stream nothing -- the critic's JSON is internal and would be noise in the
    chat). Returns (full_text, tool_calls, telemetry).

    Handles the router's `reset` chunk: when a provider dies mid-stream and
    the router falls back, everything accumulated so far is invalid, so the
    local buffer is cleared AND a `stream_reset` is published so the UI drops
    the partial text it already rendered. Without both halves the user ends
    up looking at the aborted attempt's prefix glued onto the replacement
    provider's full response. Tool calls collected from the aborted attempt
    are dropped for the same reason -- executing a dead provider's half-parsed
    calls alongside the replacement's would double-apply side effects.
    """
    db = config["configurable"]["db"]
    tenant_id = config["configurable"]["tenant_id"]

    full_text = ""
    tool_calls: list[ToolCall] = []
    tokens_in = tokens_out = 0
    provider_used = ""
    fallback_log: list[dict] = []

    try:
        async for chunk, provider in route_and_stream(
            db=db,
            tenant_id=tenant_id,
            system_prompt=system_prompt,
            messages=messages,
            model_id=model_id,
            fallback_log=fallback_log,
            tools=tools,
        ):
            if chunk.reset:
                full_text = ""
                tool_calls = []
                if writer and event:
                    writer({"event": "stream_reset", "data": {"scope": event}})
                continue

            full_text += chunk.delta
            provider_used = provider.name
            if chunk.tool_calls:
                tool_calls.extend(chunk.tool_calls)
            if provider.usage:
                tokens_in, tokens_out = provider.usage.tokens_in, provider.usage.tokens_out

            if writer and event and chunk.delta:
                writer({"event": event, "data": {"content": chunk.delta}})
    finally:
        # Emitted in `finally` on purpose. When every provider in the chain
        # fails, the exception propagates and the user would otherwise get a
        # bare "the agent run failed" with no hint that three providers were
        # tried and why -- which is precisely what made the first real failure
        # of this loop hard to diagnose. The toast now lands either way.
        if writer:
            for fb in fallback_log:
                writer({"event": "provider_fallback", "data": fb})

    return full_text, tool_calls, {
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "provider_used": provider_used,
        "fallback_events": fallback_log,
    }


def _latest_user_request(state: NexusAgentState) -> str:
    for message in reversed(state.get("messages") or []):
        if message.get("role") == "user":
            return message.get("content", "")
    return ""


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


async def plan_node(state: NexusAgentState, config: RunnableConfig, writer: StreamWriter) -> dict:
    """
    Decide how to approach this turn before answering it.

    `db` and `tenant_id` come from config["configurable"], not state -- state
    gets checkpointed (Postgres-serialized) and a live DB connection cannot
    survive that round-trip. See agent_stream.py for where these are set.
    """
    if writer:
        writer({"event": "stage", "data": {"stage": "planning"}})

    system_prompt = build_planner_prompt(
        state["current_phase"], state["mode"], state.get("context_digest", "")
    )
    text, _calls, meta = await _stream_llm(
        state=state,
        config=config,
        writer=writer,
        system_prompt=system_prompt,
        messages=state.get("messages") or [],
        model_id=state["model_id"],
        event="reasoning",
    )

    plan = parse_json_object(text)
    if plan is None:
        # Fail open: a plan that would not parse is not worth failing the
        # user's turn over. Execution just proceeds unplanned, exactly as it
        # did before this pipeline existed.
        logger.warning(
            "Planner returned unparseable JSON for session %s phase %s; proceeding without a plan",
            state.get("session_id"),
            state.get("current_phase"),
        )
        plan = {}

    return {"plan": plan, **_accumulate(state, meta)}


async def execute_node(state: NexusAgentState, config: RunnableConfig, writer: StreamWriter) -> dict:
    """
    The ReAct loop: reason -> act -> observe -> repeat, until the model stops
    asking for tools or hits the step ceiling.

    On the agentic phases the model is handed real tools (write_file,
    read_file, list_files, run_command) and its tool calls are actually
    executed -- files land on disk and in the DB, commands run in the sandbox,
    and the real exit codes and stderr come back as observations. That is the
    difference between an agent and a chat that emits code blocks: when the
    model says "the tests pass", something ran the tests.

    On the conversational phases (discussion/explain/practice/quiz) no tools
    are offered at all and this collapses to exactly one call, because
    offering tools changes how a model answers even when it uses none.

    The loop accumulates into `scratch`, a turn-local transcript of assistant
    turns and tool observations. It is NOT written back into `messages`: that
    is rebuilt from the DB every turn (see state.py), so appending here would
    be discarded at best and would corrupt the persisted conversation at worst.
    What survives the turn is the final prose plus the file/command side
    effects the tools actually performed.
    """
    attempts = state.get("attempts", 0) + 1
    revision_notes = state.get("revision_notes", "")
    phase = state["current_phase"]
    phase_tools = PHASE_TOOLS.get(phase)
    use_tools = phase_tools is not None
    can_execute = phase_tools is FULL_TOOL_SPECS

    if writer:
        writer({"event": "stage", "data": {"stage": "revising" if revision_notes else "answering"}})
        if revision_notes:
            # The user has already seen the rejected draft render. Clear it
            # before the corrected answer streams in over the top.
            writer({"event": "stream_reset", "data": {"scope": "token"}})

    system_prompt = system_prompt_for_phase(
        phase,
        state["mode"],
        state.get("context_digest", ""),
        plan=state.get("plan") or None,
        revision_notes=revision_notes,
        tools_available=use_tools,
        can_execute=can_execute,
    )

    # Seeded from prior state so a revision pass ADDS to the turn's record
    # rather than replacing it. A revision typically re-reads and re-runs
    # without rewriting, so a fresh context would report "no files touched"
    # for a turn that wrote several -- the route would then emit no
    # file_written events and the Files panel would never learn they exist.
    ctx = ToolContext(
        session_id=state["session_id"],
        db=config["configurable"]["db"],
        touched_paths=set(state.get("touched_paths") or []),
        ran_command=bool(state.get("ran_command")),
    )
    base_messages: list[AgentMessage] = list(state.get("messages") or [])
    scratch: list[AgentMessage] = []

    final_text = ""
    # Step count and trace also carry across attempts: the turn's total budget
    # is what matters, and the critic needs to see everything that happened
    # this turn, not just what the latest pass did.
    steps = state.get("tool_steps", 0)
    tool_trace: list[dict] = list(state.get("tool_trace") or [])
    telemetry = {"tokens_in": 0, "tokens_out": 0, "provider_used": "", "fallback_events": []}
    # True once the model has been told it is out of steps. It gets exactly
    # one more call to write a closing summary; if it asks for tools again on
    # that call we stop regardless. Without this latch a model that ignores
    # the stop notice loops forever -- the ceiling would bound tool
    # *execution* while leaving LLM calls unbounded, which is the expensive
    # half.
    stop_notice_sent = False

    while True:
        text, calls, meta = await _stream_llm(
            state=state,
            config=config,
            writer=writer,
            system_prompt=system_prompt,
            messages=base_messages + scratch,
            model_id=state["model_id"],
            event="token",
            tools=phase_tools,
        )

        # Telemetry is summed across every step of the loop, not just the last.
        telemetry = {
            "tokens_in": telemetry["tokens_in"] + meta["tokens_in"],
            "tokens_out": telemetry["tokens_out"] + meta["tokens_out"],
            "provider_used": meta["provider_used"] or telemetry["provider_used"],
            "fallback_events": telemetry["fallback_events"] + meta["fallback_events"],
        }
        if text:
            final_text = text

        if not calls:
            break

        if stop_notice_sent:
            # It was already told to stop and asked for tools anyway. End the
            # turn on whatever prose it produced rather than negotiating.
            logger.warning(
                "session %s kept calling tools after the stop notice; ending turn",
                state.get("session_id"),
            )
            break

        steps += 1
        if steps > MAX_TOOL_STEPS:
            # Stop cleanly rather than looping on the user's budget. The model
            # is told so it can summarize honestly instead of the turn just
            # ending mid-thought.
            logger.warning(
                "session %s hit the %d-step tool ceiling in phase %s",
                state.get("session_id"), MAX_TOOL_STEPS, phase,
            )
            stop_notice_sent = True
            scratch.append({"role": "assistant", "content": text, "tool_calls": calls})
            scratch.append({"role": "tool", "tool_results": [
                ToolResult(
                    call_id=c.id, name=c.name,
                    content=(
                        f"Stopped: this turn reached its limit of {MAX_TOOL_STEPS} tool steps. "
                        "Do not call any more tools. Summarize what you accomplished, what is "
                        "still unfinished, and what you would do next."
                    ),
                    is_error=True,
                )
                for c in calls
            ]})
            continue

        if writer:
            writer({"event": "stage", "data": {"stage": "acting"}})
            for call in calls:
                writer({"event": "tool_call", "data": {
                    "id": call.id, "name": call.name, "summary": summarize_call(call), "step": steps,
                }})

        results = await execute_tool_calls(ctx, calls)

        if writer:
            for call, result in zip(calls, results):
                writer({"event": "tool_result", "data": {
                    "id": call.id,
                    "name": call.name,
                    "ok": not result.is_error,
                    # Enough for the UI's activity trace; the model gets it all.
                    "preview": result.content[:400],
                    "step": steps,
                }})

        scratch.append({"role": "assistant", "content": text, "tool_calls": calls})
        scratch.append({"role": "tool", "tool_results": results})

        # Text produced before a tool call is narration ("let me check the
        # tests"), not the answer. Clear the rendered buffer so the user ends
        # up reading the model's final summary rather than a pile of asides.
        if writer and text:
            writer({"event": "stream_reset", "data": {"scope": "token"}})
        final_text = ""

        tool_trace.extend(
            {"name": c.name, "summary": summarize_call(c), "ok": not r.is_error, "step": steps}
            for c, r in zip(calls, results)
        )

    return {
        "phase_output": final_text,
        "attempts": attempts,
        "tool_steps": steps,
        "tool_trace": tool_trace,
        "touched_paths": sorted(ctx.touched_paths),
        "ran_command": ctx.ran_command,
        # Consumed -- a stale directive must not leak into a later pass.
        "revision_notes": "",
        **_accumulate(state, telemetry),
    }


async def critique_node(state: NexusAgentState, config: RunnableConfig, writer: StreamWriter) -> dict:
    """
    Judge the draft against the plan and the phase's exit criteria, and decide
    whether the phase is complete.

    The critic is shown the tool trace, not just the prose. That is what stops
    it grading a claim: it can see whether a command was actually run and
    whether it exited zero, so "the tests pass" is checkable rather than taken
    on faith.

    Fails open in every failure mode (unparseable verdict, provider error):
    a broken critic must never cost the user an answer that was already
    produced successfully.
    """
    if writer:
        writer({"event": "stage", "data": {"stage": "reviewing"}})

    draft = state.get("phase_output", "")
    plan = state.get("plan") or {}

    try:
        text, _calls, meta = await _stream_llm(
            state=state,
            config=config,
            writer=writer,
            system_prompt=build_critic_prompt(
                state["current_phase"], state["mode"], state.get("context_digest", "")
            ),
            messages=[{"role": "user", "content": build_critic_input(
                plan, draft, _latest_user_request(state),
                tool_trace=state.get("tool_trace") or [],
                ran_command=bool(state.get("ran_command")),
            )}],
            model_id=_CRITIC_MODEL_OVERRIDE or state["model_id"],
            event=None,  # the critic's JSON is internal -- never rendered in chat
        )
    except ProviderError as exc:
        logger.warning(
            "Critic call failed for session %s (%s); accepting draft as-is", state.get("session_id"), exc
        )
        return {"critique": {"approved": True, "issues": [], "phase_complete": False,
                             "reason": "Review stage unavailable."},
                "should_advance_phase": False}

    verdict = parse_json_object(text)
    if verdict is None:
        logger.warning(
            "Critic returned unparseable JSON for session %s; accepting draft as-is", state.get("session_id")
        )
        verdict = {"approved": True, "issues": [], "phase_complete": False,
                   "reason": "Review stage returned no usable verdict."}

    approved = bool(verdict.get("approved", True))
    issues = [str(i) for i in (verdict.get("issues") or []) if i]
    # A rejection with no stated defect gives execute_node nothing to act on,
    # so it would just regenerate at random. Treat it as an approval.
    if not approved and not issues:
        logger.info("Critic rejected without citing issues for session %s; treating as approved",
                    state.get("session_id"))
        approved = True

    critique = {
        "approved": approved,
        "issues": issues,
        "phase_complete": bool(verdict.get("phase_complete", False)),
        "reason": str(verdict.get("reason", "")),
    }

    will_retry = not approved and state.get("attempts", 0) < MAX_ATTEMPTS
    if writer:
        writer({"event": "critique", "data": {
            "approved": approved,
            "issues": issues,
            "phase_complete": critique["phase_complete"],
            "reason": critique["reason"],
            "revising": will_retry,
        }})

    return {
        "critique": critique,
        "revision_notes": build_revision_directive(issues, draft) if will_retry else "",
        # Only a draft that actually passed review may close out a phase.
        "should_advance_phase": approved and critique["phase_complete"],
        **_accumulate(state, meta),
    }


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


# Node names deliberately differ from the state keys they write (`planner`
# writes `plan`, `critic` writes `critique`): LangGraph rejects a node whose
# name collides with a state key.
_PLANNER, _EXECUTOR, _CRITIC = "planner", "executor", "critic"


def entry_router(state: NexusAgentState) -> str:
    return _PLANNER if state.get("current_phase") in PLANNED_PHASES else _EXECUTOR


def after_execute(state: NexusAgentState) -> str:
    return _CRITIC if state.get("current_phase") in CRITIQUED_PHASES else END


def after_critique(state: NexusAgentState) -> str:
    """Loop back for one revision pass when the critic found real defects and
    the attempt budget allows it; otherwise the turn is done."""
    critique = state.get("critique") or {}
    if not critique.get("approved", True) and state.get("attempts", 0) < MAX_ATTEMPTS:
        return _EXECUTOR
    return END


def build_graph(checkpointer: BaseCheckpointSaver):
    graph = StateGraph(NexusAgentState)
    graph.add_node(_PLANNER, plan_node)
    graph.add_node(_EXECUTOR, execute_node)
    graph.add_node(_CRITIC, critique_node)

    graph.add_conditional_edges(START, entry_router, {_PLANNER: _PLANNER, _EXECUTOR: _EXECUTOR})
    graph.add_edge(_PLANNER, _EXECUTOR)
    graph.add_conditional_edges(_EXECUTOR, after_execute, {_CRITIC: _CRITIC, END: END})
    graph.add_conditional_edges(_CRITIC, after_critique, {_EXECUTOR: _EXECUTOR, END: END})

    return graph.compile(checkpointer=checkpointer)


_compiled_graph = None


def init_graph(checkpointer: BaseCheckpointSaver) -> None:
    """Called once from app startup (see app/main.py lifespan). The
    Postgres-backed checkpointer needs an async pool opened once and closed on
    shutdown, and that lifecycle has to live at the app level rather than in a
    lazily-built module singleton with no shutdown hook."""
    global _compiled_graph
    _compiled_graph = build_graph(checkpointer)


def get_graph():
    if _compiled_graph is None:
        raise RuntimeError(
            "Graph not initialized -- init_graph() must run during app startup "
            "(see app/main.py lifespan). This should never happen outside tests "
            "that skip the lifespan; if you're writing a test, call init_graph() "
            "with a MemorySaver() first."
        )
    return _compiled_graph
