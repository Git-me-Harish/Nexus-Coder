"""
Workspace path containment and DB<->disk sync.

The path tests are security tests, not hygiene: every path here arrives from
a model, and `resolve_path` is the only thing standing between a generated
`../../../../etc/passwd` and the API server's filesystem.
"""
import asyncio

import pytest

from app.agents import workspace
from app.agents.workspace import WorkspaceError

SID = "wstestsession"


@pytest.fixture(autouse=True)
def isolated_workspace(tmp_path, monkeypatch):
    """Point workspaces at a tmp dir so tests never touch the real one."""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path), raising=False)
    yield
    workspace.destroy_workspace(SID)


# --- containment ------------------------------------------------------------


@pytest.mark.parametrize("bad_path", [
    "../escape.txt",
    "../../etc/passwd",
    "a/../../../outside.txt",
    "/etc/passwd",
    "/absolute.txt",
    "..",
    "",
    "   ",
])
def test_paths_that_escape_the_workspace_are_rejected(bad_path):
    with pytest.raises(WorkspaceError):
        workspace.resolve_path(SID, bad_path)


@pytest.mark.parametrize("good_path", [
    "app.py",
    "src/main.py",
    "a/b/c/deep.txt",
    "./relative.txt",
    "dir/../sibling.txt",  # normalizes to sibling.txt, still inside
])
def test_paths_inside_the_workspace_are_allowed(good_path):
    resolved = workspace.resolve_path(SID, good_path)
    root = workspace.workspace_root(SID)
    assert resolved == root or root in resolved.parents


def test_backslash_paths_are_normalized():
    """Models emit Windows-style separators; they must not defeat containment."""
    assert workspace.resolve_path(SID, "src\\main.py").name == "main.py"
    with pytest.raises(WorkspaceError):
        workspace.resolve_path(SID, "..\\..\\escape.txt")


def test_symlink_cannot_be_used_to_escape(tmp_path):
    """A symlink pointing outside must not become a write primitive."""
    root = workspace.workspace_root(SID)
    outside = tmp_path / "outside_target"
    outside.mkdir(exist_ok=True)
    link = root / "sneaky"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not permitted in this environment")

    with pytest.raises(WorkspaceError):
        workspace.resolve_path(SID, "sneaky/pwned.txt")


def test_unsafe_session_id_is_rejected():
    for bad in ["../other", "a/b", "", "..", "x/../../y"]:
        with pytest.raises(WorkspaceError):
            workspace.workspace_root(bad)


# --- read / write -----------------------------------------------------------


@pytest.mark.asyncio
async def test_write_then_read_roundtrip():
    await workspace.write_file(SID, "src/app.py", "print('hi')")
    assert await workspace.read_file(SID, "src/app.py") == "print('hi')"


@pytest.mark.asyncio
async def test_write_creates_parent_directories():
    await workspace.write_file(SID, "a/b/c/deep.txt", "x")
    assert workspace.resolve_path(SID, "a/b/c/deep.txt").exists()


@pytest.mark.asyncio
async def test_files_are_written_with_lf_endings_on_every_host():
    """
    Regression: Path.write_text translates "\\n" to os.linesep, so on a Windows
    host every generated file landed as CRLF -- and then ran in a LINUX
    container, where CRLF breaks shebangs and shell scripts. Caught in a real
    end-to-end run, where a file's byte count grew by exactly its line count
    between writing and listing it.
    """
    await workspace.write_file(SID, "script.sh", "#!/bin/sh\necho hi\n")

    raw = workspace.resolve_path(SID, "script.sh").read_bytes()
    assert b"\r\n" not in raw
    assert raw == b"#!/bin/sh\necho hi\n"


@pytest.mark.asyncio
async def test_non_ascii_content_survives_the_roundtrip_exactly():
    """
    Models emit typographic characters constantly -- non-breaking hyphens,
    em dashes, smart quotes -- and source files legitimately contain CJK and
    emoji. Everything is written and read as explicit UTF-8 so the host's
    console or locale encoding can never mangle a user's file.
    """
    tricky = 'x = "café ‑ naïve — “smart” 😀 你好"'
    await workspace.write_file(SID, "unicode.py", tricky)

    assert await workspace.read_file(SID, "unicode.py") == tricky
    assert workspace.resolve_path(SID, "unicode.py").read_bytes().decode("utf-8") == tricky


@pytest.mark.asyncio
async def test_reading_a_missing_file_is_a_workspace_error():
    with pytest.raises(WorkspaceError):
        await workspace.read_file(SID, "nope.py")


