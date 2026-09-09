"""GET /sessions/{id}/export/zip -- the Review phase's zip download."""
import io
import zipfile

import pytest


@pytest.fixture(autouse=True)
def workspace_env(tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "workspace_root", str(tmp_path), raising=False)


async def _new_session(client, auth_headers, title="My Cool Project"):
    r_proj = await client.post("/api/projects", json={"name": "P"}, headers=auth_headers)
    r_sess = await client.post(
        "/api/sessions",
        json={"projectId": r_proj.json()["project"]["id"], "mode": "development", "title": title},
        headers=auth_headers,
    )
    return r_sess.json()["session"]["id"]


async def test_export_contains_exactly_the_workspace_files(client, auth_headers):
    session_id = await _new_session(client, auth_headers)

    from app.agents import workspace
    await workspace.write_file(session_id, "app.py", "print('hi')")
    await workspace.write_file(session_id, "src/nested/util.py", "x = 1")
    await workspace.write_file(session_id, "__pycache__/junk.pyc", "should not appear")

    r = await client.get(f"/api/sessions/{session_id}/export/zip", headers=auth_headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert "attachment" in r.headers["content-disposition"]

    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(zf.namelist())
    assert names == {"app.py", "src/nested/util.py"}
    assert zf.read("app.py").decode() == "print('hi')"


async def test_export_filename_is_derived_from_the_session_title(client, auth_headers):
    session_id = await _new_session(client, auth_headers, title="My Cool Project!!")
    r = await client.get(f"/api/sessions/{session_id}/export/zip", headers=auth_headers)
    disposition = r.headers["content-disposition"]
    assert "My-Cool-Project" in disposition
    assert session_id[:8] in disposition


async def test_export_hydrates_from_db_first_so_a_stale_disk_still_exports_everything(client, auth_headers, tmp_path):
    """The workspace directory is a working copy that can be behind the DB
    (a redeploy, a different machine) -- export must reflect the durable
    record, not whatever happens to be on disk already."""
    session_id = await _new_session(client, auth_headers)

    from app.agents import workspace
    from sqlalchemy import select
    import app.db.session as dbsession
    from app.models.message import SessionFile

    # Simulate "the DB has a file the disk has never seen": insert a
    # SessionFile row directly, without ever calling workspace.write_file.
    async with dbsession.AsyncSessionLocal() as db:
        db.add(SessionFile(session_id=session_id, file_path="only_in_db.txt", content="from the db", language="text"))
        await db.commit()

    assert not workspace.resolve_path(session_id, "only_in_db.txt").exists()

    r = await client.get(f"/api/sessions/{session_id}/export/zip", headers=auth_headers)
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    assert zf.read("only_in_db.txt").decode() == "from the db"


async def test_export_of_an_empty_workspace_is_a_valid_empty_zip(client, auth_headers):
    session_id = await _new_session(client, auth_headers)
    r = await client.get(f"/api/sessions/{session_id}/export/zip", headers=auth_headers)
    assert r.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    assert zf.namelist() == []


async def test_export_of_another_users_session_is_rejected(client, auth_headers):
    session_id = await _new_session(client, auth_headers)

    r_other = await client.post("/api/auth/register", json={"email": "otherzip@example.com", "password": "password123!"})
    other_headers = {"Authorization": f"Bearer {r_other.json()['token']}"}

    r = await client.get(f"/api/sessions/{session_id}/export/zip", headers=other_headers)
    assert r.status_code == 404
