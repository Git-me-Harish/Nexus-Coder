"""
The ReAct loop: reason -> act -> observe -> repeat.

These drive the compiled graph against a scripted provider so the loop's
control flow is pinned without spending money or depending on a model's
mood. Tool execution itself is REAL -- files are actually written to a tmp
workspace -- because the whole point of the loop is that side effects happen;
a test that stubs the tools would be testing nothing.

`run_command` is the one thing not exercised here: it needs Docker, so it
lives in test_sandbox.py behind a skip-if-unavailable guard.
"""
import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.agents import graph as graph_mod
from app.agents import workspace
from app.agents.providers.base import StreamChunk, ToolCall

SID = "reactsession"


@pytest.fixture(autouse=True)
def isolated_workspace(tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "workspace_root", str(tmp_path), raising=False)
    yield
    workspace.destroy_workspace(SID)


def scripted(turns):
    """Each entry is (text, [ToolCall]) -- one model turn."""
    calls = {"n": 0, "tools_seen": [], "messages_seen": []}

    async def _route_and_stream(*, system_prompt, messages, model_id, fallback_log=None, tools=None, **_):
        index = calls["n"]
        calls["n"] += 1
        calls["tools_seen"].append([t.name for t in tools] if tools else None)
        calls["messages_seen"].append(messages)

        text, tool_calls = turns[index]
        provider = type("P", (), {
            "name": "fake",
            "usage": type("U", (), {"tokens_in": 5, "tokens_out": 7})(),
        })()
        if text:
            yield StreamChunk(delta=text), provider
        yield StreamChunk(finished=True, tool_calls=tool_calls), provider

    return _route_and_stream, calls


def base_state(phase, **overrides):
    state = {
        "messages": [{"role": "user", "content": "build a thing"}],
        "session_id": SID, "mode": "development", "current_phase": phase,
        "model_id": "claude-sonnet-5", "context_digest": "",
        "attempts": 0, "tokens_in": 0, "tokens_out": 0, "fallback_events": [],
        "revision_notes": "", "plan": {}, "critique": {}, "phase_output": "",
        "should_advance_phase": False, "tool_steps": 0, "tool_trace": [],
        "touched_paths": [], "ran_command": False,
    }
    state.update(overrides)
    return state


async def run(monkeypatch, phase, turns, db=None, **overrides):
    router, calls = scripted(turns)
    monkeypatch.setattr(graph_mod, "route_and_stream", router)
    compiled = graph_mod.build_graph(MemorySaver())
    config = {"configurable": {"thread_id": "t", "db": db, "tenant_id": "tn"}}

    events, final = [], {}
    async for mode, payload in compiled.astream(
        base_state(phase, **overrides), config=config, stream_mode=["custom", "values"]
    ):
        (events.append(payload) if mode == "custom" else None)
        if mode != "custom":
            final = payload
    return final, events, calls


def tc(id_, name, **args):
    return ToolCall(id=id_, name=name, arguments=args)


# --- tool availability ------------------------------------------------------


@pytest.mark.asyncio
async def test_conversational_phases_are_offered_no_tools(monkeypatch):
    """Offering tools changes how a model answers even when it uses none --
    purely conversational phases (discussion/explain/practice/quiz) get
    nothing to call. (Ideation used to be this test's example, but it now
    writes a confirmed IDEA.md, so it's a doc-tools phase -- see the test
    below.)"""
    _, _, calls = await run(monkeypatch, "discussion", [("here's my take", [])])
    assert calls["tools_seen"] == [None]


