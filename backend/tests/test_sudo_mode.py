"""
Step-up ("sudo") auth on the provider-credential routes.

The point of these tests is that the protection is REAL -- enforced by the
API, not by the UI declining to render a screen. A gate that only exists in
the frontend is not a gate.
"""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import TokenType, create_sudo_token
from app.schemas.credential import ValidationResult

CREDENTIAL_ROUTES = [
    ("get", "/api/providers/credentials", None),
    ("put", "/api/providers/credentials/anthropic", {"apiKey": "sk-ant-something123"}),
    ("post", "/api/providers/credentials/anthropic/validate", None),
    ("delete", "/api/providers/credentials/anthropic", None),
]


def _stub_valid(monkeypatch):
    async def fake_validate(provider: str, api_key: str) -> ValidationResult:
        return ValidationResult(provider=provider, is_valid=True, error=None)

    monkeypatch.setattr("app.services.credential_service.validate_key", fake_validate)


async def _call(client, method: str, url: str, body, headers):
    kwargs = {"headers": headers}
    if body is not None:
        kwargs["json"] = body
    return await getattr(client, method)(url, **kwargs)


@pytest.mark.parametrize("method,url,body", CREDENTIAL_ROUTES)
async def test_signed_in_alone_cannot_touch_credentials(client, auth_headers, method, url, body):
    """A valid session is not enough on any of these routes."""
    r = await _call(client, method, url, body, auth_headers)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "SUDO_REQUIRED"


@pytest.mark.parametrize("method,url,body", CREDENTIAL_ROUTES)
async def test_elevation_unlocks_credentials(client, sudo_headers, monkeypatch, method, url, body):
    _stub_valid(monkeypatch)
    r = await _call(client, method, url, body, sudo_headers)
    assert r.status_code != 403, r.text


async def test_sudo_requires_the_correct_password(client, auth_headers):
    r = await client.post("/api/auth/sudo", json={"password": "not-my-password"}, headers=auth_headers)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_PASSWORD"


async def test_sudo_requires_a_session(client):
    r = await client.post("/api/auth/sudo", json={"password": "password123!"})
    assert r.status_code == 401


async def test_expired_elevation_is_rejected(client, auth_headers, monkeypatch):
    """The window is short on purpose; once it lapses the API asks again."""
    settings = get_settings()
    me = await client.get("/api/auth/me", headers=auth_headers)
    user_id = me.json()["user"]["id"]
    tenant_id = me.json()["tenant"]["id"]

    now = datetime.now(timezone.utc)
    stale = jwt.encode(
        {
            "sub": user_id, "tenant_id": tenant_id, "type": TokenType.SUDO.value,
            "iat": now - timedelta(minutes=30), "exp": now - timedelta(minutes=20),
            "iss": "nexus-api", "jti": "expiredtoken",
        },
        settings.jwt_secret, algorithm=settings.jwt_algorithm,
    )

    r = await client.get("/api/providers/credentials", headers={**auth_headers, "X-Sudo-Token": stale})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "SUDO_REQUIRED"


async def test_another_users_elevation_does_not_transfer(client, auth_headers):
    """An elevation is bound to the account it was issued for -- otherwise one
    user's confirmation would unlock everybody's keys."""
    other = await client.post("/api/auth/register", json={
        "email": "sudo-other@example.com", "password": "password123!",
    })
    other_headers = {"Authorization": f"Bearer {other.json()['token']}"}
    elevated = await client.post("/api/auth/sudo", json={"password": "password123!"}, headers=other_headers)
    stolen = elevated.json()["token"]

    # Someone else's valid sudo token, presented on this session.
    r = await client.get("/api/providers/credentials", headers={**auth_headers, "X-Sudo-Token": stolen})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "SUDO_REQUIRED"


async def test_garbage_and_wrong_type_tokens_are_rejected(client, auth_headers):
    for bad in ["not-a-jwt", ""]:
        r = await client.get("/api/providers/credentials", headers={**auth_headers, "X-Sudo-Token": bad})
        assert r.status_code == 403

    # A normal ACCESS token must not double as an elevation.
    access = auth_headers["Authorization"].removeprefix("Bearer ")
    r = await client.get("/api/providers/credentials", headers={**auth_headers, "X-Sudo-Token": access})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "SUDO_REQUIRED"


async def test_github_account_without_password_is_told_to_set_one(client, db_session):
    from app.services import auth_service

    user, tenant = await auth_service.login_or_register_with_github(
        db_session, github_user_id="7777", login="nopass",
        email="sudo-github@example.com", name="No Pass", avatar_url=None,
    )
    assert user.has_password is False

    from app.core.security import create_access_token
    token = create_access_token(user_id=user.id, tenant_id=tenant.id, email=user.email)

    r = await client.post(
        "/api/auth/sudo", json={"password": "anything-at-all"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "PASSWORD_NOT_SET"


async def test_sudo_token_is_not_accepted_as_a_session_token(client, auth_headers):
    """Elevation proves a password was re-entered; it is not a login."""
    me = await client.get("/api/auth/me", headers=auth_headers)
    sudo = create_sudo_token(user_id=me.json()["user"]["id"], tenant_id=me.json()["tenant"]["id"])

    r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {sudo}"})
    assert r.status_code == 401
