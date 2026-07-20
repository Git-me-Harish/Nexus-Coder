"""
Tests for the BYOK credential system. `validate_key` is monkeypatched
throughout -- it makes a real network call to the provider's API, which
has no place in a fast unit suite (and no real API keys exist here to
test with anyway). What's under test is the encryption/storage/masking/
resolution logic, not whether a live key happens to be valid.
"""
import pytest

from app.schemas.credential import ValidationResult

pytestmark = pytest.mark.asyncio


def _stub_valid(monkeypatch, is_valid: bool = True, error: str | None = None):
    async def fake_validate(provider: str, api_key: str) -> ValidationResult:
        return ValidationResult(provider=provider, is_valid=is_valid, error=error)

    monkeypatch.setattr("app.services.credential_service.validate_key", fake_validate)


async def test_save_credential_never_returns_raw_key(client, auth_headers, monkeypatch):
    _stub_valid(monkeypatch)
    r = await client.put("/api/providers/credentials/anthropic", json={"apiKey": "sk-ant-realkeyabc123"}, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()["credential"]
    assert "sk-ant-realkeyabc123" not in str(body)
    assert body["keyPreview"].startswith("sk-ant")
    assert body["keyPreview"] != "sk-ant-realkeyabc123"
    assert body["isValid"] is True


async def test_save_credential_records_invalid_result(client, auth_headers, monkeypatch):
    _stub_valid(monkeypatch, is_valid=False, error="Invalid API key")
    r = await client.put("/api/providers/credentials/openai", json={"apiKey": "sk-badkey000000"}, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()["credential"]
    assert body["isValid"] is False
    assert body["lastValidationError"] == "Invalid API key"


async def test_list_credentials_excludes_raw_key(client, auth_headers, monkeypatch):
    _stub_valid(monkeypatch)
    await client.put("/api/providers/credentials/anthropic", json={"apiKey": "sk-ant-secretvalue"}, headers=auth_headers)
    r = await client.get("/api/providers/credentials", headers=auth_headers)
    assert r.status_code == 200
    creds = r.json()["credentials"]
    assert len(creds) == 1
    assert "sk-ant-secretvalue" not in str(creds)


async def test_delete_credential(client, auth_headers, monkeypatch):
    _stub_valid(monkeypatch)
    await client.put("/api/providers/credentials/openai", json={"apiKey": "sk-somekey12345"}, headers=auth_headers)
    r = await client.delete("/api/providers/credentials/openai", headers=auth_headers)
    assert r.status_code == 200
    r = await client.get("/api/providers/credentials", headers=auth_headers)
    assert r.json()["credentials"] == []


async def test_delete_nonexistent_credential_404s(client, auth_headers):
    r = await client.delete("/api/providers/credentials/anthropic", headers=auth_headers)
    assert r.status_code == 404


async def test_save_unsupported_provider_rejected(client, auth_headers, monkeypatch):
    _stub_valid(monkeypatch)
    r = await client.put("/api/providers/credentials/not-a-real-provider", json={"apiKey": "sk-whatever12345"}, headers=auth_headers)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "UNSUPPORTED_PROVIDER"


async def test_credential_is_tenant_isolated(client, monkeypatch):
    _stub_valid(monkeypatch)
    r1 = await client.post("/api/auth/register", json={"email": "credowner@example.com", "password": "password123!"})
    headers1 = {"Authorization": f"Bearer {r1.json()['token']}"}
    await client.put("/api/providers/credentials/anthropic", json={"apiKey": "sk-ant-owner-only"}, headers=headers1)

    r2 = await client.post("/api/auth/register", json={"email": "credother@example.com", "password": "password123!"})
    headers2 = {"Authorization": f"Bearer {r2.json()['token']}"}

    r = await client.get("/api/providers/credentials", headers=headers2)
    assert r.json()["credentials"] == []


async def test_models_available_reflects_configured_credential(client, auth_headers, monkeypatch):
    r = await client.get("/api/models", headers=auth_headers)
    anthropic_models = [m for m in r.json()["models"] if m["provider"] == "anthropic"]
    assert all(m["available"] is False for m in anthropic_models), "should be unavailable with no key configured"

    _stub_valid(monkeypatch)
    await client.put("/api/providers/credentials/anthropic", json={"apiKey": "sk-ant-nowconfigured"}, headers=auth_headers)

    r = await client.get("/api/models", headers=auth_headers)
    anthropic_models = [m for m in r.json()["models"] if m["provider"] == "anthropic"]
    assert all(m["available"] is True for m in anthropic_models), "should become available once a valid key exists"


async def test_agent_stream_returns_provider_not_configured_with_no_keys(client, auth_headers):
    r_proj = await client.post("/api/projects", json={"name": "P"}, headers=auth_headers)
    project_id = r_proj.json()["project"]["id"]
    r_sess = await client.post("/api/sessions", json={"projectId": project_id, "mode": "development"}, headers=auth_headers)
    session_id = r_sess.json()["session"]["id"]

    events = []
    async with client.stream(
        "POST", f"/api/sessions/{session_id}/agent/stream", json={"userMessage": "hello"}, headers=auth_headers
    ) as resp:
        async for line in resp.aiter_lines():
            if line:
                events.append(line)
            if len(events) >= 6:
                break

    joined = "\n".join(events)
    assert "PROVIDER_NOT_CONFIGURED" in joined
    assert "Configure Models" in joined