@pytest.mark.asyncio
async def test_doc_phases_get_file_tools_but_not_run_command(monkeypatch):
    """Ideation/planning/specification produce workspace artifacts (IDEA.md/
    PLAN.md/SPEC.md) but there's no code yet to execute -- they get
    write_file/read_file/list_files and deliberately NOT run_command."""
    for phase in ("ideation", "planning", "specification"):
        _, _, calls = await run(
            monkeypatch, phase,
            [
                ('{"goal": "g"}', []),   # planner
                ("done", []),             # executor
                ('{"approved": true, "phase_complete": false}', []),  # critic
            ],
        )
        assert calls["tools_seen"][0] is None, f"the planner reasons, it does not act ({phase})"
        assert set(calls["tools_seen"][1]) == {"write_file", "read_file", "list_files"}, phase
        assert calls["tools_seen"][2] is None, f"the critic judges, it does not act ({phase})"


@pytest.mark.asyncio
async def test_agentic_phases_are_offered_real_tools(monkeypatch):
    """Implementation/debug/review get the full set, run_command included --
    verifying real behavior is the point of these phases."""
    for phase in ("implementation", "debug", "review"):
        _, _, calls = await run(
            monkeypatch, phase,
            [
                ('{"goal": "g"}', []),          # planner -- never gets tools
                ("done", []),                    # executor
                ('{"approved": true, "phase_complete": false}', []),  # critic
            ],
        )
        assert calls["tools_seen"][0] is None, f"the planner reasons, it does not act ({phase})"
        assert set(calls["tools_seen"][1]) == {"write_file", "read_file", "list_files", "run_command"}, phase
        assert calls["tools_seen"][2] is None, f"the critic judges, it does not act ({phase})"


# --- the loop ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_call_actually_writes_a_real_file(monkeypatch, db_session):
    """The defining behaviour: a tool call has a real side effect on disk."""
    final, events, calls = await run(
        monkeypatch, "implementation",
        [
            ('{"goal": "write app"}', []),
            ("creating the file", [tc("t1", "write_file", path="app.py", content="print('hi')")]),
            ("Created app.py.", []),
            ('{"approved": true, "issues": [], "phase_complete": true, "reason": "done"}', []),
        ],
        db=db_session,
    )

    assert await workspace.read_file(SID, "app.py") == "print('hi')"
    assert final["touched_paths"] == ["app.py"]
    assert final["tool_steps"] == 1
    assert final["phase_output"] == "Created app.py."
    assert [t["name"] for t in final["tool_trace"]] == ["write_file"]
    assert all(t["ok"] for t in final["tool_trace"])


@pytest.mark.asyncio
async def test_observations_are_fed_back_to_the_model(monkeypatch, db_session):
    """The 'observe' half of ReAct: the model must see what its tool returned."""
    await workspace.write_file(SID, "existing.py", "SECRET_MARKER = 42")

    final, _, calls = await run(
        monkeypatch, "implementation",
        [
            ('{"goal": "read it"}', []),
            ("", [tc("t1", "read_file", path="existing.py")]),
            ("The file defines SECRET_MARKER.", []),
            ('{"approved": true, "phase_complete": false}', []),
        ],
        db=db_session,
    )

    # The third provider call (index 2) is the one after the tool ran; its
    # message list must contain the tool's real output.
    followup = calls["messages_seen"][2]
    tool_turns = [m for m in followup if m.get("role") == "tool"]
    assert tool_turns, "the tool result was never sent back to the model"
    assert "SECRET_MARKER = 42" in tool_turns[0]["tool_results"][0].content


@pytest.mark.asyncio
async def test_multi_step_loop_runs_until_the_model_stops_asking(monkeypatch, db_session):
    final, events, calls = await run(
        monkeypatch, "implementation",
        [
            ('{"goal": "multi"}', []),
            ("", [tc("t1", "write_file", path="a.py", content="a")]),
            ("", [tc("t2", "write_file", path="b.py", content="b")]),
            ("", [tc("t3", "list_files")]),
            ("Built both files.", []),
            ('{"approved": true, "phase_complete": true, "reason": "ok"}', []),
        ],
        db=db_session,
    )

    assert final["tool_steps"] == 3
    assert final["touched_paths"] == ["a.py", "b.py"]
    assert final["phase_output"] == "Built both files."
    assert await workspace.read_file(SID, "b.py") == "b"


