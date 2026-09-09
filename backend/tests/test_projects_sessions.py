import pytest

pytestmark = pytest.mark.asyncio


async def test_create_and_list_projects(client, auth_headers):
    r = await client.post("/api/projects", json={"name": "My Project", "mode": "development"}, headers=auth_headers)
    assert r.status_code == 201
    project = r.json()["project"]
    assert project["name"] == "My Project"

    r = await client.get("/api/projects", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()["projects"]) == 1


async def test_project_not_found_returns_404(client, auth_headers):
    r = await client.patch("/api/projects/does-not-exist", json={"name": "x"}, headers=auth_headers)
    assert r.status_code == 404


async def test_cross_tenant_project_access_is_404_not_403(client):
    """Tenant isolation: a project from tenant A must be invisible to
    tenant B, and specifically 404 (not 403) so existence isn't leaked."""
    r1 = await client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123!"})
    headers1 = {"Authorization": f"Bearer {r1.json()['token']}"}
    r_proj = await client.post("/api/projects", json={"name": "Secret Project"}, headers=headers1)
    project_id = r_proj.json()["project"]["id"]

    r2 = await client.post("/api/auth/register", json={"email": "intruder@example.com", "password": "password123!"})
    headers2 = {"Authorization": f"Bearer {r2.json()['token']}"}

    r = await client.get("/api/projects", headers=headers2)
    assert project_id not in [p["id"] for p in r.json()["projects"]]

    r = await client.patch(f"/api/projects/{project_id}", json={"name": "hijacked"}, headers=headers2)
    assert r.status_code == 404


async def test_create_session_sets_mode_appropriate_initial_phase(client, auth_headers):
    r_proj = await client.post("/api/projects", json={"name": "P"}, headers=auth_headers)
    project_id = r_proj.json()["project"]["id"]

    r = await client.post("/api/sessions", json={"projectId": project_id, "mode": "learning"}, headers=auth_headers)
    assert r.status_code == 201
    assert r.json()["session"]["currentPhase"] == "explain"

    r = await client.post("/api/sessions", json={"projectId": project_id, "mode": "development"}, headers=auth_headers)
    assert r.json()["session"]["currentPhase"] == "ideation"


async def test_session_detail_includes_nested_relations(client, auth_headers):
    r_proj = await client.post("/api/projects", json={"name": "P"}, headers=auth_headers)
    project_id = r_proj.json()["project"]["id"]
    r_sess = await client.post("/api/sessions", json={"projectId": project_id, "mode": "development"}, headers=auth_headers)
    session_id = r_sess.json()["session"]["id"]

    r = await client.get(f"/api/sessions/{session_id}", headers=auth_headers)
    body = r.json()["session"]
    for key in ("messages", "files", "specifications", "learningTopics", "project"):
        assert key in body, f"missing {key} in session detail response"


