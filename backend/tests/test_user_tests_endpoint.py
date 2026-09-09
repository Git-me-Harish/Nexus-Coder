"""
The Debug phase's user-authored test case endpoint (POST /sessions/{id}/tests).

Real Docker, mirroring test_sandbox.py's skip-if-unavailable pattern -- a
user's test case runs in the exact same sandbox the agent's own run_command
uses, so this exercises real execution, not a stub.
"""
import pytest

from app.agents.sandbox import sandbox_health


async def _skip_unless_sandbox_usable():
    health = await sandbox_health()
    if not health["usable"]:
        pytest.skip(f"sandbox unavailable: {health['detail']}")


@pytest.fixture(autouse=True)
def sandbox_env(tmp_path, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "sandbox_enabled", True, raising=False)


async def _new_session(client, auth_headers):
    r_proj = await client.post("/api/projects", json={"name": "P"}, headers=auth_headers)
    r_sess = await client.post(
        "/api/sessions",
        json={"projectId": r_proj.json()["project"]["id"], "mode": "development"},
        headers=auth_headers,
    )
    return r_sess.json()["session"]["id"]


async def test_a_passing_user_test_case_runs_for_real_and_reports_passed(client, auth_headers):
    await _skip_unless_sandbox_usable()
    session_id = await _new_session(client, auth_headers)

    from app.agents import workspace
    await workspace.write_file(session_id, "app.py", "def add(a, b):\n    return a + b\n")

    r = await client.post(
        f"/api/sessions/{session_id}/tests",
        json={"name": "addition works", "code": "from app import add\ndef test_add():\n    assert add(2, 3) == 5\n"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["passed"] is True
    assert result["exitCode"] == 0
    assert "1 passed" in result["output"]
    assert result["filePath"] == "tests/test_user_addition_works.py"


async def test_a_failing_user_test_case_reports_the_real_failure(client, auth_headers):
    await _skip_unless_sandbox_usable()
    session_id = await _new_session(client, auth_headers)

    from app.agents import workspace
    await workspace.write_file(session_id, "app.py", "def add(a, b):\n    return a - b  # bug\n")

    r = await client.post(
        f"/api/sessions/{session_id}/tests",
        json={"name": "addition works", "code": "from app import add\ndef test_add():\n    assert add(2, 3) == 5\n"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["passed"] is False
    assert result["exitCode"] != 0
    assert "1 failed" in result["output"]


async def test_the_test_file_is_persisted_and_visible_in_the_files_list(client, auth_headers):
    await _skip_unless_sandbox_usable()
    session_id = await _new_session(client, auth_headers)

    from app.agents import workspace
    await workspace.write_file(session_id, "app.py", "x = 1\n")

    await client.post(
        f"/api/sessions/{session_id}/tests",
        json={"name": "Weird Name!!", "code": "def test_trivial():\n    assert True\n"},
        headers=auth_headers,
    )

    r = await client.get(f"/api/sessions/{session_id}/files", headers=auth_headers)
    paths = [f["filePath"] for f in r.json()["files"]]
    assert "tests/test_user_weird_name.py" in paths


async def test_empty_code_is_rejected_before_touching_the_sandbox(client, auth_headers):
    session_id = await _new_session(client, auth_headers)
    r = await client.post(
        f"/api/sessions/{session_id}/tests",
        json={"name": "x", "code": ""},
        headers=auth_headers,
    )
    assert r.status_code == 422
