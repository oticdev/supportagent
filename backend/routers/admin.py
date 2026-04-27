import json
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

import config
from db import get_pool, log_ingest_run
from ingest.firecrawl_loader import ingest_all
from evals.golden_dataset import GOLDEN_DATASET

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
    escalated_only: bool = False,
    _: None = Depends(require_admin),
):
    """
    Returns one row per session (grouped), showing:
    - user email
    - number of turns
    - the opening message (first thing the user said)
    - whether the session was escalated
    - channel (chat / voice)
    - when it started and when it last had activity
    """
    pool = await get_pool()
    offset = (page - 1) * page_size

    where = "WHERE bool_or(c.escalated) = TRUE" if escalated_only else ""
    count_where = "WHERE escalated_session = TRUE" if escalated_only else ""

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                c.session_id,
                MAX(c.mode)                                         AS mode,
                MAX(c.user_email)                                   AS user_email,
                COUNT(*)                                            AS turns,
                MIN(c.transcript)                                   AS first_message,
                bool_or(c.escalated)                                AS escalated,
                MIN(c.created_at)                                   AS started_at,
                MAX(c.created_at)                                   AS last_activity,
                -- escalation details (if any)
                MAX(e.user_name)                                    AS escalation_name,
                MAX(e.user_email)                                   AS escalation_email,
                MAX(e.category)                                     AS escalation_category,
                MAX(e.reason)                                       AS escalation_reason,
                MAX(e.appointment_time)                             AS appointment_time
            FROM conversations c
            LEFT JOIN escalations e ON e.conversation_id::text = c.session_id
            {where}
            GROUP BY c.session_id
            ORDER BY MAX(c.created_at) DESC
            LIMIT $1 OFFSET $2
            """,
            page_size, offset,
        )

        total = await conn.fetchval(
            f"""
            SELECT COUNT(*) FROM (
                SELECT session_id, bool_or(escalated) AS escalated_session
                FROM conversations
                GROUP BY session_id
            ) s {count_where}
            """
        )

    def serialize(r):
        d = dict(r)
        # prefer escalation email (collected by agent) over session email
        d["user_email"] = d.pop("escalation_email") or d.get("user_email")
        d["user_name"] = d.pop("escalation_name")
        return d

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": [serialize(r) for r in rows],
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


# ── Evaluation endpoints ──────────────────────────────────────────────────────

@router.get("/eval/cases")
async def list_eval_cases(_: None = Depends(require_admin)):
    """Return the golden dataset so the frontend can display it."""
    return {
        "total": len(GOLDEN_DATASET),
        "cases": [
            {
                "id": c.id,
                "query": c.query,
                "expected_route": c.expected_route,
                "tags": c.tags,
                "description": c.description,
            }
            for c in GOLDEN_DATASET
        ],
    }


@router.post("/eval/run")
async def trigger_eval(
    background_tasks: BackgroundTasks,
    tags: list[str] | None = Query(default=None),
    _: None = Depends(require_admin),
):
    """Kick off an eval run in the background. Returns immediately."""
    background_tasks.add_task(_run_eval_async, tags)
    label = f"tags={tags}" if tags else "all cases"
    return {"status": "started", "scope": label, "total_cases": len(GOLDEN_DATASET)}


@router.get("/eval/runs")
async def list_eval_runs(
    limit: int = Query(10, ge=1, le=50),
    _: None = Depends(require_admin),
):
    """Return the most recent eval runs with summary scores (no per-case detail)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, total, passed, failed, pass_rate, route_accuracy,
                   avg_accuracy, avg_helpfulness, avg_tone, avg_safety, avg_overall,
                   tags, created_at
            FROM eval_runs
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
    return {"runs": [dict(r) for r in rows]}


@router.get("/eval/runs/latest")
async def latest_eval_run(_: None = Depends(require_admin)):
    """Return the most recent eval run including per-case results."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM eval_runs ORDER BY created_at DESC LIMIT 1"
        )
    if not row:
        return {"status": "never_run"}
    d = dict(row)
    d["results"] = json.loads(d["results"]) if isinstance(d["results"], str) else d["results"]
    return d


async def _run_eval_async(tags: list[str] | None = None):
    from evals.runner import run_eval
    try:
        await run_eval(tags=tags)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Eval run failed: %s", e)
