"""
The agent's tools: what it can actually DO, as opposed to describe.

These are real. `write_file` writes bytes to a real filesystem, `run_command`
starts a real container and returns its real exit code and stderr. Nothing
here is stubbed -- that is the whole point of the ReAct loop in graph.py: the
model's belief about its code gets checked against what actually happened.

DESIGN NOTES
------------
`ToolContext` carries the session id and DB handle so a tool can write through
to both the filesystem and SessionFile rows in one step. It is passed
explicitly rather than stashed in a global, because tools run concurrently
(see execute_tool_calls) and a module-level "current session" would be a race
waiting to happen.

Every tool returns a plain string: that string is fed straight back to the
model as an observation. So errors are returned, not raised -- a traceback
kills the turn, whereas "no such file: foo.py" is something the model can
read and correct on its next step. The only thing that should ever propagate
out of here is a bug in this file.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import workspace
from app.agents.providers.base import ToolCall, ToolResult, ToolSpec
from app.agents.sandbox import run_in_sandbox
from app.agents.workspace import WorkspaceError

logger = logging.getLogger("nexus.tools")

#: A single tool call gets its own ceiling so one pathological call (a huge
#: file read, a hung container) cannot hold the user's turn open forever.
TOOL_TIMEOUT_SECONDS = 120


@dataclass
class ToolContext:
    session_id: str
    db: AsyncSession
    #: Paths touched this turn, accumulated so the route can emit
    #: `file_written` events and sync them to the DB once, after the loop.
    touched_paths: set[str] = field(default_factory=set)
    #: True once any command has actually executed, so the critic can tell
    #: "the tests pass" from "the model asserts the tests would pass".
    ran_command: bool = False


# ---------------------------------------------------------------------------
# Tool specs -- what the model is told it can do.
#
# Descriptions are written for the model, not for us: they say when to reach
# for the tool, because a vague description is the most common cause of an
# agent that has tools and ignores them.
# ---------------------------------------------------------------------------

_WRITE_FILE = ToolSpec(
    name="write_file",
    description=(
        "Create or overwrite a file in the project workspace. Writes the COMPLETE "
        "file contents -- there is no partial or patch mode, so include the whole "
        "file every time. Use this for every file you produce; do not paste code "
        "into your reply and hope it is saved."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path relative to the project root, e.g. 'src/app.py'.",
            },
            "content": {"type": "string", "description": "Complete contents of the file."},
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    },
)

_READ_FILE = ToolSpec(
    name="read_file",
    description=(
        "Read a file from the workspace. Use this before editing a file you did not "
        "write this turn, so you modify what is actually there instead of what you "
        "assume is there."
    ),
    input_schema={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Path relative to the project root."}},
        "required": ["path"],
        "additionalProperties": False,
    },
)

_LIST_FILES = ToolSpec(
    name="list_files",
    description="List every file currently in the workspace, with sizes. Use it to orient before assuming a layout.",
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
)

_RUN_COMMAND = ToolSpec(
    name="run_command",
    description=(
        "Run a shell command in the project workspace and get back its exit code and "
        "combined stdout/stderr. This is how you VERIFY your work: run the tests, run "
        "the linter, execute the script. Runs in an offline container -- there is no "
        "network, so installing packages will not work. Prefer running tests over "
        "claiming code is correct."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command, e.g. 'python -m pytest -q' or 'node index.js'.",
            }
        },
        "required": ["command"],
        "additionalProperties": False,
    },
)

#: Ideation/planning/specification produce workspace artifacts (IDEA.md,
#: PLAN.md, SPEC.md) but there is nothing to execute yet -- no run_command.
#: Keeping it out isn't just tidiness: offering a tool the phase has no
#: legitimate use for is an invitation to call it anyway (e.g. probing the
#: container before any code exists), and it's one fewer thing the critic
#: has to reason about when judging what "done" looks like for these phases.
DOC_TOOL_SPECS: list[ToolSpec] = [_WRITE_FILE, _READ_FILE, _LIST_FILES]

#: Implementation/debug/review get everything, including execution.
FULL_TOOL_SPECS: list[ToolSpec] = [_WRITE_FILE, _READ_FILE, _LIST_FILES, _RUN_COMMAND]

#: Backward-compatible alias -- existing call sites and tests refer to this
#: name for "the full set".
TOOL_SPECS = FULL_TOOL_SPECS

TOOL_NAMES = {t.name for t in FULL_TOOL_SPECS}


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------


async def _write_file(ctx: ToolContext, args: dict) -> str:
    path = args.get("path")
    content = args.get("content")
    if not isinstance(path, str) or not path:
        return "Error: 'path' is required and must be a string."
    if not isinstance(content, str):
        return "Error: 'content' is required and must be a string."

    await workspace.write_file(ctx.session_id, path, content)
    ctx.touched_paths.add(path)
    lines = content.count("\n") + 1
    return f"Wrote {path} ({len(content)} bytes, {lines} lines)."


async def _read_file(ctx: ToolContext, args: dict) -> str:
    path = args.get("path")
    if not isinstance(path, str) or not path:
        return "Error: 'path' is required and must be a string."
    content = await workspace.read_file(ctx.session_id, path)
    return f"Contents of {path}:\n{content}"


async def _list_files(ctx: ToolContext, args: dict) -> str:
    entries = await asyncio.to_thread(workspace.list_workspace_files, ctx.session_id)
    if not entries:
        return "The workspace is empty -- no files have been created yet."
    return "Files in the workspace:\n" + "\n".join(
        f"  {e['path']} ({e['bytes']} bytes)" for e in entries
    )


async def _run_command(ctx: ToolContext, args: dict) -> str:
    command = args.get("command")
    if not isinstance(command, str) or not command.strip():
        return "Error: 'command' is required and must be a non-empty string."

    # The container sees only what is on disk. Anything written by an earlier
    # turn -- or by the pre-tools file extractor -- lives in the DB and may
    # never have been materialized on this machine.
    await workspace.hydrate_from_db(ctx.db, ctx.session_id)

    result = await run_in_sandbox(command, workspace.workspace_root(ctx.session_id))
    ctx.ran_command = True

    if result.error:
        return f"Command did not run: {result.error}"

    # Reconcile whatever the command changed -- generated files, formatter
    # rewrites, test artifacts -- back into the DB.
    synced = await workspace.sync_from_disk(ctx.db, ctx.session_id)
    ctx.touched_paths.update(f["path"] for f in synced)

    verdict = "succeeded" if result.exit_code == 0 else f"failed (exit code {result.exit_code})"
    body = result.output.strip() or "(no output)"
    return f"$ {command}\nCommand {verdict}.\n\n{body}"


_IMPLEMENTATIONS = {
    "write_file": _write_file,
    "read_file": _read_file,
    "list_files": _list_files,
    "run_command": _run_command,
}


async def execute_tool_call(ctx: ToolContext, call: ToolCall) -> ToolResult:
    """
    Run one tool call and convert any failure into a readable observation.

    Nothing raises out of here: a tool error is information the model should
    act on, not a reason to fail the user's turn.
    """
    impl = _IMPLEMENTATIONS.get(call.name)
    if impl is None:
        return ToolResult(
            call_id=call.id, name=call.name,
            content=f"Error: unknown tool {call.name!r}. Available tools: {', '.join(sorted(TOOL_NAMES))}.",
            is_error=True,
        )

    try:
        content = await asyncio.wait_for(impl(ctx, call.arguments or {}), timeout=TOOL_TIMEOUT_SECONDS)
        return ToolResult(call_id=call.id, name=call.name, content=content)
    except WorkspaceError as exc:
        return ToolResult(call_id=call.id, name=call.name, content=f"Error: {exc}", is_error=True)
    except asyncio.TimeoutError:
        return ToolResult(
            call_id=call.id, name=call.name,
            content=f"Error: {call.name} timed out after {TOOL_TIMEOUT_SECONDS}s.",
            is_error=True,
        )
    except Exception as exc:  # noqa: BLE001 -- a tool bug must not kill the turn
        logger.exception("tool %s failed on session %s", call.name, ctx.session_id)
        return ToolResult(
            call_id=call.id, name=call.name, content=f"Error running {call.name}: {exc}", is_error=True
        )


async def execute_tool_calls(ctx: ToolContext, calls: list[ToolCall]) -> list[ToolResult]:
    """
    Execute a batch of tool calls from one model turn.

    Reads (`read_file`, `list_files`) run concurrently -- models routinely ask
    for several files at once and there is no reason to serialize that.
    Everything that MUTATES state (`write_file`, `run_command`) runs in the
    model's requested order, because those genuinely depend on each other: a
    command must observe the writes that preceded it, and two writes to one
    path must not race. Results are returned in call order regardless, since
    each provider correlates them positionally or by id.
    """
    results: dict[str, ToolResult] = {}

    readonly = [c for c in calls if c.name in {"read_file", "list_files"}]
    mutating = [c for c in calls if c.name not in {"read_file", "list_files"}]

    if readonly:
        for call, result in zip(
            readonly,
            await asyncio.gather(*(execute_tool_call(ctx, c) for c in readonly)),
        ):
            results[call.id] = result

    for call in mutating:
        results[call.id] = await execute_tool_call(ctx, call)

    return [results[c.id] for c in calls]


def summarize_call(call: ToolCall) -> str:
    """One-line description of a call, for the UI's activity trace."""
    args = call.arguments or {}
    if call.name in ("write_file", "read_file"):
        return f"{call.name}({args.get('path', '?')})"
    if call.name == "run_command":
        command = str(args.get("command", "?"))
        return f"run_command({command[:80]}{'…' if len(command) > 80 else ''})"
    if call.name == "list_files":
        return "list_files()"
    return f"{call.name}({json.dumps(args)[:80]})"
