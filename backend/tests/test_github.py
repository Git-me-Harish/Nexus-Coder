"""
GitHub OAuth connect + push.

Everything that talks to github.com is mocked (httpx calls in
app/services/github_service.py) -- no real GitHub account is needed for this
suite. The only thing that needs your own registered OAuth App and a real
account is a manual click-through; see the plan doc / README for those
setup steps. `git` subprocess calls (push_workspace) are also mocked here --
they're exercised for real in test_github_push_workspace_runs_real_git
against a real, throwaway local git remote, so the actual command sequence
is proven correct without hitting github.com.
"""
import subprocess

import pytest

from app.services import github_service


@pytest.fixture(autouse=True)
def github_oauth_configured(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "github_client_id", "test-client-id", raising=False)
    monkeypatch.setattr(settings, "github_client_secret", "test-client-secret", raising=False)


async def _register_and_headers(client, email="githubtester@example.com"):
    r = await client.post("/api/auth/register", json={"email": email, "password": "password123!"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


# --- authorize / state -------------------------------------------------------


async def test_authorize_returns_a_real_github_url_with_signed_state(client, auth_headers):
    r = await client.get("/api/integrations/github/authorize", headers=auth_headers)
    assert r.status_code == 200
    url = r.json()["url"]
    assert url.startswith("https://github.com/login/oauth/authorize")
    assert "client_id=test-client-id" in url
    assert "state=" in url


async def test_authorize_without_configured_oauth_app_fails_clearly(client, auth_headers, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "github_client_id", None, raising=False)

    r = await client.get("/api/integrations/github/authorize", headers=auth_headers)
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "GITHUB_NOT_CONFIGURED"


def test_state_token_round_trips_and_rejects_tampering():
    from app.core.security import create_github_oauth_state, decode_github_oauth_state

    token = create_github_oauth_state(user_id="u1", tenant_id="t1")
    claims = decode_github_oauth_state(token)
    assert claims["sub"] == "u1" and claims["tenant_id"] == "t1"

    assert decode_github_oauth_state(token + "x") is None
    assert decode_github_oauth_state("not-a-jwt-at-all") is None


# --- callback -----------------------------------------------------------------


async def test_callback_with_invalid_state_redirects_with_an_error(client):
    r = await client.get("/api/integrations/github/callback", params={"code": "abc", "state": "bad-state"})
    assert r.status_code in (302, 307)
    assert "github=error" in r.headers["location"]


async def test_callback_success_stores_the_encrypted_token_and_redirects_connected(client, auth_headers, monkeypatch):
    from app.core.security import create_github_oauth_state

    async def fake_exchange(code):
        assert code == "the-code"
        return "gho_faketoken123"

    async def fake_identity(token):
        assert token == "gho_faketoken123"
        return {"login": "octocat", "id": 583231}

    monkeypatch.setattr(github_service, "exchange_code_for_token", fake_exchange)
    monkeypatch.setattr(github_service, "fetch_github_identity", fake_identity)

    r_reg = await client.post("/api/auth/register", json={"email": "cbuser@example.com", "password": "password123!"})
    token = r_reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Decode the real access token to get user_id/tenant_id for the state,
    # exactly as the frontend would after calling /authorize.
    import jwt as pyjwt
    from app.core.config import get_settings
    claims = pyjwt.decode(token, get_settings().jwt_secret, algorithms=[get_settings().jwt_algorithm],
                          options={"verify_signature": True})
    state = create_github_oauth_state(user_id=claims["sub"], tenant_id=claims["tenant_id"])

    r = await client.get("/api/integrations/github/callback", params={"code": "the-code", "state": state})
    assert r.status_code in (302, 307)
    assert "github=connected" in r.headers["location"]

    r_status = await client.get("/api/integrations/github/status", headers=headers)
    assert r_status.json() == {"connected": True, "githubLogin": "octocat"}

    # Stored encrypted -- never plaintext in the DB.
    from sqlalchemy import select
    import app.db.session as dbsession
    from app.models.github import GithubConnection
    async with dbsession.AsyncSessionLocal() as db:
        row = (await db.execute(select(GithubConnection).where(GithubConnection.user_id == claims["sub"]))).scalar_one()
        assert "faketoken" not in row.encrypted_access_token


async def test_disconnect_removes_the_connection(client, auth_headers, monkeypatch):
    monkeypatch.setattr(github_service, "exchange_code_for_token", lambda code: _async_return("gho_x"))
    monkeypatch.setattr(github_service, "fetch_github_identity", lambda t: _async_return({"login": "o", "id": 1}))

    from app.core.security import create_github_oauth_state
    import jwt as pyjwt
    from app.core.config import get_settings
    token = auth_headers["Authorization"].split(" ")[1]
    claims = pyjwt.decode(token, get_settings().jwt_secret, algorithms=[get_settings().jwt_algorithm])
    state = create_github_oauth_state(user_id=claims["sub"], tenant_id=claims["tenant_id"])
    await client.get("/api/integrations/github/callback", params={"code": "c", "state": state})

    r = await client.delete("/api/integrations/github/disconnect", headers=auth_headers)
    assert r.json() == {"ok": True}

    r_status = await client.get("/api/integrations/github/status", headers=auth_headers)
    assert r_status.json()["connected"] is False


async def _async_return(value):
    return value


# --- push ---------------------------------------------------------------------


async def test_push_without_a_connected_account_is_rejected(client, auth_headers):
    r_proj = await client.post("/api/projects", json={"name": "P"}, headers=auth_headers)
    r_sess = await client.post(
        "/api/sessions",
        json={"projectId": r_proj.json()["project"]["id"], "mode": "development"},
        headers=auth_headers,
    )
    session_id = r_sess.json()["session"]["id"]

    r = await client.post(f"/api/sessions/{session_id}/github/push", headers=auth_headers)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "GITHUB_NOT_CONNECTED"


async def test_push_with_an_empty_workspace_is_rejected(client, auth_headers, monkeypatch, tmp_path):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "workspace_root", str(tmp_path), raising=False)

    monkeypatch.setattr(github_service, "exchange_code_for_token", lambda code: _async_return("gho_x"))
    monkeypatch.setattr(github_service, "fetch_github_identity", lambda t: _async_return({"login": "o", "id": 1}))
    from app.core.security import create_github_oauth_state
    import jwt as pyjwt
    token = auth_headers["Authorization"].split(" ")[1]
    claims = pyjwt.decode(token, get_settings().jwt_secret, algorithms=[get_settings().jwt_algorithm])
    state = create_github_oauth_state(user_id=claims["sub"], tenant_id=claims["tenant_id"])
    await client.get("/api/integrations/github/callback", params={"code": "c", "state": state})

    r_proj = await client.post("/api/projects", json={"name": "P"}, headers=auth_headers)
    r_sess = await client.post(
        "/api/sessions",
        json={"projectId": r_proj.json()["project"]["id"], "mode": "development"},
        headers=auth_headers,
    )
    session_id = r_sess.json()["session"]["id"]

    r = await client.post(f"/api/sessions/{session_id}/github/push", headers=auth_headers)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "WORKSPACE_EMPTY"


async def test_full_push_flow_creates_repo_and_pushes(client, auth_headers, monkeypatch, tmp_path):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "workspace_root", str(tmp_path), raising=False)

    monkeypatch.setattr(github_service, "exchange_code_for_token", lambda code: _async_return("gho_x"))
    monkeypatch.setattr(github_service, "fetch_github_identity", lambda t: _async_return({"login": "octocat", "id": 1}))
    from app.core.security import create_github_oauth_state
    import jwt as pyjwt
    token = auth_headers["Authorization"].split(" ")[1]
    claims = pyjwt.decode(token, get_settings().jwt_secret, algorithms=[get_settings().jwt_algorithm])
    state = create_github_oauth_state(user_id=claims["sub"], tenant_id=claims["tenant_id"])
    await client.get("/api/integrations/github/callback", params={"code": "c", "state": state})

    r_proj = await client.post("/api/projects", json={"name": "My Project"}, headers=auth_headers)
    r_sess = await client.post(
        "/api/sessions",
        json={"projectId": r_proj.json()["project"]["id"], "mode": "development"},
        headers=auth_headers,
    )
    session_id = r_sess.json()["session"]["id"]

    from app.agents import workspace
    await workspace.write_file(session_id, "app.py", "print('hi')")

    created = {}

    async def fake_create_or_get_repo(access_token, *, name):
        created["name"] = name
        assert access_token == "gho_x"
        return {"full_name": "octocat/" + name, "html_url": f"https://github.com/octocat/{name}"}

    pushed = {}

    async def fake_push_workspace(root, *, access_token, full_name, branch="main"):
        pushed["full_name"] = full_name
        pushed["root_exists"] = root.exists()

    monkeypatch.setattr(github_service, "create_or_get_repo", fake_create_or_get_repo)
    monkeypatch.setattr(github_service, "push_workspace", fake_push_workspace)

    r = await client.post(f"/api/sessions/{session_id}/github/push", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["repoUrl"] == f"https://github.com/octocat/{created['name']}"
    assert pushed["full_name"] == "octocat/" + created["name"]
    assert pushed["root_exists"] is True
    assert "my-project" in created["name"]

    # A second push must reuse the already-created repo, not create another.
    r2 = await client.post(f"/api/sessions/{session_id}/github/push", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["repoUrl"] == r.json()["repoUrl"]


# --- push_workspace's actual git command sequence, against a real local repo -


@pytest.mark.asyncio
async def test_github_push_workspace_runs_real_git(tmp_path, monkeypatch):
    """Runs the ACTUAL push_workspace -- init, add, commit, remote,
    force-push -- against a real (local, throwaway) bare repo standing in
    for github.com. Only _remote_url is redirected; every git command is the
    real one. No network, no real GitHub account needed."""
    workdir = tmp_path / "workspace"
    workdir.mkdir()
    (workdir / "app.py").write_text("print('hi')")

    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
    remote_url = str(bare).replace("\\", "/")

    monkeypatch.setattr(github_service, "_remote_url", lambda full_name, access_token: remote_url)

    await github_service.push_workspace(workdir, access_token="unused", full_name="octocat/whatever")

    log = subprocess.run(
        ["git", "--git-dir", str(bare), "log", "--oneline", "main"],
        check=True, capture_output=True, text=True,
    )
    assert log.stdout.strip() != ""

    # Pushing again (the "second push reuses the repo" case) must not error
    # even though origin/main already exists -- this is what --force and the
    # remote-remove-then-add dance are for.
    (workdir / "app.py").write_text("print('changed')")
    await github_service.push_workspace(workdir, access_token="unused", full_name="octocat/whatever")
