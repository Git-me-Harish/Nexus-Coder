"""
The session workspace: a real directory on disk that the agent's tools read
and write, and that the sandbox bind-mounts at /workspace.

WHY A REAL DIRECTORY AND NOT JUST THE DB
----------------------------------------
SessionFile rows are what the UI renders and what survives a redeploy, but a
compiler, a test runner, or `npm install` needs actual files on a real
filesystem. So both exist, with a clear rule about which wins:

    the filesystem is the working copy; the DB is the durable record.

Tools write through to both. After a command runs, `sync_from_disk` reconciles
whatever the command changed on disk back into the DB -- that is what makes
`pytest` writing a fixture, or a formatter rewriting a file, visible in the
Files panel instead of silently lost.

PATH SAFETY
-----------
Every path the model supplies is untrusted input. `resolve_path` is the only
way a path is turned into a real location, and it rejects absolute paths,
symlink escapes, and anything that resolves outside the session root -- so
`../../../../etc/passwd` or a symlink pointing at the API server's own source
tree cannot be read or written.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.file_extraction import LANG_MAP
from app.core.config import get_settings
from app.models.message import SessionFile

logger = logging.getLogger("nexus.workspace")

#: Files bigger than this are not mirrored into the DB or shown to the model.
#: A node_modules blob or a build artifact would otherwise be read into memory
#: and, worse, into the model's context.
MAX_TRACKED_FILE_BYTES = 512 * 1024

#: Never mirrored back from disk: churny, enormous, or machine-local.
IGNORED_DIRS = {
    ".git", "node_modules", "__pycache__", ".pytest_cache", ".venv", "venv",
    "dist", "build", ".next", ".mypy_cache", ".ruff_cache", "target", ".tox",
}


class WorkspaceError(ValueError):
    """A path the model supplied is not usable -- reported back to it as a
    tool error so it can correct itself, never raised at the user."""


def workspace_root(session_id: str) -> Path:
    """
    Per-session directory. `session_id` is a server-generated cuid, never
    user input, but it is still validated: it becomes a path segment, and a
    single unvalidated separator here would be a directory traversal.
    """
    if not session_id or not session_id.replace("-", "").replace("_", "").isalnum():
        raise WorkspaceError(f"unsafe session id: {session_id!r}")

    root = Path(get_settings().workspace_root).resolve() / session_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_path(session_id: str, relative_path: str) -> Path:
    """
    Turn a model-supplied relative path into a real path inside the session
    workspace, or raise WorkspaceError.

    This is the containment boundary for every file tool. `strict=False`
    resolution still collapses `..` and follows symlinks, so both traversal
    and symlink-escape are caught by the containment check below.
    """
    if not relative_path or not relative_path.strip():
        raise WorkspaceError("path must not be empty")

    candidate = Path(relative_path.strip().replace("\\", "/"))
    if candidate.is_absolute() or (len(candidate.parts) and candidate.parts[0] == "/"):
        raise WorkspaceError(f"path must be relative to the workspace, got {relative_path!r}")

    root = workspace_root(session_id)
    resolved = (root / candidate).resolve()

    if resolved != root and root not in resolved.parents:
        raise WorkspaceError(f"path escapes the workspace: {relative_path!r}")

    return resolved


def language_for(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return LANG_MAP.get(ext, "text")


def _iter_workspace_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        yield path


def list_workspace_files(session_id: str) -> list[dict]:
    """Everything currently on disk, as {path, bytes}, sorted."""
    root = workspace_root(session_id)
    entries = [
        {"path": p.relative_to(root).as_posix(), "bytes": p.stat().st_size}
        for p in _iter_workspace_files(root)
    ]
    return sorted(entries, key=lambda e: e["path"])


def _write_text_lf(target: Path, content: str) -> None:
    """
    Write with LF endings, always.

    `Path.write_text` translates "\\n" to os.linesep, so on a Windows host
    every file the agent writes would land as CRLF -- and then execute in a
    LINUX container, where CRLF breaks shebangs ("/usr/bin/env python\\r: no
    such file"), here-docs, and any shell script. The workspace is a Linux
    working tree that merely happens to be stored on the host, so it gets
    Linux line endings regardless of what the host prefers.
    """
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


async def write_file(session_id: str, relative_path: str, content: str) -> Path:
    """Write to disk. The DB mirror happens in sync_to_db."""
    target = resolve_path(session_id, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    # Blocking IO off the event loop -- see the note in sandbox.py about why
    # stalling the loop hurts every concurrent SSE stream, not just this one.
    await asyncio.to_thread(_write_text_lf, target, content)
    return target


async def read_file(session_id: str, relative_path: str) -> str:
    target = resolve_path(session_id, relative_path)
    if not target.exists() or not target.is_file():
        raise WorkspaceError(f"no such file: {relative_path}")
    if target.stat().st_size > MAX_TRACKED_FILE_BYTES:
        raise WorkspaceError(
            f"{relative_path} is {target.stat().st_size} bytes, larger than the "
            f"{MAX_TRACKED_FILE_BYTES}-byte read limit"
        )
    return await asyncio.to_thread(target.read_text, encoding="utf-8", errors="replace")


async def hydrate_from_db(db: AsyncSession, session_id: str) -> int:
    """
    Materialize the DB's SessionFile rows onto disk.

    Needed because the workspace directory is machine-local: after a
    redeploy, a restart on different infrastructure, or a first command in a
    session whose files were written by the pre-tools file extractor, the DB
    holds files the filesystem has never seen. Only writes files that are
    missing or differ, so it stays cheap to call before every command.
    """
    rows = (await db.execute(
        select(SessionFile).where(SessionFile.session_id == session_id)
    )).scalars().all()

    written = 0
    for row in rows:
        try:
            target = resolve_path(session_id, row.file_path)
        except WorkspaceError:
            logger.warning("skipping unsafe stored path %r on session %s", row.file_path, session_id)
            continue

        if target.exists() and await asyncio.to_thread(
            lambda: target.read_text(encoding="utf-8", errors="replace")
        ) == row.content:
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(target.write_text, row.content, encoding="utf-8")
        written += 1

    return written


async def sync_to_db(db: AsyncSession, session_id: str, paths: list[str]) -> list[dict]:
    """
    Mirror specific workspace files into SessionFile rows. Returns
    [{path, language}] for the file_written events the UI listens for.

    Caller commits -- so a tool's file write and the rest of that turn's
    persistence land in one transaction.
    """
    written: list[dict] = []
    for relative in paths:
        try:
            target = resolve_path(session_id, relative)
        except WorkspaceError:
            continue
        if not target.exists() or not target.is_file():
            continue
        if target.stat().st_size > MAX_TRACKED_FILE_BYTES:
            continue

        content = await asyncio.to_thread(target.read_text, encoding="utf-8", errors="replace")
        normalized = Path(relative.replace("\\", "/")).as_posix()

        existing = (await db.execute(
            select(SessionFile).where(
                SessionFile.session_id == session_id, SessionFile.file_path == normalized
            )
        )).scalar_one_or_none()

        if existing:
            if existing.content == content:
                continue  # no-op write; don't burn a version on it
            existing.content = content
            existing.language = language_for(normalized)
            existing.version += 1
        else:
            db.add(SessionFile(
                session_id=session_id, file_path=normalized,
                content=content, language=language_for(normalized),
            ))
            # Flush so this INSERT is visible to the SELECT above on a later
            # call within the SAME transaction. The session is built with
            # autoflush=False, so without this a second sync of the same path
            # sees no existing row and adds a duplicate -- which blows up at
            # commit on uq_session_file_path and rolls back the WHOLE turn:
            # files, assistant message, token accounting, all of it.
            #
            # That is not hypothetical. It happened on the first real run:
            # run_command syncs the workspace mid-loop, then the route syncs
            # the touched paths again at the end of the turn, and the agent's
            # completed, test-passing work vanished at commit time.
            await db.flush()
        written.append({"path": normalized, "language": language_for(normalized)})

    return written


async def sync_from_disk(db: AsyncSession, session_id: str) -> list[dict]:
    """
    Reconcile everything on disk back into the DB.

    Run after a command executes: `pytest` writing a fixture, a formatter
    rewriting files, or a scaffolder generating a tree are all real changes
    the user should see in the Files panel, and none of them came through
    write_file.
    """
    root = workspace_root(session_id)
    paths = [p.relative_to(root).as_posix() for p in _iter_workspace_files(root)]
    return await sync_to_db(db, session_id, paths)


def destroy_workspace(session_id: str) -> None:
    """Remove a session's working copy. The DB rows remain the durable record."""
    try:
        shutil.rmtree(workspace_root(session_id), ignore_errors=True)
    except WorkspaceError:
        pass
