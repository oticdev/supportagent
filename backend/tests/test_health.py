"""
Integration tests for the health-check endpoint.
Verifies the endpoint returns the correct shape under both healthy and degraded DB states.
"""

from unittest.mock import AsyncMock, patch


async def test_health_ok(app_client, mock_db_pool):
    pool, conn = mock_db_pool
    conn.fetchval = AsyncMock(return_value=1)

    with patch("main.get_pool", AsyncMock(return_value=pool)):
        response = await app_client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


async def test_health_degraded_when_db_unreachable(app_client):
    broken_pool = AsyncMock()
    broken_pool.acquire = AsyncMock(side_effect=Exception("Connection refused"))

    with patch("main.get_pool", AsyncMock(return_value=broken_pool)):
        response = await app_client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "unreachable"
