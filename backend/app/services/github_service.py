"""
GitHub OAuth App integration: connect a user's own GitHub account, then push
a session's workspace to a repo under it.

Two clearly separate concerns, on purpose:
  - CONNECT (authorize/callback) is a standard OAuth Authorization Code
    exchange. The resulting access token is the USER's own GitHub identity --
    stored per-user (GithubConnection), encrypted with the same
    app/core/crypto.py Fernet key ProviderCredential rows already use.
  - PUSH runs `git` as a subprocess directly on the backend host against the
    session's workspace directory (app/agents/workspace.workspace_root) --
    deliberately NOT inside the agent's sandbox. That sandbox is offline by
    design (see app/agents/sandbox.py); a push needs real network, and it is
    a one-off action the USER triggers by clicking a button, never something
    the model decides to do on its own.

KNOWN LIMITATION, stated rather than hidden: each push force-pushes the
workspace's current state as a single commit. The session workspace is a
disposable working copy (see workspace.py's own docs on this), not a
persisted git repo, so there is no incremental history across pushes --
every push is "this is the project's state right now," not "here's what
changed." Building real incremental history would mean keeping a .git
directory alive across workspace wipes/redeploys, which conflicts with the
workspace being explicitly disposable. If that turns out to matter, the fix
is to stop treating the workspace as ephemeral for sessions with a connected
repo -- a bigger change than this pass.
"""
import asyncio
import logging
import re
from pathlib import Path
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.security import (
    create_github_login_state,
    create_github_oauth_state,
    decode_github_login_state,
    decode_github_oauth_state,
)

logger = logging.getLogger("nexus.github")

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
API_BASE = "https://api.github.com"

_SLUG_RE = re.compile(r"[^a-z0-9]+")


class GithubError(RuntimeError):
    """Any failure talking to GitHub or running git -- always a message safe
    to show the user (never contains the access token; see _scrub)."""


def _require_configured() -> tuple[str, str]:
    settings = get_settings()
    if not settings.github_client_id or not settings.github_client_secret:
        raise GithubError(
            "GitHub integration is not configured on this server. An admin needs to register an "
            "OAuth App at github.com/settings/developers and set GITHUB_CLIENT_ID/GITHUB_CLIENT_SECRET."
        )
    return settings.github_client_id, settings.github_client_secret


def build_authorize_url(*, user_id: str, tenant_id: str) -> str:
    client_id, _ = _require_configured()
    settings = get_settings()
    state = create_github_oauth_state(user_id=user_id, tenant_id=tenant_id)
    params = urlencode({
        "client_id": client_id,
        "redirect_uri": settings.github_oauth_redirect_uri,
        "scope": "repo",
        "state": state,
        "allow_signup": "false",
    })
    return f"{AUTHORIZE_URL}?{params}"


def build_login_authorize_url() -> str:
    """
    "Continue with GitHub" on the login screen -- nobody is signed in yet.

    Deliberately reuses the SAME registered redirect_uri as the connect flow:
    a GitHub OAuth App has exactly one Authorization callback URL, and a
    second endpoint would need its own registration (or a subpath of the
    existing one). The shared callback tells the two flows apart by the
    `state` token's type -- see classify_state.

    Scope is only what a sign-in needs (read the profile and the verified
    email); the far broader `repo` scope stays on the connect flow, which is
    the one that actually pushes code.
    """
    client_id, _ = _require_configured()
    settings = get_settings()
    params = urlencode({
        "client_id": client_id,
        "redirect_uri": settings.github_oauth_redirect_uri,
        "scope": "read:user user:email",
        "state": create_github_login_state(),
        "allow_signup": "true",
    })
    return f"{AUTHORIZE_URL}?{params}"


def validate_state(state: str) -> dict:
    """Returns {user_id, tenant_id} or raises GithubError -- the callback has
    no bearer token (it's a bare browser redirect from github.com), so this
    signed, short-lived state param IS the authentication for this request."""
    payload = decode_github_oauth_state(state)
    if payload is None:
        raise GithubError("This GitHub connection link has expired or is invalid. Please try connecting again.")
    return {"user_id": payload["sub"], "tenant_id": payload["tenant_id"]}


def classify_state(state: str) -> tuple[str, dict]:
    """
    Which flow is this callback servicing -- ("connect", {user_id, tenant_id})
    or ("login", {})? Both arrive at the same route (see build_login_authorize_url
    for why), and only the signed state can tell them apart, so an expired or
    forged state must fail here rather than defaulting to either branch.
    """
    connect = decode_github_oauth_state(state)
    if connect is not None:
        return "connect", {"user_id": connect["sub"], "tenant_id": connect["tenant_id"]}

    if decode_github_login_state(state) is not None:
        return "login", {}

    raise GithubError("This GitHub link has expired or is invalid. Please try again.")


