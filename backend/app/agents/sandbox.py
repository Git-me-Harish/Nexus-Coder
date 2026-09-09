"""
Real command execution for the agent, in a Docker container.

SECURITY POSTURE -- READ BEFORE CHANGING ANYTHING HERE
------------------------------------------------------
This module runs code an LLM wrote, on your infrastructure. It is the most
dangerous file in the codebase, so the constraints below are deliberate and
none of them are decoration:

  - **Docker only, never the host.** If Docker is unavailable the tool
    returns an error; it does NOT fall back to `subprocess` on the host.
    A host fallback would mean any prompt injection in a user's repo, error
    message, or dependency README becomes arbitrary code execution on the
    API server. There is no flag to enable that, on purpose.
  - **Network disabled** (`network_mode="none"`). Generated code cannot
    exfiltrate the workspace, reach your internal network, or install
    arbitrary packages mid-run.
  - **Non-root** (`user="1000:1000"`), read-only root filesystem, and
    `cap_drop=["ALL"]` with `no-new-privileges`, so a compromised process
    cannot escalate inside the container.
  - **Bounded**: CPU, memory, PID count, output size, and a wall-clock
    timeout enforced by killing the container. An unbounded `while True` in
    generated code otherwise pins a core until the process dies.
  - **The workspace is the only writable mount**, bound at /workspace, and
    it is per-session (see workspace.py), so one session cannot read or
    corrupt another's files.

The blocking docker SDK calls are run via `asyncio.to_thread`; calling them
directly would stall the whole event loop -- and with SSE streaming, stalling
the loop freezes every other user's in-flight response, not just this one.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger("nexus.sandbox")

#: Truncation ceiling for combined stdout+stderr. A runaway build log would
#: otherwise blow the model's context window in a single observation.
MAX_OUTPUT_CHARS = 20_000


@dataclass
class ExecResult:
    exit_code: int
    output: str
    timed_out: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and not self.timed_out and self.exit_code == 0


class SandboxUnavailable(RuntimeError):
    """Docker isn't usable, so we refuse to execute rather than run on the host."""


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    half = MAX_OUTPUT_CHARS // 2
    omitted = len(text) - MAX_OUTPUT_CHARS
    return f"{text[:half]}\n\n...[{omitted} characters omitted]...\n\n{text[-half:]}"


def _run_blocking(command: str, workspace: Path, settings) -> ExecResult:
    """Synchronous Docker work. Always called through asyncio.to_thread."""
    try:
        import docker
        from docker.errors import DockerException, ImageNotFound, NotFound
    except ImportError as exc:
        raise SandboxUnavailable("the `docker` package is not installed") from exc

    try:
        client = docker.from_env()
        client.ping()
    except DockerException as exc:
        raise SandboxUnavailable(f"cannot reach the Docker daemon: {exc}") from exc

    container = None
    try:
        try:
            container = client.containers.run(
                image=settings.sandbox_image,
                command=["/bin/sh", "-lc", command],
                working_dir="/workspace",
                # The ONLY writable path. Everything else is read-only.
                volumes={str(workspace.resolve()): {"bind": "/workspace", "mode": "rw"}},
                network_mode="none",
                user="1000:1000",
                read_only=True,
                # /tmp still needs to be writable for compilers, test runners
                # and package tooling -- but capped, noexec, and wiped with
                # the container.
                tmpfs={"/tmp": "rw,noexec,nosuid,size=64m"},
                cap_drop=["ALL"],
                security_opt=["no-new-privileges"],
                mem_limit=settings.sandbox_mem_limit,
                nano_cpus=int(float(settings.sandbox_cpu_limit) * 1_000_000_000),
                pids_limit=256,
                detach=True,
            )
        except ImageNotFound as exc:
            raise SandboxUnavailable(
                f"sandbox image {settings.sandbox_image!r} is not present. "
                f"Build it first: docker build -t {settings.sandbox_image} backend/sandbox/"
            ) from exc

        try:
            status = container.wait(timeout=settings.sandbox_timeout_seconds)
            exit_code = status.get("StatusCode", -1)
            timed_out = False
        except Exception:
            # requests raises ReadTimeout (not a docker error) when wait()
            # exceeds the timeout; kill the container so it can't outlive the
            # request that started it.
            timed_out = True
            exit_code = -1
            try:
                container.kill()
            except (DockerException, NotFound):
                pass

        try:
            output = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
        except DockerException:
            output = ""

        if timed_out:
            output += f"\n\n[timed out after {settings.sandbox_timeout_seconds}s and was killed]"

        return ExecResult(exit_code=exit_code, output=_truncate(output), timed_out=timed_out)

    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:  # noqa: BLE001 -- cleanup must never mask the real result
                logger.warning("could not remove sandbox container %s", getattr(container, "id", "?"))


async def run_in_sandbox(command: str, workspace: Path) -> ExecResult:
    """
    Execute `command` against `workspace` in a locked-down container.

    Returns an ExecResult even for infrastructure failures (as `error`), so a
    missing image or stopped daemon reaches the model as a normal, readable
    observation it can reason about -- rather than an exception that kills the
    user's turn.
    """
    settings = get_settings()

    if not settings.sandbox_enabled:
        return ExecResult(
            exit_code=-1,
            output="",
            error=(
                "Command execution is disabled on this deployment "
                "(SANDBOX_ENABLED is false), so this command was not run."
            ),
        )

    try:
        return await asyncio.to_thread(_run_blocking, command, workspace, settings)
    except SandboxUnavailable as exc:
        logger.error("sandbox unavailable: %s", exc)
        return ExecResult(
            exit_code=-1,
            output="",
            error=(
                f"The execution sandbox is unavailable ({exc}). Commands cannot be run "
                f"until it is fixed; they are never run outside the sandbox."
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("unexpected sandbox failure")
        return ExecResult(exit_code=-1, output="", error=f"Sandbox failure: {exc}")


async def sandbox_health() -> dict:
    """Diagnostics for startup logging and the health endpoint."""
    settings = get_settings()
    if not settings.sandbox_enabled:
        return {"enabled": False, "usable": False, "detail": "SANDBOX_ENABLED is false"}

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
            client.images.get(settings.sandbox_image)
        except Exception:  # noqa: BLE001 -- ImageNotFound and transport errors alike
            return {
                "enabled": True, "usable": False,
                "detail": f"sandbox image {settings.sandbox_image!r} is not built",
            }
        return {"enabled": True, "usable": True, "detail": f"image {settings.sandbox_image!r} ready"}

    return await asyncio.to_thread(_check)
