"""
Forgot/reset password flow.

The security properties here are the reason this file exists -- an
account-enumeration leak or a replayable link would both be silent bugs that
still "work" in a happy-path click-through.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.security import hash_password_reset_token
from app.models.user import PasswordResetToken, RefreshToken, User


async def _register(client, email="reset-me@example.com", password="original123!pw"):
    r = await client.post("/api/auth/register", json={
        "email": email, "password": password, "name": "Reset Me",
    })
    assert r.status_code == 201, r.text
    return r.json()


async def _request_reset(client, monkeypatch, email):
    """Runs the forgot-password route and returns the raw token from the link
    the email backend was handed (nothing else ever sees it)."""
    sent: dict = {}

    async def fake_send(*, to, link, ttl_minutes):
        sent["to"] = to
        sent["token"] = link.split("reset_token=")[-1]

    import app.services.email_service as email_service
    monkeypatch.setattr(email_service, "send_password_reset", fake_send)

    r = await client.post("/api/auth/forgot-password", json={"email": email})
    assert r.status_code == 200, r.text
    return r, sent


async def test_forgot_password_does_not_reveal_whether_account_exists(client, monkeypatch):
    await _register(client)

    known, _ = await _request_reset(client, monkeypatch, "reset-me@example.com")
    unknown, unknown_sent = await _request_reset(client, monkeypatch, "nobody-here@example.com")

    assert known.status_code == unknown.status_code
    assert known.json() == unknown.json()
    # ...and no email was generated for the address that does not exist.
    assert unknown_sent == {}


async def test_reset_link_sets_new_password_and_signs_in(client, monkeypatch):
    await _register(client)
    _, sent = await _request_reset(client, monkeypatch, "reset-me@example.com")

    r = await client.post("/api/auth/reset-password", json={
        "token": sent["token"], "newPassword": "brand-new-99!pw",
    })
    assert r.status_code == 200, r.text
    assert r.json()["token"] and r.json()["refreshToken"]

    old = await client.post("/api/auth/login", json={
        "email": "reset-me@example.com", "password": "original123!pw",
    })
    assert old.status_code == 401

    new = await client.post("/api/auth/login", json={
        "email": "reset-me@example.com", "password": "brand-new-99!pw",
    })
    assert new.status_code == 200


async def test_reset_link_is_single_use(client, monkeypatch):
    await _register(client)
    _, sent = await _request_reset(client, monkeypatch, "reset-me@example.com")

    first = await client.post("/api/auth/reset-password", json={
        "token": sent["token"], "newPassword": "brand-new-99!pw",
    })
    assert first.status_code == 200

    replay = await client.post("/api/auth/reset-password", json={
        "token": sent["token"], "newPassword": "attacker-pick-1!",
    })
    assert replay.status_code == 400
    assert replay.json()["error"]["code"] == "INVALID_RESET_TOKEN"

    # The replay must not have changed anything.
    assert (await client.post("/api/auth/login", json={
        "email": "reset-me@example.com", "password": "brand-new-99!pw",
    })).status_code == 200


async def test_expired_link_is_rejected(client, db_session, monkeypatch):
    await _register(client)
    _, sent = await _request_reset(client, monkeypatch, "reset-me@example.com")

    row = (await db_session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_password_reset_token(sent["token"])
        )
    )).scalar_one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.commit()

    r = await client.post("/api/auth/reset-password", json={
        "token": sent["token"], "newPassword": "brand-new-99!pw",
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_RESET_TOKEN"


async def test_unknown_token_is_rejected(client):
    r = await client.post("/api/auth/reset-password", json={
        "token": "not-a-real-token", "newPassword": "brand-new-99!pw",
    })
    assert r.status_code == 400


async def test_reset_revokes_existing_sessions(client, db_session, monkeypatch):
    session = await _register(client)
    old_refresh = session["refreshToken"]

    _, sent = await _request_reset(client, monkeypatch, "reset-me@example.com")
    await client.post("/api/auth/reset-password", json={
        "token": sent["token"], "newPassword": "brand-new-99!pw",
    })

    # The session held before the reset can no longer be refreshed.
    r = await client.post("/api/auth/refresh", json={"refreshToken": old_refresh})
    assert r.status_code == 401


async def test_requesting_again_supersedes_the_previous_link(client, db_session, monkeypatch):
    """Only the newest link may work -- and the throttle must not silently
    hand back a stale one."""
    await _register(client)
    _, first = await _request_reset(client, monkeypatch, "reset-me@example.com")

    # Age the first token past the 60s per-account throttle so a second issues.
    row = (await db_session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_password_reset_token(first["token"])
        )
    )).scalar_one()
    row.created_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    await db_session.commit()

    _, second = await _request_reset(client, monkeypatch, "reset-me@example.com")
    assert second["token"] != first["token"]

    stale = await client.post("/api/auth/reset-password", json={
        "token": first["token"], "newPassword": "brand-new-99!pw",
    })
    assert stale.status_code == 400

    fresh = await client.post("/api/auth/reset-password", json={
        "token": second["token"], "newPassword": "brand-new-99!pw",
    })
    assert fresh.status_code == 200


async def test_rapid_second_request_is_throttled(client, monkeypatch):
    await _register(client)
    _, first = await _request_reset(client, monkeypatch, "reset-me@example.com")
    r, second = await _request_reset(client, monkeypatch, "reset-me@example.com")

    # Same generic response, but no second email at the victim's inbox.
    assert r.status_code == 200
    assert second == {}
    assert first["token"]


async def test_weak_new_password_is_rejected(client, monkeypatch):
    await _register(client)
    _, sent = await _request_reset(client, monkeypatch, "reset-me@example.com")

    r = await client.post("/api/auth/reset-password", json={
        "token": sent["token"], "newPassword": "onlylettershere",
    })
    assert r.status_code == 422

    # ...and the link survives a rejected attempt, so the user can retry.
    ok = await client.post("/api/auth/reset-password", json={
        "token": sent["token"], "newPassword": "brand-new-99!pw",
    })
    assert ok.status_code == 200


async def test_changing_password_invalidates_outstanding_reset_links(client, monkeypatch):
    """A link mailed before a deliberate change must not be able to undo it."""
    session = await _register(client)
    _, sent = await _request_reset(client, monkeypatch, "reset-me@example.com")

    changed = await client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {session['token']}"},
        json={"currentPassword": "original123!pw", "newPassword": "deliberate-1!pw"},
    )
    assert changed.status_code == 200, changed.text

    r = await client.post("/api/auth/reset-password", json={
        "token": sent["token"], "newPassword": "attacker-pick-1!",
    })
    assert r.status_code == 400


async def test_reset_sets_a_first_password_for_a_github_account(client, db_session, monkeypatch):
    """GitHub sign-ups have no password; proving control of the verified email
    is a legitimate way to add one."""
    from app.services import auth_service

    user, _ = await auth_service.login_or_register_with_github(
        db_session, github_user_id="90210", login="ghuser",
        email="gh-reset@example.com", name="GH User", avatar_url=None,
    )
    assert user.has_password is False

    _, sent = await _request_reset(client, monkeypatch, "gh-reset@example.com")
    r = await client.post("/api/auth/reset-password", json={
        "token": sent["token"], "newPassword": "first-password1!",
    })
    assert r.status_code == 200
    assert r.json()["user"]["hasPassword"] is True

    login = await client.post("/api/auth/login", json={
        "email": "gh-reset@example.com", "password": "first-password1!",
    })
    assert login.status_code == 200


async def test_only_the_token_hash_is_stored(client, db_session, monkeypatch):
    """The raw token lives in the user's inbox and nowhere else."""
    await _register(client)
    _, sent = await _request_reset(client, monkeypatch, "reset-me@example.com")

    rows = (await db_session.execute(select(PasswordResetToken))).scalars().all()
    assert len(rows) == 1
    assert rows[0].token_hash != sent["token"]
    assert rows[0].token_hash == hash_password_reset_token(sent["token"])
