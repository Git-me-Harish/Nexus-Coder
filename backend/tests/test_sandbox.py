"""
Real sandbox execution and its containment guarantees.

These start actual containers. They are skipped -- not failed -- when Docker
or the image is unavailable, so the suite still runs on a machine without
them; but where Docker IS available these must pass, because every one of
them is a property the design depends on. This module is the reason
`run_command` can be trusted to be neither a mock nor a hole in the host.

Build the image first:  docker build -t nexus-sandbox:latest backend/sandbox/
"""

import pytest

from app.agents import workspace
from app.agents.sandbox import run_in_sandbox, sandbox_health

SID = "sandboxtestsess"


@pytest.fixture(autouse=True)
def sandbox_env(tmp_path, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "sandbox_enabled", True, raising=False)
    yield
    workspace.destroy_workspace(SID)


async def _skip_unless_usable():
    health = await sandbox_health()
    if not health["usable"]:
        pytest.skip(f"sandbox unavailable: {health['detail']}")


@pytest.mark.asyncio
async def test_runs_real_code_and_returns_real_output():
    await _skip_unless_usable()
    await workspace.write_file(SID, "hello.py", "print('hello from the sandbox')")

    result = await run_in_sandbox("python hello.py", workspace.workspace_root(SID))

    assert result.ok
    assert "hello from the sandbox" in result.output


@pytest.mark.asyncio
async def test_failing_command_reports_the_real_exit_code_and_stderr():
    """The loop depends on this: a real failure is what the model reacts to."""
    await _skip_unless_usable()
    await workspace.write_file(SID, "boom.py", "raise ValueError('kaboom')")

    result = await run_in_sandbox("python boom.py", workspace.workspace_root(SID))

    assert not result.ok
    assert result.exit_code == 1
    assert "kaboom" in result.output and "ValueError" in result.output


@pytest.mark.asyncio
async def test_tests_actually_run():
    await _skip_unless_usable()
    await workspace.write_file(SID, "test_m.py", "def test_ok():\n    assert 1 + 1 == 2\n")

    result = await run_in_sandbox("python -m pytest -q test_m.py", workspace.workspace_root(SID))

    assert result.ok and "1 passed" in result.output


@pytest.mark.asyncio
async def test_writes_land_on_the_host_workspace():
    """The container's work must be visible to the API process, or the DB
    sync after a command has nothing to pick up."""
    await _skip_unless_usable()
    await workspace.write_file(SID, "gen.py", "open('generated.txt','w').write('by the agent')")

    result = await run_in_sandbox("python gen.py", workspace.workspace_root(SID))

    assert result.ok
    assert await workspace.read_file(SID, "generated.txt") == "by the agent"


# --- containment ------------------------------------------------------------


@pytest.mark.asyncio
async def test_network_is_disabled():
    """Generated code must not be able to exfiltrate the workspace or reach
    the internal network."""
    await _skip_unless_usable()
    result = await run_in_sandbox(
        "python -c \"import urllib.request; urllib.request.urlopen('http://example.com', timeout=5)\"",
        workspace.workspace_root(SID),
    )
    assert not result.ok


@pytest.mark.asyncio
async def test_runs_as_a_non_root_user():
    await _skip_unless_usable()
    result = await run_in_sandbox("id -u", workspace.workspace_root(SID))
    assert result.output.strip().endswith("1000")


@pytest.mark.asyncio
async def test_root_filesystem_is_read_only():
    await _skip_unless_usable()
    result = await run_in_sandbox("touch /etc/pwned", workspace.workspace_root(SID))
    assert not result.ok


@pytest.mark.asyncio
async def test_only_this_session_workspace_is_mounted():
    """One session must not be able to read or corrupt another's files."""
    await _skip_unless_usable()
    await workspace.write_file(SID, "mine.txt", "mine")
    other = "sandboxothersess"
    await workspace.write_file(other, "theirs.txt", "theirs")
    try:
        result = await run_in_sandbox("ls /workspace", workspace.workspace_root(SID))
        assert "mine.txt" in result.output
        assert "theirs.txt" not in result.output
    finally:
        workspace.destroy_workspace(other)


# --- limits -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_runaway_process_is_killed_at_the_timeout():
    await _skip_unless_usable()
    result = await run_in_sandbox("python -c 'while True: pass'", workspace.workspace_root(SID))

    assert result.timed_out
    assert not result.ok
    assert "timed out" in result.output


@pytest.mark.asyncio
async def test_enormous_output_is_truncated():
    """A runaway build log would otherwise blow the model's context window in
    a single observation."""
    await _skip_unless_usable()
    result = await run_in_sandbox(
        "python -c \"print('x' * 5_000_000)\"", workspace.workspace_root(SID)
    )
    from app.agents.sandbox import MAX_OUTPUT_CHARS

    assert len(result.output) <= MAX_OUTPUT_CHARS + 200
    assert "characters omitted" in result.output


# --- refusing to run --------------------------------------------------------


@pytest.mark.asyncio
async def test_disabled_sandbox_reports_instead_of_running_on_the_host():
    """The critical negative: with execution off, nothing runs -- and it comes
    back as a readable observation rather than an exception."""
    from app.core.config import get_settings

    settings = get_settings()
    original = settings.sandbox_enabled
    settings.sandbox_enabled = False
    try:
        result = await run_in_sandbox("echo should-not-run", workspace.workspace_root(SID))
    finally:
        settings.sandbox_enabled = original

    assert result.error is not None
    assert not result.ok
    assert "should-not-run" not in result.output


@pytest.mark.asyncio
async def test_missing_image_is_an_observation_not_a_crash():
    from app.core.config import get_settings

    settings = get_settings()
    original = settings.sandbox_image
    settings.sandbox_image = "nexus-sandbox-does-not-exist:v0"
    try:
        result = await run_in_sandbox("echo hi", workspace.workspace_root(SID))
    finally:
        settings.sandbox_image = original

    assert result.error is not None and not result.ok
    assert "not present" in result.error or "unavailable" in result.error
