"""Pytest fixtures for API integration tests."""
import os
import sys
import tempfile
from pathlib import Path

# Ensure backend is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session")
def test_db_path():
    """Create a temporary SQLite database for test session."""
    tmp = tempfile.mktemp(suffix=".db")
    yield tmp
    try:
        os.unlink(tmp)
    except OSError:
        pass


@pytest_asyncio.fixture(loop_scope="session")
async def app(test_db_path: str):
    """Create FastAPI app with test database."""
    from app.config import settings

    # Override DB URL for tests
    settings.database_url = f"sqlite+aiosqlite:///{test_db_path}"

    from app.main import app as _app
    from app.db.database import init_db

    # Initialize test db tables
    await init_db()

    yield _app


@pytest_asyncio.fixture(loop_scope="session")
async def client(app):
    """Async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
