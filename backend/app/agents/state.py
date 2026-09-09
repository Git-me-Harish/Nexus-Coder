"""
Graph state for one agent turn.

NO REDUCERS, DELIBERATELY. Every field here is plain overwrite semantics,
and that is load-bearing given how this graph is actually invoked.

The route (app/api/v1/routes/agent_stream.py) re-reads the full message
history from Postgres and re-invokes the graph once per HTTP turn, against
a checkpointer keyed on the session's thread_id. Any accumulating reducer
in that arrangement silently diverges from the database:

  - `messages` previously used `add_messages`. Because the route passes
    plain dicts with no `id`, the reducer assigned each a fresh UUID and
    *appended* to what the checkpoint already held, so every turn re-added
    the entire prior conversation. History grew quadratically and the text
    sent to the provider filled up with duplicate copies of earlier turns.
  - the same trap applies to `operator.add` on the token counters,
    `fallback_events`, and `attempts`: the per-turn input would be *added*
    to the checkpointed value instead of replacing it, so counters would
    keep climbing across turns and never reset.

So: the DB is the single source of truth for conversation history, and the
checkpointer exists for durability and inspection, not accumulation. Nodes
that need to accumulate within a turn (token counters, fallback events,
attempt count) read the current value off `state` and return the absolute
result -- see `_accumulate` in app/agents/graph.py. Passing a zeroed value
in the turn's input then correctly resets it.
"""
from typing import TypedDict


class NexusAgentState(TypedDict, total=False):
    # --- turn input (set by the route, never written by a node) ---
    messages: list            # [{"role": "user"|"assistant", "content": str}], full history from DB
    session_id: str
    mode: str                 # development | problem_solving | learning
    current_phase: str        # see DEV_PHASES + the problem_solving/learning phases in constants.py
    model_id: str
    context_digest: str       # confirmed spec + prior-phase summary -- see app/agents/prompts.py

    # --- reasoning pipeline (written by the nodes, in order) ---
    plan: dict                # plan_node's structured plan: goal/steps/risks/success_criteria
    phase_output: str         # execute_node's answer for this turn -- what the user sees
    critique: dict            # critique_node's verdict: approved/issues/phase_complete/reason
    revision_notes: str       # critique issues fed back into execute_node on a retry pass
    attempts: int             # execute→critique cycles used this turn (bounded by MAX_ATTEMPTS)

    # --- ReAct loop results (see AGENTIC_PHASES in graph.py) ---
    # These are the record of what the agent actually DID, as opposed to what
    # it said. critique_node is shown them so it can check claims against
    # real executions, and the route persists them as the turn's audit trail.
    tool_steps: int           # reason→act→observe cycles used (bounded by MAX_TOOL_STEPS)
    tool_trace: list[dict]    # [{name, summary, ok, step}] of every executed call
    touched_paths: list[str]  # workspace files created or modified this turn
    ran_command: bool         # whether anything was actually executed in the sandbox

    # `should_advance_phase` is now genuinely wired: critique_node sets it
    # when the phase's exit criteria are met, and the route applies it
    # through session_service.advance_phase (which still enforces the
    # spec-confirmation approval gate). Previously this field was declared
    # here and written by nobody.
    should_advance_phase: bool

    # --- telemetry ---
    tokens_in: int
    tokens_out: int
    provider_used: str
    fallback_events: list[dict]  # populated when the provider router had to fall back