@pytest.mark.asyncio
async def test_oversized_file_is_not_read_into_context():
    await workspace.write_file(SID, "huge.txt", "x" * (workspace.MAX_TRACKED_FILE_BYTES + 1))
    with pytest.raises(WorkspaceError):
        await workspace.read_file(SID, "huge.txt")


@pytest.mark.asyncio
async def test_listing_skips_ignored_directories():
    await workspace.write_file(SID, "keep.py", "1")
    await workspace.write_file(SID, "node_modules/pkg/index.js", "2")
    await workspace.write_file(SID, "__pycache__/x.pyc", "3")

    listed = {e["path"] for e in workspace.list_workspace_files(SID)}
    assert listed == {"keep.py"}


# --- DB sync ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_to_db_creates_then_versions(db_session):
    await workspace.write_file(SID, "app.py", "v1")
    written = await workspace.sync_to_db(db_session, SID, ["app.py"])
    await db_session.commit()
    assert written == [{"path": "app.py", "language": "python"}]

    rows = await _files(db_session)
    assert rows[0].content == "v1" and rows[0].version == 1

    await workspace.write_file(SID, "app.py", "v2")
    await workspace.sync_to_db(db_session, SID, ["app.py"])
    await db_session.commit()

    rows = await _files(db_session)
    assert len(rows) == 1, "same path must update in place, not duplicate"
    assert rows[0].content == "v2" and rows[0].version == 2


@pytest.mark.asyncio
async def test_syncing_the_same_path_twice_before_commit_does_not_duplicate(db_session):
    """
    Regression from the first real run. run_command syncs the workspace into
    the DB mid-loop, and the route syncs the touched paths again at the end of
    the turn -- both inside ONE uncommitted transaction. The session uses
    autoflush=False, so the first pending INSERT was invisible to the second
    lookup, a duplicate row was added, and the commit died on
    uq_session_file_path -- rolling back the entire turn's work: files,
    assistant message and token accounting alike.
    """
    await workspace.write_file(SID, "app.py", "v1")

    await workspace.sync_to_db(db_session, SID, ["app.py"])   # e.g. from run_command
    await workspace.write_file(SID, "app.py", "v2")
    await workspace.sync_to_db(db_session, SID, ["app.py"])   # e.g. from the route
    await db_session.commit()                                  # must not raise

    rows = await _files(db_session)
    assert len(rows) == 1
    assert rows[0].content == "v2"


@pytest.mark.asyncio
async def test_sync_from_disk_then_sync_to_db_commits_cleanly(db_session):
    """The exact two-call sequence a real agent turn performs."""
    await workspace.write_file(SID, "a.py", "1")
    await workspace.write_file(SID, "b.py", "2")

    await workspace.sync_from_disk(db_session, SID)             # run_command
    await workspace.sync_to_db(db_session, SID, ["a.py", "b.py"])  # end of turn
    await db_session.commit()

    assert {r.file_path for r in await _files(db_session)} == {"a.py", "b.py"}


@pytest.mark.asyncio
async def test_identical_rewrite_does_not_burn_a_version(db_session):
    await workspace.write_file(SID, "app.py", "same")
    await workspace.sync_to_db(db_session, SID, ["app.py"])
    await db_session.commit()

    written = await workspace.sync_to_db(db_session, SID, ["app.py"])
    await db_session.commit()

    assert written == [], "a no-op write should not be announced as a file change"
    assert (await _files(db_session))[0].version == 1


@pytest.mark.asyncio
async def test_hydrate_from_db_materializes_files_the_disk_never_saw(db_session):
    """The workspace is machine-local; the DB is the durable record. After a
    redeploy the files exist only in Postgres and must be restored before a
    command can run against them."""
    await workspace.write_file(SID, "app.py", "from db")
    await workspace.sync_to_db(db_session, SID, ["app.py"])
    await db_session.commit()

    workspace.destroy_workspace(SID)
    assert not workspace.resolve_path(SID, "app.py").exists()

    restored = await workspace.hydrate_from_db(db_session, SID)
    assert restored == 1
    assert await workspace.read_file(SID, "app.py") == "from db"


@pytest.mark.asyncio
async def test_sync_from_disk_picks_up_files_no_tool_wrote(db_session):
    """A command that generates files (a scaffolder, a formatter, a test
    artifact) must still surface in the Files panel."""
    await workspace.write_file(SID, "generated_by_command.py", "x = 1")
    written = await workspace.sync_from_disk(db_session, SID)
    await db_session.commit()

    assert {w["path"] for w in written} == {"generated_by_command.py"}


async def _files(db):
    from sqlalchemy import select

    from app.models.message import SessionFile

    return list((await db.execute(
        select(SessionFile).where(SessionFile.session_id == SID).order_by(SessionFile.file_path)
    )).scalars().all())
