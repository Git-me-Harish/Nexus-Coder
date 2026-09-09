"""
Live preview: actually run the app a session generated, in a second,
network-enabled container, reverse-proxied into the browser.

WHY A SECOND IMAGE, AND WHY NODE PROJECTS DON'T WORK
-----------------------------------------------------
The agent's build sandbox (app/agents/sandbox.py) is deliberately offline --
no `pip install`, no `npm install`, ever, at build time. That means a
generated app's dependencies are only ever whatever is preinstalled in an
image. `nexus-preview` (Dockerfile.preview, in the same directory as the
build sandbox's Dockerfile) is what "preinstalled" means for previewing:
FastAPI/Flask/uvicorn baked in. A Node/npm project's dependencies were never
installed anywhere -- giving the preview container network access doesn't
retroactively fetch them -- so those are an explicit "unsupported" response,
not a silent failure (see detect_app).

WHY THIS CONTAINER HAS NETWORK, UNLIKE THE BUILD SANDBOX
---------------------------------------------------------
This container only ever RUNS code that already exists; it never installs
anything and there is no LLM deciding what commands to run inside it. That
removes the two build-sandbox risks network access would otherwise create
(exfiltrating the workspace via a model-issued command, or pulling in
arbitrary packages mid-build). Everything else from the build sandbox's
threat model still applies for defense in depth: non-root, read-only root
filesystem, capabilities dropped -- see the container args below.

LIFECYCLE
---------
One container per session, tracked in an in-process dict. This is a
same-process limitation (a second API worker would not see another worker's
preview), exactly like `_compiled_graph` in graph.py is documented as a
single-process global -- acceptable for this app's current deployment shape,
called out here so it isn't rediscovered by surprise later. A background
reaper (see app/main.py lifespan) stops containers idle past
PREVIEW_IDLE_TIMEOUT_MINUTES; `stop_preview` also lets the user end it
explicitly from the Review phase UI.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.core.config import get_settings

logger = logging.getLogger("nexus.preview")

CONTAINER_PORT = 8000


class PreviewUnavailable(RuntimeError):
    """Docker isn't usable for previewing -- refuse rather than guess."""


class PreviewUnsupported(RuntimeError):
    """The workspace's app type can't be previewed (Node project, or nothing
    recognizable) -- a clear, permanent reason, distinct from an infra
    failure that might work if retried."""


@dataclass
class PreviewInfo:
    session_id: str
    container_id: str
    host_port: int
    kind: str
    last_used: float


@dataclass
class _Entry:
    container_id: str
    host_port: int
    kind: str
    last_used: float


#: session_id -> running preview container. Single-process, see module
#: docstring. Never accessed from a thread -- all mutation happens on the
#: event loop; only the Docker calls themselves are offloaded via to_thread.
_PREVIEWS: dict[str, _Entry] = {}


# ---------------------------------------------------------------------------
# App-type detection
# ---------------------------------------------------------------------------


def _find_assignment(source: str, class_name: str) -> str | None:
    match = re.search(rf"(\w+)\s*=\s*{class_name}\s*\(", source)
    return match.group(1) if match else None


def detect_app(workspace_root: Path) -> tuple[str, str]:
    """
    Returns (kind, run_command). Raises PreviewUnsupported if nothing
    recognizable is found -- this is a best-effort heuristic, not a build
    system, so it only handles the common, obvious shapes: a FastAPI or
    Flask app object in main.py/app.py at the workspace root, or a static
    index.html. Anything else (a package.json, or no entry point at all)
    is told plainly rather than guessed at.
    """
    if (workspace_root / "package.json").exists():
        raise PreviewUnsupported(
            "This looks like a Node/npm project. The build sandbox has no network access, "
            "so its dependencies were never installed -- live preview only supports Python "
            "(FastAPI/Flask) and static HTML/CSS/JS apps."
        )

    for filename in ("main.py", "app.py"):
        candidate = workspace_root / filename
        if not candidate.exists():
            continue
        source = candidate.read_text(encoding="utf-8", errors="replace")
        module = candidate.stem

        fastapi_var = _find_assignment(source, "FastAPI")
        if fastapi_var:
            return "fastapi", f"uvicorn {module}:{fastapi_var} --host 0.0.0.0 --port {CONTAINER_PORT}"

        flask_var = _find_assignment(source, "Flask")
        if flask_var:
            return "flask", f"flask --app {module}:{flask_var} run --host 0.0.0.0 --port {CONTAINER_PORT}"

    if (workspace_root / "index.html").exists():
        return "static", f"python -m http.server {CONTAINER_PORT}"

    raise PreviewUnsupported(
        "Couldn't find a recognizable app to preview -- looked for a FastAPI/Flask app "
        "object in main.py or app.py, or a static index.html at the workspace root."
    )


# ---------------------------------------------------------------------------
# Container lifecycle
# ---------------------------------------------------------------------------


