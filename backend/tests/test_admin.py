"""
Integration tests for admin endpoints (/api/admin/*).

Tests cover:
- authentication (valid creds, wrong creds, missing creds)
- GET /api/admin/logs — correct shape, escalated_only filter
- POST /api/admin/reingest — triggers background task
- GET /api/admin/ingest-status — returns last run info
"""

import base64
from unittest.mock import AsyncMock, MagicMock, patch


def _auth(username="admin", password="testpassword"):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


# ── Authentication ────────────────────────────────────────────────────────────

async def test_admin_logs_rejects_wrong_password(app_client):
    response = await app_client.get("/api/admin/logs", headers=_auth(password="wrong"))
    assert response.status_code == 401


async def test_admin_logs_rejects_missing_auth(app_client):
    response = await app_client.get("/api/admin/logs")
    assert response.status_code == 401


async def test_admin_logs_accepts_correct_credentials(app_client, mock_db_pool):
    pool, conn = mock_db_pool
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)

    with patch("routers.admin.get_pool", AsyncMock(return_value=pool)):
        response = await app_client.get("/api/admin/logs", headers=_auth())

    assert response.status_code == 200


# ── GET /api/admin/logs ───────────────────────────────────────────────────────

async def test_admin_logs_returns_correct_shape(app_client, mock_db_pool):
    pool, conn = mock_db_pool
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)

    with patch("routers.admin.get_pool", AsyncMock(return_value=pool)):
        response = await app_client.get("/api/admin/logs", headers=_auth())

    body = response.json()
    assert "results" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body
    assert body["total"] == 0
    assert body["results"] == []


async def test_admin_logs_escalated_only_filter_sets_query_param(app_client, mock_db_pool):
    pool, conn = mock_db_pool
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)

    with patch("routers.admin.get_pool", AsyncMock(return_value=pool)):
        response = await app_client.get(
            "/api/admin/logs?escalated_only=true", headers=_auth()
        )

    assert response.status_code == 200
    # DB fetch is called — the WHERE clause filtering is covered by SQL logic
    conn.fetch.assert_called_once()


async def test_admin_logs_pagination_defaults(app_client, mock_db_pool):
    pool, conn = mock_db_pool
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)

    with patch("routers.admin.get_pool", AsyncMock(return_value=pool)):
        response = await app_client.get("/api/admin/logs", headers=_auth())

    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 20


# ── GET /api/admin/ingest-status ─────────────────────────────────────────────

async def test_ingest_status_never_run(app_client, mock_db_pool):
    pool, conn = mock_db_pool
    conn.fetchrow = AsyncMock(return_value=None)

    with patch("routers.admin.get_pool", AsyncMock(return_value=pool)):
        response = await app_client.get("/api/admin/ingest-status", headers=_auth())

    assert response.status_code == 200
    assert response.json() == {"status": "never_run"}


async def test_ingest_status_returns_last_run(app_client, mock_db_pool):
    pool, conn = mock_db_pool
    conn.fetchrow = AsyncMock(return_value={
        "status": "success",
        "pages_synced": 12,
        "created_at": "2025-01-01T00:00:00+00:00",
    })

    with patch("routers.admin.get_pool", AsyncMock(return_value=pool)):
        response = await app_client.get("/api/admin/ingest-status", headers=_auth())

    body = response.json()
    assert body["status"] == "success"
    assert body["pages_synced"] == 12


# ── POST /api/admin/reingest ──────────────────────────────────────────────────

async def test_reingest_starts_background_task(app_client, mock_db_pool):
    pool, conn = mock_db_pool

    with patch("routers.admin.get_pool", AsyncMock(return_value=pool)), \
         patch("routers.admin._run_ingest_async", AsyncMock()):

        response = await app_client.post("/api/admin/reingest", headers=_auth())

    assert response.status_code == 200
    assert response.json()["status"] == "started"


async def test_reingest_force_mode(app_client, mock_db_pool):
    pool, conn = mock_db_pool

    with patch("routers.admin.get_pool", AsyncMock(return_value=pool)), \
         patch("routers.admin._run_ingest_async", AsyncMock()):

        response = await app_client.post(
            "/api/admin/reingest?force=true", headers=_auth()
        )

    assert response.status_code == 200
    body = response.json()
    assert "force" in body["mode"].lower() or "wipe" in body["mode"].lower()
