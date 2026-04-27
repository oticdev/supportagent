import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

import config
from db import get_pool, log_ingest_run
from ingest.firecrawl_loader import ingest_all

router = APIRouter()
_security = HTTPBasic()


def require_admin(credentials: HTTPBasicCredentials = Depends(_security)) -> None:
    if not config.ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin password not configured. Set ADMIN_PASSWORD in environment.",
        )
    ok_user = secrets.compare_digest(
        credentials.username.encode(), config.ADMIN_USERNAME.encode()
    )
    ok_pass = secrets.compare_digest(
        credentials.password.encode(), config.ADMIN_PASSWORD.encode()
    )
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

@router.get("/logs")
async def get_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    route: str | None = None,
    _: None = Depends(require_admin),
):
    pool = await get_pool()
    offset = (page - 1) * page_size

    where = "WHERE route = $3" if route else ""
    count_where = "WHERE route = $1" if route else ""

    async with pool.acquire() as conn:
        if route:
            rows = await conn.fetch(
                f"""
                SELECT id, session_id, mode, transcript, response, route, escalated, created_at
                FROM conversations {where}
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                page_size, offset, route,
            )
            total = await conn.fetchval(
                f"SELECT COUNT(*) FROM conversations {count_where}", route
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, session_id, mode, transcript, response, route, escalated, created_at
                FROM conversations
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                page_size, offset,
            )
            total = await conn.fetchval("SELECT COUNT(*) FROM conversations")

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": [dict(r) for r in rows],
    }


@router.get("/ingest-status")
async def ingest_status(_: None = Depends(require_admin)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        last_run = await conn.fetchrow(
            "SELECT status, pages_synced, created_at FROM ingest_runs ORDER BY created_at DESC LIMIT 1"
        )
    return dict(last_run) if last_run else {"status": "never_run"}


@router.post("/reingest")
async def reingest(
    background_tasks: BackgroundTasks,
    force: bool = False,
    _: None = Depends(require_admin),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO ingest_runs (status, pages_synced) VALUES ('running', 0)"
        )

    background_tasks.add_task(_run_ingest_async, force)
    mode = "force wipe + re-ingest" if force else "smart sync (hash-based)"
    return {"status": "started", "mode": mode}


async def _run_ingest_async(force: bool = False):
    try:
        result = await ingest_all(force=force)
        await log_ingest_run("success", result["pages_updated"])
    except Exception as e:
        await log_ingest_run("failed", 0, str(e))