async def fetch_github_email(access_token: str) -> str | None:
    """
    The primary VERIFIED email, or None.

    /user.email is null whenever the user keeps their email private, which is
    the default for a lot of accounts -- so sign-in cannot rely on it and asks
    /user/emails (what the `user:email` scope is for) instead. Unverified
    addresses are skipped on purpose: matching an existing Nexus account by an
    unverified address would let anyone who adds someone else's email to their
    GitHub account take over that Nexus account.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{API_BASE}/user/emails", headers=_auth_headers(access_token))
        if r.status_code != 200:
            return None
        emails = r.json()

    verified = [e for e in emails if e.get("verified")]
    primary = next((e for e in verified if e.get("primary")), None)
    chosen = primary or (verified[0] if verified else None)
    return chosen["email"].lower() if chosen else None


async def exchange_code_for_token(code: str) -> str:
    client_id, client_secret = _require_configured()
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": client_id, "client_secret": client_secret,
                "code": code, "redirect_uri": settings.github_oauth_redirect_uri,
            },
        )
        r.raise_for_status()
        data = r.json()

    if "error" in data:
        raise GithubError(data.get("error_description") or data["error"])
    token = data.get("access_token")
    if not token:
        raise GithubError("GitHub did not return an access token.")
    return token


async def fetch_github_identity(access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{API_BASE}/user", headers=_auth_headers(access_token))
        r.raise_for_status()
        return r.json()


def _auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"}


def encrypt_token(token: str) -> str:
    return encrypt_secret(token)


def decrypt_token(ciphertext: str) -> str:
    return decrypt_secret(ciphertext)


def repo_name_for_session(*, project_name: str, session_id: str) -> str:
    slug = _SLUG_RE.sub("-", (project_name or "nexus-project").strip().lower()).strip("-") or "nexus-project"
    return f"{slug}-{session_id[:8]}"


async def create_or_get_repo(access_token: str, *, name: str) -> dict:
    """Creates a private repo under the connected user's account, or returns
    the existing one if a prior push already created it (idempotent by
    design -- pushing twice must not error on 'name already exists')."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            f"{API_BASE}/user/repos", headers=_auth_headers(access_token),
            json={"name": name, "private": True, "auto_init": False,
                  "description": "Created by Nexus Coder"},
        )
        if r.status_code == 201:
            return r.json()

        already_exists = r.status_code == 422 and any(
            "already exists" in e.get("message", "") for e in r.json().get("errors", [])
        )
        if not already_exists:
            raise GithubError(f"GitHub rejected repo creation: {r.text[:300]}")

        identity = await fetch_github_identity(access_token)
        r = await client.get(f"{API_BASE}/repos/{identity['login']}/{name}", headers=_auth_headers(access_token))
        r.raise_for_status()
        return r.json()


def _scrub(text: str, access_token: str) -> str:
    """Never let the token reach a log line or an error shown to the user."""
    return text.replace(access_token, "***")


async def _run_git(args: list[str], *, cwd: Path, access_token: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        "git", *args, cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise GithubError(_scrub(stderr.decode("utf-8", errors="replace").strip() or f"git {args[0]} failed", access_token))


def _remote_url(full_name: str, access_token: str) -> str:
    """Split out so tests can point the real push_workspace at a local
    throwaway bare repo instead of github.com, without reimplementing the
    git command sequence being tested."""
    return f"https://x-access-token:{access_token}@github.com/{full_name}.git"


async def push_workspace(root: Path, *, access_token: str, full_name: str, branch: str = "main") -> None:
    """
    Pushes the workspace directory as a single commit to `full_name`
    ("owner/repo"), force-pushing `branch`. See the module docstring for why
    this is single-commit, not incremental history.
    """
    remote = _remote_url(full_name, access_token)

    await _run_git(["init", "-b", branch], cwd=root, access_token=access_token)
    await _run_git(["add", "-A"], cwd=root, access_token=access_token)
    await _run_git(
        ["-c", "user.email=nexus-agent@local", "-c", "user.name=Nexus Coder",
         "commit", "-m", "Push from Nexus Coder", "--allow-empty"],
        cwd=root, access_token=access_token,
    )
    # A prior push already added "origin" -- ignore that failure, but not any other.
    try:
        await _run_git(["remote", "remove", "origin"], cwd=root, access_token=access_token)
    except GithubError:
        pass
    await _run_git(["remote", "add", "origin", remote], cwd=root, access_token=access_token)
    await _run_git(["push", "--force", "-u", "origin", branch], cwd=root, access_token=access_token)
