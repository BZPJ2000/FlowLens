"""API integration tests — Phase 3 endpoints"""
import pytest
import pytest_asyncio


# ═══════════════════════════════════════════
# Health & Projects
# ═══════════════════════════════════════════

@pytest.mark.asyncio(loop_scope="session")
async def test_health_endpoint(client):
    res = await client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio(loop_scope="session")
async def test_list_projects_empty(client):
    res = await client.get("/api/v1/projects")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


# ═══════════════════════════════════════════
# Import — creates project + analysis
# ═══════════════════════════════════════════

@pytest.mark.asyncio(loop_scope="session")
async def test_import_invalid_url(client):
    """Import with empty URL should return 400."""
    res = await client.post("/api/v1/projects/import", json={
        "source_type": "github", "source_url": "",
    })
    assert res.status_code == 400


@pytest.mark.asyncio(loop_scope="session")
async def test_import_creates_project(client):
    """Import with a URL creates a project analysis (may fail at clone stage, but project + analysis should be created)."""
    res = await client.post("/api/v1/projects/import", json={
        "source_type": "github",
        "source_url": "https://github.com/nonexistent/test-repo.git",
    })
    # Should return 200 or 202 with project_id + analysis_id
    assert res.status_code == 200
    data = res.json()
    assert "project_id" in data
    assert "analysis_id" in data
    assert data["status"] == "pending"


@pytest.mark.asyncio(loop_scope="session")
async def test_list_projects_after_import(client):
    """After import, the project should appear in the list."""
    res = await client.get("/api/v1/projects")
    assert res.status_code == 200
    projects = res.json()
    assert len(projects) >= 1
    assert projects[0]["name"] == "test-repo"


# ═══════════════════════════════════════════
# Analysis status
# ═══════════════════════════════════════════

@pytest.mark.asyncio(loop_scope="session")
async def test_get_analysis_not_found(client):
    """Non-existent analysis returns 404."""
    res = await client.get("/api/v1/analyses/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404


# ═══════════════════════════════════════════
# Chat
# ═══════════════════════════════════════════

@pytest_asyncio.fixture(loop_scope="session")
async def existing_analysis_id(client):
    """Get any existing analysis ID from the project list."""
    res = await client.get("/api/v1/projects")
    projects = res.json()
    if projects and projects[0].get("latest_analysis"):
        return projects[0]["latest_analysis"]["analysis_id"]
    return None


@pytest.mark.asyncio(loop_scope="session")
async def test_chat_creates_session(client, existing_analysis_id):
    """Posting a chat message should create a session and return a reply."""
    if not existing_analysis_id:
        pytest.skip("No existing analysis to test chat against")

    res = await client.post(f"/api/v1/analyses/{existing_analysis_id}/chat", json={
        "message": "这个项目的主要架构是什么？",
    })
    assert res.status_code == 200
    data = res.json()
    assert "session_id" in data
    assert "reply" in data
    assert "referenced" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_list_chat_sessions(client, existing_analysis_id):
    """Chat sessions endpoint should return list."""
    if not existing_analysis_id:
        pytest.skip("No existing analysis")

    res = await client.get(f"/api/v1/analyses/{existing_analysis_id}/chat/sessions")
    assert res.status_code == 200
    sessions = res.json()
    assert isinstance(sessions, list)
    assert len(sessions) >= 1
    assert "session_id" in sessions[0]
    assert "title" in sessions[0]
    assert "created_at" in sessions[0]


@pytest.mark.asyncio(loop_scope="session")
async def test_get_chat_history(client, existing_analysis_id):
    """Get chat history for a specific session."""
    if not existing_analysis_id:
        pytest.skip("No existing analysis")

    # First get sessions list to find a session ID
    res = await client.get(f"/api/v1/analyses/{existing_analysis_id}/chat/sessions")
    sessions = res.json()
    assert len(sessions) > 0
    session_id = sessions[0]["session_id"]

    # Get history
    res = await client.get(f"/api/v1/analyses/{existing_analysis_id}/chat/{session_id}")
    assert res.status_code == 200
    messages = res.json()
    assert isinstance(messages, list)
    assert len(messages) >= 1  # at least the user message
    assert messages[0]["role"] in ("user", "assistant")


@pytest.mark.asyncio(loop_scope="session")
async def test_list_sessions_nonexistent_analysis(client):
    """List sessions for non-existent analysis returns 404."""
    res = await client.get("/api/v1/analyses/00000000-0000-0000-0000-000000000000/chat/sessions")
    assert res.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_get_history_nonexistent_session(client, existing_analysis_id):
    """Get history for non-existent session returns empty or 404."""
    if not existing_analysis_id:
        pytest.skip("No existing analysis")
    # Use a random UUID that doesn't correspond to a session
    res = await client.get(
        f"/api/v1/analyses/{existing_analysis_id}/chat/00000000-0000-0000-0000-000000000000"
    )
    # Should return empty list (valid analysis, no such session → empty messages)
    assert res.status_code in (200, 404)
