"""
Shared fixtures for all tests.

Uses pytest-asyncio with auto mode — no @pytest.mark.asyncio needed on individual tests.
External services (DB, OpenAI, Firecrawl) are always mocked so tests run without
any infrastructure.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

# ── Minimal env so config.py doesn't raise on import ─────────────────────────
os.environ.setdefault("OPENAI_API_KEY", "sk-test-openai")
os.environ.setdefault("OPENROUTER_API_KEY", "sk-test-openrouter")
os.environ.setdefault("FIRECRAWL_API_KEY", "fc-test")
os.environ.setdefault("DATABASE_URL", "postgresql://relay:relay@localhost:5432/relaypay")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "testpassword")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:5173")


@pytest.fixture
def mock_db_pool():
    """A mock asyncpg pool that returns a usable async context manager."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=1)
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()

    pool = AsyncMock()
    pool.acquire = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=conn),
                                                     __aexit__=AsyncMock(return_value=False)))
    return pool, conn


@pytest.fixture
async def app_client(mock_db_pool):
    """
    HTTPX async client wired to the FastAPI app.
    DB pool and init_db are mocked so no real Postgres is needed.
    """
    pool, _ = mock_db_pool

    with patch("db.get_pool", AsyncMock(return_value=pool)), \
         patch("db.init_db", AsyncMock()):
        from main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client


@pytest.fixture
def admin_headers():
    """Basic-auth header for admin endpoints."""
    import base64
    token = base64.b64encode(b"admin:testpassword").decode()
    return {"Authorization": f"Basic {token}"}
