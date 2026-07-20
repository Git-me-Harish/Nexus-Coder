import pytest

pytestmark = pytest.mark.asyncio


async def test_register_creates_own_tenant(client):
    r1 = await client.post("/api/auth/register", json={"email": "alice@example.com", "password": "password123!", "name": "Alice"})
    r2 = await client.post("/api/auth/register", json={"email": "bob@example.com", "password": "password123!", "name": "Bob"})
    assert r1.status_code == 201 and r2.status_code == 201
    # Each signup must get its own tenant -- not a shared default. See
    # app/services/auth_service.py for why this matters.
    assert r1.json()["tenant"]["id"] != r2.json()["tenant"]["id"]


async def test_duplicate_email_returns_409_not_500(client):
    payload = {"email": "dupe@example.com", "password": "password123!", "name": "First"}
    r1 = await client.post("/api/auth/register", json=payload)
    r2 = await client.post("/api/auth/register", json={**payload, "name": "Second"})
    assert r1.status_code == 201
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "EMAIL_TAKEN"


async def test_weak_password_rejected(client):
    r = await client.post("/api/auth/register", json={"email": "weak@example.com", "password": "alllettersnodigits"})
    assert r.status_code == 422


async def test_login_wrong_password_401(client):
    await client.post("/api/auth/register", json={"email": "login@example.com", "password": "password123!"})
    r = await client.post("/api/auth/login", json={"email": "login@example.com", "password": "wrongpassword1"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_login_nonexistent_user_401_not_404(client):
    """Must not leak account existence via a different status code."""
    r = await client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "whatever123"})
    assert r.status_code == 401


async def test_refresh_rotates_token(client):
    r = await client.post("/api/auth/register", json={"email": "rotate@example.com", "password": "password123!"})
    old_access, old_refresh = r.json()["token"], r.json()["refreshToken"]

    r2 = await client.post("/api/auth/refresh", json={"refreshToken": old_refresh})
    assert r2.status_code == 200
    assert r2.json()["token"] != old_access
    assert r2.json()["refreshToken"] != old_refresh


async def test_refresh_reuse_detected_and_revokes_family(client):
    r = await client.post("/api/auth/register", json={"email": "reuse@example.com", "password": "password123!"})
    old_refresh = r.json()["refreshToken"]

    r2 = await client.post("/api/auth/refresh", json={"refreshToken": old_refresh})
    assert r2.status_code == 200
    new_refresh = r2.json()["refreshToken"]

    # Reusing the now-rotated-away token must fail...
    r3 = await client.post("/api/auth/refresh", json={"refreshToken": old_refresh})
    assert r3.status_code == 401
    assert r3.json()["error"]["code"] == "REFRESH_REUSE_DETECTED"

    # ...and must have revoked the whole family, including the token that
    # legitimately replaced it.
    r4 = await client.post("/api/auth/refresh", json={"refreshToken": new_refresh})
    assert r4.status_code == 401


async def test_unauthenticated_request_401(client):
    r = await client.get("/api/projects")
    assert r.status_code == 401


async def test_me_requires_valid_token(client, auth_headers):
    r = await client.get("/api/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "test@example.com"