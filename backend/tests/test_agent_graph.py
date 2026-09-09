"""
Tests for the plan -> execute -> critique -> (revise) reasoning graph.

These drive the compiled graph directly against a fake provider stream
rather than going through the HTTP route, so each behaviour is pinned
without needing a real model or a live DB:

  - the conversational phases stay a single call (no plan/critique tax)
  - the artifact phases plan, answer, and review
  - a rejected draft is revised exactly once, and the revision replaces the
    rejected text rather than appending to it
  - a provider dying mid-stream discards its partial output instead of
    concatenating it onto the fallback provider's answer
  - token counters are per-turn absolutes, not values that keep climbing
    across turns via the checkpointer
"""
import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.agents import graph as graph_mod
from app.agents.providers.base import StreamChunk


class FakeProvider:
    def __init__(self, name="fake", tokens_in=10, tokens_out=20):
        self.name = name
        self.usage = type("U", (), {"tokens_in": tokens_in, "tokens_out": tokens_out})()


def scripted_router(responses):
    """Builds a route_and_stream stand-in that yields the next scripted
    response per call. Each response is a list of StreamChunks."""
    calls = {"n": 0, "prompts": []}

    async def _route_and_stream(*, system_prompt, messages, model_id, fallback_log=None, **_):
        idx = calls["n"]
        calls["n"] += 1
        calls["prompts"].append(system_prompt)
        provider = FakeProvider()
        for chunk in responses[idx]:
            yield chunk, provider

    return _route_and_stream, calls


def text_chunks(*parts):
    return [StreamChunk(delta=p) for p in parts]


def base_state(phase, **overrides):
    state = {
        "messages": [{"role": "user", "content": "build me a thing"}],
        "session_id": "s1", "mode": "development", "current_phase": phase,
        "model_id": "claude-sonnet-4-6", "context_digest": "",
        "attempts": 0, "tokens_in": 0, "tokens_out": 0,
        "fallback_events": [], "revision_notes": "", "plan": {}, "critique": {},
        "phase_output": "", "should_advance_phase": False,
    }
    state.update(overrides)
    return state


async def run(monkeypatch, phase, responses, **overrides):
    router, calls = scripted_router(responses)
    monkeypatch.setattr(graph_mod, "route_and_stream", router)
    compiled = graph_mod.build_graph(MemorySaver())
    config = {"configurable": {"thread_id": "t1", "db": None, "tenant_id": "tenant1"}}

    custom_events = []
    final = {}
    async for mode, payload in compiled.astream(
        base_state(phase, **overrides), config=config, stream_mode=["custom", "values"]
    ):
        if mode == "custom":
            custom_events.append(payload)
        else:
            final = payload
    return final, custom_events, calls


@pytest.mark.asyncio
async def test_conversational_phase_is_a_single_call(monkeypatch):
    """A purely conversational phase (discussion) must not pay the
    plan+critique tax -- one provider call only. (Ideation used to be this
    test's example, but it now converges on and writes a confirmed IDEA.md,
    so it earns the same plan->critique structure as the artifact phases --
    see PLANNED_PHASES/CRITIQUED_PHASES in graph.py.)"""
    final, events, calls = await run(monkeypatch, "discussion", [text_chunks("here are ", "three ideas")])

    assert calls["n"] == 1
    assert final["phase_output"] == "here are three ideas"
    assert final["attempts"] == 1
    assert [e["event"] for e in events if e["event"] == "reasoning"] == []
    assert final["tokens_in"] == 10 and final["tokens_out"] == 20


@pytest.mark.asyncio
async def test_implementation_plans_answers_and_reviews(monkeypatch):
    final, events, calls = await run(
        monkeypatch, "implementation",
        [
            text_chunks('{"goal": "write the API", "steps": ["route", "model"]}'),
            text_chunks("```py\n// app/main.py\nprint(1)\n```"),
            text_chunks('{"approved": true, "issues": [], "phase_complete": true, "reason": "spec met"}'),
        ],
    )

    assert calls["n"] == 3
    assert final["plan"]["goal"] == "write the API"
    assert final["critique"]["approved"] is True
    assert final["should_advance_phase"] is True
    assert final["attempts"] == 1
    # Three calls, but only the answer is rendered as chat text; the plan
    # streams as `reasoning` and the critic's JSON is never streamed at all.
    assert "".join(e["data"]["content"] for e in events if e["event"] == "token") == final["phase_output"]
    assert any(e["event"] == "reasoning" for e in events)
    assert [e["data"]["stage"] for e in events if e["event"] == "stage"] == ["planning", "answering", "reviewing"]
    # Token counters sum across all three calls.
    assert final["tokens_in"] == 30 and final["tokens_out"] == 60