@pytest.mark.asyncio
async def test_loop_is_bounded_so_a_stuck_model_cannot_burn_the_budget(monkeypatch, db_session):
    """A model that keeps calling tools forever must be stopped, and told, so
    it can summarize instead of the turn just ending mid-thought."""
    monkeypatch.setattr(graph_mod, "MAX_TOOL_STEPS", 3)

    # A model that NEVER stops asking for tools -- the pathological case.
    turns = [('{"goal": "loop"}', [])]
    turns += [("", [tc(f"t{i}", "list_files")]) for i in range(20)]
    turns += [('{"approved": true, "phase_complete": false}', [])]

    final, _, calls = await run(monkeypatch, "implementation", turns, db=db_session)

    assert final["tool_steps"] == 4, "one step past the ceiling is where execution stops"
    # The ceiling must bound LLM calls too, not just tool execution: planner +
    # 4 executor calls + 1 post-notice call + critic. Without the stop latch
    # this loops until the script runs dry.
    assert calls["n"] == 7

    # The stop is communicated as a tool observation, not silence, so the
    # model can close out honestly.
    stop_notices = [
        r for msgs in calls["messages_seen"] for m in msgs if m.get("role") == "tool"
        for r in m.get("tool_results", []) if "reached its limit" in r.content
    ]
    assert stop_notices


@pytest.mark.asyncio
async def test_a_failing_tool_becomes_an_observation_not_a_crash(monkeypatch, db_session):
    """A bad path must come back as something the model can correct, rather
    than killing the user's turn."""
    final, _, calls = await run(
        monkeypatch, "implementation",
        [
            ('{"goal": "oops"}', []),
            ("", [tc("t1", "read_file", path="../../../etc/passwd")]),
            ("That path was outside the workspace; I'll stay inside it.", []),
            ('{"approved": true, "phase_complete": false}', []),
        ],
        db=db_session,
    )

    assert final["phase_output"].startswith("That path was outside")
    assert final["tool_trace"][0]["ok"] is False
    results = [
        r for m in calls["messages_seen"][2] if m.get("role") == "tool"
        for r in m.get("tool_results", [])
    ]
    assert results[0].is_error and "escapes the workspace" in results[0].content


@pytest.mark.asyncio
async def test_unknown_tool_is_reported_back_to_the_model(monkeypatch, db_session):
    final, _, calls = await run(
        monkeypatch, "implementation",
        [
            ('{"goal": "x"}', []),
            ("", [tc("t1", "delete_everything", target="/")]),
            ("That tool does not exist.", []),
            ('{"approved": true, "phase_complete": false}', []),
        ],
        db=db_session,
    )
    results = [
        r for m in calls["messages_seen"][2] if m.get("role") == "tool"
        for r in m.get("tool_results", [])
    ]
    assert results[0].is_error and "unknown tool" in results[0].content


# --- streaming contract -----------------------------------------------------


@pytest.mark.asyncio
async def test_ui_sees_each_tool_call_and_its_result(monkeypatch, db_session):
    _, events, _ = await run(
        monkeypatch, "implementation",
        [
            ('{"goal": "x"}', []),
            ("", [tc("t1", "write_file", path="x.py", content="1")]),
            ("Done.", []),
            ('{"approved": true, "phase_complete": false}', []),
        ],
        db=db_session,
    )

    kinds = [e["event"] for e in events]
    assert "tool_call" in kinds and "tool_result" in kinds
    assert "acting" in [e["data"].get("stage") for e in events if e["event"] == "stage"]

    call_event = next(e for e in events if e["event"] == "tool_call")
    assert call_event["data"]["summary"] == "write_file(x.py)"
    result_event = next(e for e in events if e["event"] == "tool_result")
    assert result_event["data"]["ok"] is True


