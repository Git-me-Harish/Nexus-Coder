"""
GitHub OAuth connect flow + per-session push. See app/services/github_service.py
for the design rationale (why push runs on the host, not in the sandbox; why
history is single-commit).
"""
import logging
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.agents import workspace
from app.api.deps import CurrentAuth, DbSession, TenantDb
from app.core.config import get_settings
from app.core.exceptions import api_error
from app.core.security import create_auth_exchange_token
from app.models.github import GithubConnection
from app.models.project import Project
from app.services import auth_service, github_service, session_service

router = APIRouter(tags=["github"])
logger = logging.getLogger("nexus.api.github")


@router.get("/integrations/github/authorize")
async def github_authorize(auth: CurrentAuth):
    try:
        url = github_service.build_authorize_url(user_id=auth.user_id, tenant_id=auth.tenant_id)
    except github_service.GithubError as exc:
        raise api_error(503, "GITHUB_NOT_CONFIGURED", str(exc))
    return {"url": url}


@router.get("/integrations/github/callback")
async def github_callback(code: str, state: str, db: DbSession):
    """
    Hit by a bare browser redirect from github.com -- there is no bearer
    token here, so identity comes entirely from the signed `state`.

    ONE route serves two different flows, because a GitHub OAuth App has a
    single registered callback URL:
      - connect  (state = github_oauth_state, minted while signed in) stores
        a repo-scoped token for pushing a session's workspace.
      - sign-in  (state = github_login_state, minted by the login screen)
        creates or signs in a user and hands the frontend a one-time
        exchange code.
    `classify_state` is what keeps them apart; a forged or expired state
    matches neither and fails closed.

    Always redirects back to the frontend -- errors surface as a query param
    rather than a raw API error page, since a human's browser lands here.
    """
    frontend = get_settings().frontend_base_url
    try:
        flow, claims = github_service.classify_state(state)
        access_token = await github_service.exchange_code_for_token(code)
        identity = await github_service.fetch_github_identity(access_token)

        if flow == "login":
            # Deliberately NOT identity["email"] (the account's public email):
            # only /user/emails states verification, and account matching is
            # only safe on a verified address. See fetch_github_email.
            email = await github_service.fetch_github_email(access_token)
            user, tenant = await auth_service.login_or_register_with_github(
                db,
                github_user_id=str(identity["id"]),
                login=identity["login"],
                email=email.lower() if email else None,
                name=identity.get("name"),
                avatar_url=identity.get("avatar_url"),
            )
            exchange = create_auth_exchange_token(user_id=user.id, tenant_id=tenant.id)
            return RedirectResponse(f"{frontend}/?auth=github&code={quote(exchange)}")

        existing = (await db.execute(
            select(GithubConnection).where(GithubConnection.user_id == claims["user_id"])
        )).scalar_one_or_none()
        if existing:
            existing.encrypted_access_token = github_service.encrypt_token(access_token)
            existing.github_login = identity["login"]
            existing.github_user_id = identity["id"]
        else:
            db.add(GithubConnection(
                user_id=claims["user_id"], tenant_id=claims["tenant_id"],
                encrypted_access_token=github_service.encrypt_token(access_token),
                github_login=identity["login"], github_user_id=identity["id"],
            ))
        await db.commit()
        return RedirectResponse(f"{frontend}/?github=connected")
    except github_service.GithubError as exc:
        logger.warning("GitHub OAuth callback failed: %s", exc)
        return RedirectResponse(f"{frontend}/?github=error&message={quote(str(exc))}")
    except HTTPException as exc:
        # e.g. a GitHub account with no verified email -- a real, explainable
        # outcome for the user, not a 500 page in the middle of an OAuth hop.
        # api_error() puts {"code", "message"} straight on `detail`.
        detail = exc.detail
        message = detail.get("message") if isinstance(detail, dict) else str(detail)
        logger.warning("GitHub sign-in rejected: %s", message)
        return RedirectResponse(f"{frontend}/?auth=error&message={quote(str(message))}")


@router.delete("/integrations/github/disconnect")
async def github_disconnect(auth: CurrentAuth, db: DbSession):
    existing = (await db.execute(
        select(GithubConnection).where(GithubConnection.user_id == auth.user_id)
    )).scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.commit()
    return {"ok": True}


@router.get("/integrations/github/status")
async def github_status(auth: CurrentAuth, db: DbSession):
    existing = (await db.execute(
        select(GithubConnection).where(GithubConnection.user_id == auth.user_id)
    )).scalar_one_or_none()
    return {"connected": existing is not None, "githubLogin": existing.github_login if existing else None}


@router.post("/sessions/{session_id}/github/push")
async def push_to_github(session_id: str, auth: CurrentAuth, db: TenantDb):
    session = await session_service.get_session(db, auth.tenant_id, auth.user_id, session_id)

    connection = (await db.execute(
        select(GithubConnection).where(GithubConnection.user_id == auth.user_id)
    )).scalar_one_or_none()
    if connection is None:
        raise api_error(409, "GITHUB_NOT_CONNECTED", "Connect your GitHub account before pushing.")

    try:
        access_token = github_service.decrypt_token(connection.encrypted_access_token)
    except ValueError as exc:
        raise api_error(409, "GITHUB_TOKEN_INVALID", str(exc))

    await workspace.hydrate_from_db(db, session.id)
    if not workspace.list_workspace_files(session.id):
        raise api_error(409, "WORKSPACE_EMPTY", "There is nothing in the workspace to push yet.")

    try:
        if session.github_repo_url:
            # Already created on a prior push -- reuse it rather than
            # creating a second repo for the same session.
            full_name = session.github_repo_url.split("github.com/")[-1].rstrip("/")
            repo = {"full_name": full_name, "html_url": session.github_repo_url}
        else:
            project = await db.get(Project, session.project_id)
            repo_name = github_service.repo_name_for_session(
                project_name=project.name if project else session.title or "", session_id=session.id,
            )
            repo = await github_service.create_or_get_repo(access_token, name=repo_name)

        await github_service.push_workspace(
            workspace.workspace_root(session.id), access_token=access_token, full_name=repo["full_name"],
        )
    except github_service.GithubError as exc:
        raise api_error(502, "GITHUB_PUSH_FAILED", str(exc))

    session.github_repo_url = repo["html_url"]
    await db.commit()
    return {"repoUrl": repo["html_url"]}