@pytest.mark.asyncio
async def test_rejected_draft_is_revised_once_and_replaces_the_draft(monkeypatch):
    final, events, calls = await run(
        monkeypatch, "implementation",
        [
            text_chunks('{"goal": "g", "steps": ["s"]}'),
            text_chunks("BAD DRAFT"),
            text_chunks('{"approved": false, "issues": ["missing error handling"], "phase_complete": false}'),
            text_chunks("GOOD DRAFT"),
            text_chunks('{"approved": true, "issues": [], "phase_complete": true, "reason": "fixed"}'),
        ],
    )

    assert calls["n"] == 5
    assert final["phase_output"] == "GOOD DRAFT"
    assert final["attempts"] == 2
    assert final["should_advance_phase"] is True
    # The rejected draft was rendered, so the UI must be told to clear it
    # before the revision streams in -- otherwise the user reads
    # "BAD DRAFTGOOD DRAFT".
    assert any(e["event"] == "stream_reset" and e["data"]["scope"] == "token" for e in events)
    assert [e["data"]["stage"] for e in events if e["event"] == "stage"] == [
        "planning", "answering", "reviewing", "revising", "reviewing",
    ]
    # The critic's specific defect AND the draft being fixed were both fed
    # back into the revision prompt -- without the draft the reviser rerolls
    # blind instead of revising.
    assert "missing error handling" in calls["prompts"][3]
    assert "BAD DRAFT" in calls["prompts"][3]


@pytest.mark.asyncio
async def test_revision_loop_is_bounded(monkeypatch):
    """A critic that never approves must not loop forever on the user's dime."""
    rejection = text_chunks('{"approved": false, "issues": ["still wrong"], "phase_complete": false}')
    final, _, calls = await run(
        monkeypatch, "implementation",
        [
            text_chunks('{"goal": "g"}'),
            text_chunks("draft one"), rejection,
            text_chunks("draft two"), rejection,
        ],
    )

    assert final["attempts"] == graph_mod.MAX_ATTEMPTS == 2
    assert calls["n"] == 5  # plan + 2x(execute+critique), then it stops
    assert final["should_advance_phase"] is False


@pytest.mark.asyncio
async def test_midstream_provider_failure_discards_partial_output(monkeypatch):
    """The router's reset chunk must clear the accumulator, so the fallback
    provider's answer replaces the aborted attempt instead of being glued
    onto its prefix."""
    final, events, _ = await run(
        monkeypatch, "discussion",
        [[
            StreamChunk(delta="Here is the pl"),
            StreamChunk(delta="", reset=True),
            StreamChunk(delta="A complete answer from the fallback."),
        ]],
    )

    assert final["phase_output"] == "A complete answer from the fallback."
    assert "Here is the pl" not in final["phase_output"]
    # The client rendered the aborted prefix, so it is told to drop it too.
    assert any(e["event"] == "stream_reset" for e in events)


@pytest.mark.asyncio
async def test_unparseable_plan_and_critique_fail_open(monkeypatch):
    """A malformed internal artifact must never cost the user their answer."""
    final, _, calls = await run(
        monkeypatch, "implementation",
        [
            text_chunks("I'm afraid I can't do that."),   # planner, no JSON
            text_chunks("the real answer"),
            text_chunks("looks good to me!"),             # critic, no JSON
        ],
    )

    assert calls["n"] == 3
    assert final["plan"] == {}
    assert final["phase_output"] == "the real answer"
    assert final["critique"]["approved"] is True       # fail open, not a retry
    assert final["should_advance_phase"] is False      # but never advances on a non-verdict


@pytest.mark.asyncio
async def test_rejection_without_issues_is_treated_as_approval(monkeypatch):
    """A rejection citing no defect gives the executor nothing to act on, so
    retrying would just reroll at random."""
    final, _, calls = await run(
        monkeypatch, "implementation",
        [
            text_chunks('{"goal": "g"}'),
            text_chunks("an answer"),
            text_chunks('{"approved": false, "issues": [], "phase_complete": false}'),
        ],
    )

    assert calls["n"] == 3          # no revision pass
    assert final["critique"]["approved"] is True
    assert final["attempts"] == 1


@pytest.mark.asyncio
async def test_counters_reset_across_turns_on_the_same_thread(monkeypatch):
    """Regression: with an accumulating reducer, turn two's counters would be
    added to turn one's checkpointed values instead of replacing them, and
    history would be re-appended to itself every turn."""
    router, calls = scripted_router([
        text_chunks("first answer"),
        text_chunks("second answer"),
    ])
    monkeypatch.setattr(graph_mod, "route_and_stream", router)
    compiled = graph_mod.build_graph(MemorySaver())
    config = {"configurable": {"thread_id": "same-thread", "db": None, "tenant_id": "t"}}

    turn1 = await compiled.ainvoke(base_state("discussion"), config=config)
    assert turn1["tokens_in"] == 10 and turn1["attempts"] == 1
    assert len(turn1["messages"]) == 1

    history = [
        {"role": "user", "content": "build me a thing"},
        {"role": "assistant", "content": "first answer"},
        {"role": "user", "content": "now change it"},
    ]
    turn2 = await compiled.ainvoke(base_state("discussion", messages=history), config=config)

    # Counters are this turn's totals, not turn one's plus turn two's.
    assert turn2["tokens_in"] == 10 and turn2["tokens_out"] == 20
    assert turn2["attempts"] == 1
    # History is exactly what the DB supplied -- not the checkpoint's copy
    # with the DB's copy appended to it.
    assert turn2["messages"] == history
