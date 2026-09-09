"""
Live preview: start/stop a session's preview container, and reverse-proxy
the browser to it. See app/agents/preview.py for the container lifecycle and
why this needs its own signed access token instead of the normal bearer auth.
"""
import logging

import httpx
from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from app.agents import preview, workspace
from app.api.deps import CurrentAuth, DbSession, TenantDb
from app.core.exceptions import api_error
from app.core.security import create_preview_access_token, decode_preview_access_token
from app.services import session_service

router = APIRouter(prefix="/sessions", tags=["preview"])
logger = logging.getLogger("nexus.api.preview")

# Headers that must never be blindly forwarded in either direction -- either
# they're connection-scoped (meaningless/harmful to replay) or Starlette
# recomputes them itself from the actual response body.
_HOP_BY_HOP = {"connection", "keep-alive", "transfer-encoding", "content-encoding", "content-length", "host"}


@router.post("/{session_id}/preview/start")
async def start_preview(session_id: str, auth: CurrentAuth, db: TenantDb):
    session = await session_service.get_session(db, auth.tenant_id, auth.user_id, session_id)
    await workspace.hydrate_from_db(db, session.id)

    try:
        info = await preview.start_preview(session.id, workspace.workspace_root(session.id))
    except preview.PreviewUnsupported as exc:
        raise api_error(409, "PREVIEW_UNSUPPORTED", str(exc))
    except preview.PreviewUnavailable as exc:
        raise api_error(503, "PREVIEW_UNAVAILABLE", str(exc))

    token = create_preview_access_token(session_id=session.id, user_id=auth.user_id, tenant_id=auth.tenant_id)
    return {"proxyPath": f"/api/sessions/{session.id}/preview/proxy/?pt={token}", "kind": info.kind}


@router.delete("/{session_id}/preview")
async def stop_preview(session_id: str, auth: CurrentAuth, db: TenantDb):
    await session_service.get_session(db, auth.tenant_id, auth.user_id, session_id)
    await preview.stop_preview(session_id)
    return {"ok": True}


def _validate_preview_token(session_id: str, pt: str) -> dict:
    claims = decode_preview_access_token(pt)
    if claims is None or claims.get("session_id") != session_id:
        raise api_error(401, "UNAUTHORIZED", "Invalid or expired preview link.")
    return claims


@router.api_route(
    "/{session_id}/preview/proxy/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def proxy_preview(session_id: str, path: str, request: Request, db: DbSession, pt: str = Query(...)):
    """
    Reverse-proxies to the session's preview container. Authenticated by the
    `pt` query-param token (see create_preview_access_token), not the normal
    bearer header -- a bare `<iframe src>` has no way to attach one.
    """
    claims = _validate_preview_token(session_id, pt)
    # Re-validate ownership against the DB rather than trusting the token's
    # claims alone -- a session deleted after the token was issued must not
    # keep proxying.
    await session_service.get_session(db, claims["tenant_id"], claims["sub"], session_id)

    port = preview.get_port(session_id)
    if port is None:
        raise api_error(409, "PREVIEW_NOT_RUNNING", "This preview is not running. Start it again.")
    preview.touch(session_id)

    target_url = f"http://127.0.0.1:{port}/{path}"
    forward_headers = {
        k: v for k, v in request.headers.items() if k.lower() not in _HOP_BY_HOP | {"authorization", "cookie"}
    }
    query = dict(request.query_params)
    query.pop("pt", None)

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            upstream = await client.request(
                request.method, target_url, params=query,
                content=await request.body(), headers=forward_headers,
            )
    except httpx.HTTPError as exc:
        logger.warning("preview proxy failed for session %s: %s", session_id, exc)
        raise api_error(502, "PREVIEW_UNREACHABLE", "The preview app did not respond.")

    response_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in _HOP_BY_HOP}
    return Response(content=upstream.content, status_code=upstream.status_code, headers=response_headers)
