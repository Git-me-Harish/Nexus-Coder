from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class NexusAgentState(TypedDict):
    """
    Graph state for one agent turn. `messages` accumulates via the
    add_messages reducer (append, don't overwrite) — everything else
    overwrites per-turn since it's recomputed each pass.
    """
    messages: Annotated[list, add_messages]
    session_id: str
    mode: str                 # development | problem_solving | learning
    current_phase: str        # ideation | specification | implementation | review
    model_id: str
    context_digest: str       # confirmed spec + prior-phase summary -- see app/agents/prompts.py
    phase_output: str         # this turn's generated text
    should_advance_phase: bool
    tokens_in: int
    tokens_out: int
    provider_used: str
    iterations: int
    fallback_events: list[dict]  # populated when the provider router had to fall back