def _start_blocking(session_id: str, workspace_root: Path, run_command: str, settings) -> tuple[str, int]:
    """Synchronous Docker work. Always called through asyncio.to_thread."""
    try:
        import docker
        from docker.errors import DockerException, ImageNotFound
    except ImportError as exc:
        raise PreviewUnavailable("the `docker` package is not installed") from exc

    try:
        client = docker.from_env()
        client.ping()
    except DockerException as exc:
        raise PreviewUnavailable(f"cannot reach the Docker daemon: {exc}") from exc

    try:
        container = client.containers.run(
            image=settings.preview_image,
            command=["/bin/sh", "-lc", run_command],
            working_dir="/workspace",
            # Read-only: the preview runs the app, it does not need to (and
            # should not be able to) modify the workspace the agent built.
            volumes={str(workspace_root.resolve()): {"bind": "/workspace", "mode": "ro"}},
            ports={f"{CONTAINER_PORT}/tcp": None},  # Docker assigns an ephemeral host port
            user="1000:1000",
            read_only=True,
            tmpfs={"/tmp": "rw,noexec,nosuid,size=64m"},
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            # Reusing the build sandbox's resource limits rather than adding
            # a second set of tunables -- one running app doesn't need a
            # different ceiling than one build command did.
            mem_limit=settings.sandbox_mem_limit,
            nano_cpus=int(float(settings.sandbox_cpu_limit) * 1_000_000_000),
            pids_limit=256,
            detach=True,
        )
    except ImageNotFound as exc:
        raise PreviewUnavailable(
            f"preview image {settings.preview_image!r} is not present. Build it first: "
            f"docker build -t {settings.preview_image} -f backend/sandbox/Dockerfile.preview backend/sandbox/"
        ) from exc

    container.reload()
    port_bindings = container.attrs["NetworkSettings"]["Ports"].get(f"{CONTAINER_PORT}/tcp")
    if not port_bindings:
        try:
            container.remove(force=True)
        except DockerException:
            pass
        raise PreviewUnavailable("container started but Docker did not publish a host port")

    return container.id, int(port_bindings[0]["HostPort"])


async def start_preview(session_id: str, workspace_root: Path) -> PreviewInfo:
    """
    Idempotent: if a preview is already running for this session, its info
    is returned as-is (and its last_used bumped) rather than starting a
    second container.
    """
    settings = get_settings()
    if not settings.preview_enabled:
        raise PreviewUnavailable("Live preview is disabled on this deployment (PREVIEW_ENABLED is false).")

    existing = _PREVIEWS.get(session_id)
    if existing is not None and await _is_running(existing.container_id):
        existing.last_used = time.monotonic()
        return PreviewInfo(session_id, existing.container_id, existing.host_port, existing.kind, existing.last_used)

    kind, run_command = detect_app(workspace_root)

    try:
        container_id, host_port = await asyncio.to_thread(
            _start_blocking, session_id, workspace_root, run_command, settings
        )
    except PreviewUnavailable:
        raise

    entry = _Entry(container_id=container_id, host_port=host_port, kind=kind, last_used=time.monotonic())
    _PREVIEWS[session_id] = entry

    # The app needs a moment to bind its port after the process starts;
    # give it a few short retries rather than the first proxied request
    # racing the app's own startup.
    await _wait_for_port(host_port)

    return PreviewInfo(session_id, container_id, host_port, kind, entry.last_used)


async def _wait_for_port(host_port: int, attempts: int = 20, delay: float = 0.25) -> None:
    for _ in range(attempts):
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                await client.get(f"http://127.0.0.1:{host_port}/")
            return
        except httpx.HTTPError:
            await asyncio.sleep(delay)
    # Not up yet after ~5s -- proceed anyway; the first real proxied request
    # will surface whatever the actual problem is (a slow start is not the
    # same as a broken app, so this doesn't raise).


def _stop_blocking(container_id: str) -> None:
    try:
        import docker
        from docker.errors import DockerException, NotFound
    except ImportError:
        return
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        container.remove(force=True)
    except (DockerException, NotFound):
        pass


async def _is_running(container_id: str) -> bool:
    def _check() -> bool:
        try:
            import docker
            from docker.errors import DockerException, NotFound
            client = docker.from_env()
            return client.containers.get(container_id).status == "running"
        except (ImportError, DockerException, NotFound):
            return False
    return await asyncio.to_thread(_check)


async def stop_preview(session_id: str) -> None:
    entry = _PREVIEWS.pop(session_id, None)
    if entry is not None:
        await asyncio.to_thread(_stop_blocking, entry.container_id)


def touch(session_id: str) -> None:
    """Bumps last_used so the reaper doesn't kill an actively-viewed preview."""
    entry = _PREVIEWS.get(session_id)
    if entry is not None:
        entry.last_used = time.monotonic()


def get_port(session_id: str) -> int | None:
    entry = _PREVIEWS.get(session_id)
    return entry.host_port if entry is not None else None


async def reap_idle_previews() -> None:
    """Stops previews idle past PREVIEW_IDLE_TIMEOUT_MINUTES. Called on a
    timer from app/main.py's lifespan when preview_enabled is on."""
    settings = get_settings()
    cutoff = settings.preview_idle_timeout_minutes * 60
    now = time.monotonic()
    idle = [sid for sid, entry in _PREVIEWS.items() if now - entry.last_used > cutoff]
    for session_id in idle:
        logger.info("reaping idle preview for session %s", session_id)
        await stop_preview(session_id)


async def preview_health() -> dict:
    """Diagnostics for the /health endpoint, mirroring sandbox_health."""
    settings = get_settings()
    if not settings.preview_enabled:
        return {"enabled": False, "usable": False, "detail": "PREVIEW_ENABLED is false"}

    def _check() -> dict:
        try:
            import docker
            from docker.errors import DockerException
        except ImportError:
            return {"enabled": True, "usable": False, "detail": "the `docker` package is not installed"}
        try:
            client = docker.from_env()
            client.ping()
        except DockerException as exc:
            return {"enabled": True, "usable": False, "detail": f"cannot reach the Docker daemon: {exc}"}
        try:
            client.images.get(settings.preview_image)
        except Exception:  # noqa: BLE001
            return {"enabled": True, "usable": False, "detail": f"preview image {settings.preview_image!r} is not built"}
        return {"enabled": True, "usable": True, "detail": f"image {settings.preview_image!r} ready"}

    return await asyncio.to_thread(_check)
