"""
LangGraph StateGraph replacing the old static `workerForPhase()` lookup.

Structure: a single `run_phase` node executes the current phase's system
prompt against the conversation, then `route_next` decides whether to
advance to the next phase (END for this turn either way — phase advance
is persisted and picked up on the session's next incoming message, since
each HTTP/SSE turn is one graph invocation, not a fully autonomous loop).

An iteration cap (`iterations`) prevents any future extension of this
graph — e.g. adding a self-critique loop between implementation and
review — from looping unboundedly, per the anti-pattern in the langgraph
skill.

Checkpointer is injected via `init_graph()` at app startup (see
app/main.py lifespan) rather than built lazily here, because the
Postgres-backed checkpointer needs an async connection pool opened once
and closed on shutdown — that lifecycle has to live at the app level, not
inside a module-level singleton that has no shutdown hook.
"""
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.agents.constants import PHASE_TRANSITIONS
from app.agents.prompts import system_prompt_for_phase
from app.agents.providers.router import route_and_stream
from app.agents.state import NexusAgentState

MAX_ITERATIONS = 6


async def run_phase_node(state: NexusAgentState, config: RunnableConfig) -> dict:
    """
    `db` and `tenant_id` come from config["configurable"], not state --
    state gets checkpointed (in-memory now, Postgres-serialized once
    USE_POSTGRES_CHECKPOINTER is on), and a live DB connection can't
    survive that round-trip. See agent_stream.py for where these are set.
    """
    db = config["configurable"]["db"]
    tenant_id = config["configurable"]["tenant_id"]

    system_prompt = system_prompt_for_phase(state["current_phase"], state["mode"], state.get("context_digest", ""))
    history = [{"role": m.type if hasattr(m, "type") else m["role"],
                "content": m.content if hasattr(m, "content") else m["content"]}
               for m in state["messages"]]
    # LangChain message .type is "human"/"ai"; providers expect "user"/"assistant".
    role_map = {"human": "user", "ai": "assistant"}
    history = [{"role": role_map.get(m["role"], m["role"]), "content": m["content"]} for m in history]

    full_text = ""
    tokens_in = tokens_out = 0
    provider_used = "unknown"
    fallback_log: list[dict] = []

    async for chunk, provider in route_and_stream(
        db=db, tenant_id=tenant_id, system_prompt=system_prompt, messages=history,
        model_id=state["model_id"], fallback_log=fallback_log,
    ):
        full_text += chunk.delta
        provider_used = provider.name
        if provider.usage:
            tokens_in, tokens_out = provider.usage.tokens_in, provider.usage.tokens_out

    return {
        "messages": [{"role": "assistant", "content": full_text}],
        "phase_output": full_text,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "provider_used": provider_used,
        "iterations": state.get("iterations", 0) + 1,
        "fallback_events": fallback_log,
    }


def route_next(state: NexusAgentState) -> str:
    if state.get("iterations", 0) >= MAX_ITERATIONS:
        return END
    return END  # each API turn is one pass; explicit phase-advance is a separate endpoint


def build_graph(checkpointer: BaseCheckpointSaver):
    graph = StateGraph(NexusAgentState)
    graph.add_node("run_phase", run_phase_node)
    graph.add_edge(START, "run_phase")
    graph.add_conditional_edges("run_phase", route_next, {END: END})
    return graph.compile(checkpointer=checkpointer)


_compiled_graph = None


def init_graph(checkpointer: BaseCheckpointSaver) -> None:
    """Called once from app startup (see app/main.py lifespan)."""
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


def next_phase(current_phase: str) -> str | None:
    return PHASE_TRANSITIONS.get(current_phase)