@pytest.mark.asyncio
async def test_narration_before_a_tool_call_is_cleared_from_the_answer(monkeypatch, db_session):
    """'Let me check the tests...' is an aside, not the answer. The user should
    be left reading the final summary, not a pile of narration."""
    final, events, _ = await run(
        monkeypatch, "implementation",
        [
            ('{"goal": "x"}', []),
            ("Let me write that file...", [tc("t1", "write_file", path="x.py", content="1")]),
            ("I created x.py.", []),
            ('{"approved": true, "phase_complete": false}', []),
        ],
        db=db_session,
    )

    assert final["phase_output"] == "I created x.py."
    assert "Let me write that file" not in final["phase_output"]
    assert any(
        e["event"] == "stream_reset" and e["data"]["scope"] == "token" for e in events
    ), "the UI was never told to drop the narration it had already rendered"


# --- the critic sees evidence ----------------------------------------------


@pytest.mark.asyncio
async def test_revision_pass_keeps_the_first_attempt_s_record(monkeypatch, db_session):
    """
    Regression from a real end-to-end run: the critic rejected, the revision
    pass only re-read and re-ran (no new writes), and a fresh ToolContext
    reported `touched_paths: []` for a turn that had written two files. The
    route then emitted no file_written events and the Files panel never
    learned they existed.
    """
    final, _, _ = await run(
        monkeypatch, "implementation",
        [
            ('{"goal": "x"}', []),
            ("", [tc("t1", "write_file", path="app.py", content="v1")]),
            ("Wrote app.py.", []),
            ('{"approved": false, "issues": ["explain it better"], "phase_complete": false}', []),
            # The revision only re-reads -- it writes nothing new.
            ("", [tc("t2", "read_file", path="app.py")]),
            ("I wrote app.py, which does X.", []),
            ('{"approved": true, "issues": [], "phase_complete": true, "reason": "ok"}', []),
        ],
        db=db_session,
    )

    assert final["touched_paths"] == ["app.py"], "the first attempt's writes were forgotten"
    assert final["tool_steps"] == 2, "step budget must span the whole turn"
    assert [t["name"] for t in final["tool_trace"]] == ["write_file", "read_file"]


@pytest.mark.asyncio
async def test_ran_command_is_remembered_across_a_revision(monkeypatch, db_session):
    """`ran_command` is what tells the critic a claim is checkable; losing it
    on revision makes verified work look unverified."""
    final, _, _ = await run(
        monkeypatch, "implementation",
        [
            ('{"goal": "x"}', []),
            ("", [tc("t1", "list_files")]),
            ("Looked around.", []),
            ('{"approved": true, "issues": [], "phase_complete": false}', []),
        ],
        db=db_session,
        ran_command=True,  # a previous attempt this turn had run something
    )
    assert final["ran_command"] is True


@pytest.mark.asyncio
async def test_critic_is_shown_what_actually_ran(monkeypatch, db_session):
    _, _, calls = await run(
        monkeypatch, "implementation",
        [
            ('{"goal": "x"}', []),
            ("", [tc("t1", "write_file", path="x.py", content="1")]),
            ("Wrote it.", []),
            ('{"approved": true, "phase_complete": false}', []),
        ],
        db=db_session,
    )

    critic_input = calls["messages_seen"][-1][0]["content"]
    assert "WHAT THE AGENT ACTUALLY DID" in critic_input
    assert "write_file(x.py)" in critic_input
    assert "no command was ever run" in critic_input, (
        "the critic must be told that nothing was verified, so it does not "
        "take 'it works' on faith"
    )


@pytest.mark.asyncio
async def test_critic_is_told_when_the_agent_did_nothing(monkeypatch, db_session):
    _, _, calls = await run(
        monkeypatch, "implementation",
        [
            ('{"goal": "x"}', []),
            ("Here is the code you asked for: print('hi')", []),
            # Approve, so the turn ends here and the assertion targets this
            # critic call rather than a revision pass's.
            ('{"approved": true, "issues": [], "phase_complete": false}', []),
        ],
        db=db_session,
    )

    critic_input = calls["messages_seen"][-1][0]["content"]
    assert "nothing -- no tools were called" in critic_input
