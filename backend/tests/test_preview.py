"""
Live preview: app-type detection (pure, no Docker needed) and real container
lifecycle (skipped -- not failed -- when Docker or the preview image is
unavailable, mirroring test_sandbox.py).

Build the image first:
  docker build -t nexus-preview:latest -f backend/sandbox/Dockerfile.preview backend/sandbox/
"""
import httpx
import pytest
import pytest_asyncio

from app.agents import preview, workspace

SID = "previewtestsess"


@pytest_asyncio.fixture(autouse=True)
async def preview_env(tmp_path, monkeypatch):
    settings_obj = _settings()
    monkeypatch.setattr(settings_obj, "workspace_root", str(tmp_path), raising=False)
    monkeypatch.setattr(settings_obj, "preview_enabled", True, raising=False)
    yield
    # Must actually stop the container, not just drop the dict entry -- a
    # bare `_PREVIEWS.pop` here previously left every test's container
    # running forever, since nothing else in the test process ever calls
    # docker stop/remove on it.
    await preview.stop_preview(SID)
    workspace.destroy_workspace(SID)


def _settings():
    from app.core.config import get_settings
    return get_settings()


async def _skip_unless_usable():
    health = await preview.preview_health()
    if not health["usable"]:
        pytest.skip(f"preview unavailable: {health['detail']}")


# --- detection (no Docker needed) -------------------------------------------


@pytest.mark.asyncio
async def test_detects_fastapi_app():
    await workspace.write_file(SID, "main.py", "from fastapi import FastAPI\napp = FastAPI()\n")
    kind, cmd = preview.detect_app(workspace.workspace_root(SID))
    assert kind == "fastapi"
    assert "uvicorn main:app" in cmd and "--port 8000" in cmd


@pytest.mark.asyncio
async def test_detects_fastapi_app_with_a_nonstandard_variable_name():
    await workspace.write_file(SID, "app.py", "from fastapi import FastAPI\napi = FastAPI()\n")
    kind, cmd = preview.detect_app(workspace.workspace_root(SID))
    assert kind == "fastapi"
    assert "uvicorn app:api" in cmd


@pytest.mark.asyncio
async def test_detects_flask_app():
    await workspace.write_file(SID, "main.py", "from flask import Flask\napp = Flask(__name__)\n")
    kind, cmd = preview.detect_app(workspace.workspace_root(SID))
    assert kind == "flask"
    assert "flask --app main:app run" in cmd


@pytest.mark.asyncio
async def test_detects_static_site():
    await workspace.write_file(SID, "index.html", "<html></html>")
    kind, cmd = preview.detect_app(workspace.workspace_root(SID))
    assert kind == "static"
    assert "http.server 8000" in cmd


@pytest.mark.asyncio
async def test_node_project_is_explicitly_unsupported_not_silently_broken():
    """The build sandbox never installs npm deps (it's offline by design), so
    a Node project's preview can never actually run -- this must be a clear,
    permanent message, not a confusing runtime crash from a missing module."""
    await workspace.write_file(SID, "package.json", '{"name": "x"}')
    with pytest.raises(preview.PreviewUnsupported, match="Node/npm"):
        preview.detect_app(workspace.workspace_root(SID))


@pytest.mark.asyncio
async def test_unrecognizable_workspace_is_unsupported():
    await workspace.write_file(SID, "notes.txt", "just some notes")
    with pytest.raises(preview.PreviewUnsupported):
        preview.detect_app(workspace.workspace_root(SID))


@pytest.mark.asyncio
async def test_disabled_preview_refuses_to_start(monkeypatch):
    monkeypatch.setattr(_settings(), "preview_enabled", False, raising=False)
    await workspace.write_file(SID, "index.html", "<html></html>")
    with pytest.raises(preview.PreviewUnavailable, match="disabled"):
        await preview.start_preview(SID, workspace.workspace_root(SID))


# --- real container lifecycle ------------------------------------------------


@pytest.mark.asyncio
async def test_runs_a_real_fastapi_app_and_serves_a_real_response():
    await _skip_unless_usable()
    await workspace.write_file(SID, "main.py", (
        "from fastapi import FastAPI\napp = FastAPI()\n"
        "@app.get('/')\ndef root(): return {'ok': True}\n"
    ))

    info = await preview.start_preview(SID, workspace.workspace_root(SID))
    assert info.kind == "fastapi"

    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(f"http://127.0.0.1:{info.host_port}/")
    assert r.status_code == 200 and r.json() == {"ok": True}


@pytest.mark.asyncio
async def test_runs_a_real_static_site():
    await _skip_unless_usable()
    await workspace.write_file(SID, "index.html", "<html><body>marker-xyz</body></html>")

    info = await preview.start_preview(SID, workspace.workspace_root(SID))
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(f"http://127.0.0.1:{info.host_port}/")
    assert r.status_code == 200 and "marker-xyz" in r.text


@pytest.mark.asyncio
async def test_starting_twice_is_idempotent_not_a_second_container():
    await _skip_unless_usable()
    await workspace.write_file(SID, "index.html", "<html></html>")
    root = workspace.workspace_root(SID)

    first = await preview.start_preview(SID, root)
    second = await preview.start_preview(SID, root)

    assert first.container_id == second.container_id
    assert first.host_port == second.host_port


@pytest.mark.asyncio
async def test_stop_actually_removes_the_container_and_get_port_returns_none():
    await _skip_unless_usable()
    await workspace.write_file(SID, "index.html", "<html></html>")
    root = workspace.workspace_root(SID)

    info = await preview.start_preview(SID, root)
    assert preview.get_port(SID) == info.host_port

    await preview.stop_preview(SID)
    assert preview.get_port(SID) is None

    import docker
    client = docker.from_env()
    with pytest.raises(docker.errors.NotFound):
        client.containers.get(info.container_id)


@pytest.mark.asyncio
async def test_the_workspace_mount_is_read_only():
    """The preview only RUNS the app; it must not be able to modify what the
    agent built."""
    await _skip_unless_usable()
    await workspace.write_file(SID, "main.py", (
        "from fastapi import FastAPI\napp = FastAPI()\n"
        "@app.get('/')\n"
        "def root():\n"
        "    try:\n"
        "        open('/workspace/pwned.txt', 'w').write('x')\n"
        "        return {'wrote': True}\n"
        "    except OSError as e:\n"
        "        return {'wrote': False, 'error': str(e)}\n"
    ))

    info = await preview.start_preview(SID, workspace.workspace_root(SID))
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(f"http://127.0.0.1:{info.host_port}/")
    assert r.json()["wrote"] is False
    assert not (workspace.workspace_root(SID) / "pwned.txt").exists()


@pytest.mark.asyncio
async def test_reap_idle_previews_stops_only_what_is_actually_idle(monkeypatch):
    await _skip_unless_usable()
    await workspace.write_file(SID, "index.html", "<html></html>")
    await preview.start_preview(SID, workspace.workspace_root(SID))

    monkeypatch.setattr(_settings(), "preview_idle_timeout_minutes", 0, raising=False)
    # last_used is "now" (monotonic), so a 0-minute cutoff means anything not
    # touched in this same instant counts as idle -- force that by rewinding
    # the recorded timestamp rather than sleeping in a test.
    preview._PREVIEWS[SID].last_used -= 1
    await preview.reap_idle_previews()

    assert preview.get_port(SID) is None