async def test_advance_phase_blocked_without_confirmed_artifacts(client, auth_headers):
    """
    All three development-mode transitions before Implementation are gated on
    an explicit user confirmation now: ideation->planning on IDEA.md
    (idea_confirmed_at), planning->specification on PLAN.md
    (plan_confirmed_at), specification->implementation on the Specification
    row's confirmed_at (unchanged). Each gate is independent of what the
    agent's critic believed about phase_complete -- see the note in
    session_service.advance_phase.
    """
    r_proj = await client.post("/api/projects", json={"name": "P"}, headers=auth_headers)
    project_id = r_proj.json()["project"]["id"]
    r_sess = await client.post("/api/sessions", json={"projectId": project_id, "mode": "development"}, headers=auth_headers)
    session_id = r_sess.json()["session"]["id"]

    # ideation -> planning: REQUIRES the idea confirmed
    r = await client.post(f"/api/sessions/{session_id}", json={}, headers=auth_headers)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "IDEA_NOT_CONFIRMED"

    r = await client.patch(f"/api/sessions/{session_id}/idea/confirm", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["session"]["ideaConfirmedAt"] is not None

    r = await client.post(f"/api/sessions/{session_id}", json={}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["session"]["currentPhase"] == "planning"

    # planning -> specification: REQUIRES the plan confirmed
    r = await client.post(f"/api/sessions/{session_id}", json={}, headers=auth_headers)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "PLAN_NOT_CONFIRMED"

    r = await client.patch(f"/api/sessions/{session_id}/plan/confirm", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["session"]["planConfirmedAt"] is not None

    r = await client.post(f"/api/sessions/{session_id}", json={}, headers=auth_headers)
    assert r.json()["session"]["currentPhase"] == "specification"

    # specification -> implementation: REQUIRES a confirmed spec
    r = await client.post(f"/api/sessions/{session_id}", json={}, headers=auth_headers)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "SPEC_NOT_CONFIRMED"

    # save + confirm a spec, then the same transition should succeed
    await client.put(
        f"/api/sessions/{session_id}/spec",
        json={"dimensions": {"ui": {"id": "custom", "label": "Minimal server-rendered UI"}}},
        headers=auth_headers,
    )
    await client.patch(f"/api/sessions/{session_id}/spec", headers=auth_headers)
    r = await client.post(f"/api/sessions/{session_id}", json={}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["session"]["currentPhase"] == "implementation"


async def test_confirming_idea_or_plan_on_another_tenant_users_session_is_rejected(client, auth_headers):
    """The confirm endpoints must go through the same tenant/user-scoped
    get_session lookup as everything else -- confirming someone else's
    ideation just because you know a session id would be a real hole."""
    r_proj = await client.post("/api/projects", json={"name": "P"}, headers=auth_headers)
    project_id = r_proj.json()["project"]["id"]
    r_sess = await client.post("/api/sessions", json={"projectId": project_id, "mode": "development"}, headers=auth_headers)
    session_id = r_sess.json()["session"]["id"]

    r_other = await client.post("/api/auth/register", json={
        "email": "otherconfirm@example.com", "password": "password123!",
    })
    other_headers = {"Authorization": f"Bearer {r_other.json()['token']}"}

    r = await client.patch(f"/api/sessions/{session_id}/idea/confirm", headers=other_headers)
    assert r.status_code == 404
    r = await client.patch(f"/api/sessions/{session_id}/plan/confirm", headers=other_headers)
    assert r.status_code == 404


async def test_message_length_is_bounded(client, auth_headers):
    r_proj = await client.post("/api/projects", json={"name": "P"}, headers=auth_headers)
    project_id = r_proj.json()["project"]["id"]
    r_sess = await client.post("/api/sessions", json={"projectId": project_id, "mode": "development"}, headers=auth_headers)
    session_id = r_sess.json()["session"]["id"]

    r = await client.post(f"/api/sessions/{session_id}/messages", json={"content": "x" * 40_000}, headers=auth_headers)
    assert r.status_code == 422

    r = await client.post(f"/api/sessions/{session_id}/messages", json={"content": ""}, headers=auth_headers)
    assert r.status_code == 422


async def test_spec_rejects_unknown_dimension_slug(client, auth_headers):
    r_proj = await client.post("/api/projects", json={"name": "P"}, headers=auth_headers)
    project_id = r_proj.json()["project"]["id"]
    r_sess = await client.post("/api/sessions", json={"projectId": project_id, "mode": "development"}, headers=auth_headers)
    session_id = r_sess.json()["session"]["id"]

    r = await client.put(
        f"/api/sessions/{session_id}/spec",
        json={"dimensions": {"not_a_real_dimension": {"id": "x", "label": "y"}}},
        headers=auth_headers,
    )
    assert r.status_code == 422


async def test_spec_accepts_valid_dimension(client, auth_headers):
    r_proj = await client.post("/api/projects", json={"name": "P"}, headers=auth_headers)
    project_id = r_proj.json()["project"]["id"]
    r_sess = await client.post("/api/sessions", json={"projectId": project_id, "mode": "development"}, headers=auth_headers)
    session_id = r_sess.json()["session"]["id"]

    r = await client.put(
        f"/api/sessions/{session_id}/spec",
        json={"dimensions": {"database": {"id": "postgres", "label": "PostgreSQL"}}},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["spec"]["dimensions"]["database"]["label"] == "PostgreSQL"


async def test_build_depth_is_set_via_session_update_and_validated(client, auth_headers):
    """build_depth is set through the generic PATCH /sessions/{id} endpoint
    (SessionUpdate), deliberately NOT inferred from a chat reply -- see the
    ChatPanel build-depth gate. Only the three known values are accepted."""
    r_proj = await client.post("/api/projects", json={"name": "P"}, headers=auth_headers)
    project_id = r_proj.json()["project"]["id"]
    r_sess = await client.post("/api/sessions", json={"projectId": project_id, "mode": "development"}, headers=auth_headers)
    session_id = r_sess.json()["session"]["id"]
    assert r_sess.json()["session"]["buildDepth"] is None

    r = await client.patch(f"/api/sessions/{session_id}", json={"buildDepth": "prototype"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["session"]["buildDepth"] == "prototype"

    r = await client.patch(f"/api/sessions/{session_id}", json={"buildDepth": "not_a_real_depth"}, headers=auth_headers)
    assert r.status_code == 422


async def test_session_not_visible_to_other_tenant_member_even_if_ever_shared(client):
    """
    Sessions are scoped by tenant_id AND user_id (not just tenant_id) --
    matches the reference app's ownership hardening. Guards against a
    future team-invite feature accidentally exposing one member's private
    sessions to another member of the same tenant.
    """
    r1 = await client.post("/api/auth/register", json={"email": "owner2@example.com", "password": "password123!"})
    headers1 = {"Authorization": f"Bearer {r1.json()['token']}"}
    r_proj = await client.post("/api/projects", json={"name": "P"}, headers=headers1)
    r_sess = await client.post(
        "/api/sessions", json={"projectId": r_proj.json()["project"]["id"], "mode": "development"}, headers=headers1
    )
    session_id = r_sess.json()["session"]["id"]

    r2 = await client.post("/api/auth/register", json={"email": "other2@example.com", "password": "password123!"})
    headers2 = {"Authorization": f"Bearer {r2.json()['token']}"}

    r = await client.get(f"/api/sessions/{session_id}", headers=headers2)
    assert r.status_code == 404