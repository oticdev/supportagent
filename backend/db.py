import asyncpg
from datetime import datetime, timezone
from pgvector.asyncpg import register_vector
import config

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            config.DATABASE_URL,
            init=register_vector,
        )
    return _pool


async def init_db():
    # Phase 1: plain connection to install the extension before vector type exists
    plain = await asyncpg.connect(config.DATABASE_URL)
    try:
        await plain.execute("CREATE EXTENSION IF NOT EXISTS vector")
    finally:
        await plain.close()

    # Phase 2: now the vector type exists — safe to build the pool
    pool = await get_pool()
    async with pool.acquire() as conn:

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                source       TEXT NOT NULL,
                url          TEXT,
                content      TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                embedding    vector(1536),
                created_at   TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # HNSW index — works at any scale, no minimum row-count requirement.
        # (IVFFlat needs ~lists×39 rows; HNSW has no such constraint.)
        # Drop old IVFFlat index if it was created previously.
        await conn.execute("""
            DROP INDEX IF EXISTS documents_embedding_idx
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS documents_embedding_hnsw_idx
            ON documents USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id  TEXT,
                mode        TEXT,
                transcript  TEXT,
                response    TEXT,
                route       TEXT,
                escalated   BOOLEAN DEFAULT FALSE,
                user_email  TEXT,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Migration: add user_email to existing deployments
        await conn.execute("""
            ALTER TABLE conversations ADD COLUMN IF NOT EXISTS user_email TEXT
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS ingest_runs (
                id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                status        TEXT,
                pages_synced  INT,
                error         TEXT,
                created_at    TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                session_id  TEXT PRIMARY KEY,
                history     JSONB NOT NULL DEFAULT '[]',
                updated_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS escalations (
                id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                conversation_id  UUID REFERENCES conversations(id) ON DELETE SET NULL,
                user_name        TEXT NOT NULL,
                user_email       TEXT NOT NULL,
                category         TEXT NOT NULL,
                reason           TEXT NOT NULL,
                call_booked      BOOLEAN DEFAULT FALSE,
                appointment_time TIMESTAMPTZ,
                calendar_event_id TEXT,
                status           TEXT DEFAULT 'open',
                created_at       TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS eval_runs (
                id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                total            INT NOT NULL,
                passed           INT NOT NULL,
                failed           INT NOT NULL,
                pass_rate        FLOAT NOT NULL,
                route_accuracy   FLOAT NOT NULL,
                avg_accuracy     FLOAT NOT NULL,
                avg_helpfulness  FLOAT NOT NULL,
                avg_tone         FLOAT NOT NULL,
                avg_safety       FLOAT NOT NULL,
                avg_overall      FLOAT NOT NULL,
                tags             TEXT[] DEFAULT '{}',
                results          JSONB NOT NULL DEFAULT '[]',
                created_at       TIMESTAMPTZ DEFAULT NOW()
            )
        """)


import json

SESSION_MAX_TURNS = 20  # keep last 20 turns to avoid token bloat


async def get_session_history(session_id: str) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT history FROM chat_sessions WHERE session_id = $1", session_id
        )
    return json.loads(row["history"]) if row else []


async def save_session_history(session_id: str, history: list[dict]) -> None:
    trimmed = history[-SESSION_MAX_TURNS:]
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO chat_sessions (session_id, history, updated_at)
            VALUES ($1, $2::jsonb, NOW())
            ON CONFLICT (session_id) DO UPDATE
                SET history = EXCLUDED.history, updated_at = NOW()
            """,
            session_id, json.dumps(trimmed),
        )


async def delete_session(session_id: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM chat_sessions WHERE session_id = $1", session_id
        )


async def log_conversation(
    session_id: str,
    mode: str,
    transcript: str,
    response: str,
    route: str,
    user_email: str | None = None,
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO conversations (session_id, mode, transcript, response, route, escalated, user_email)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            session_id, mode, transcript, response, route, route == "ESCALATE", user_email,
        )


async def log_ingest_run(status: str, pages_synced: int = 0, error: str | None = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO ingest_runs (status, pages_synced, error) VALUES ($1, $2, $3)",
            status, pages_synced, error,
        )


async def create_escalation(
    user_name: str,
    user_email: str,
    category: str,
    reason: str,
    appointment_time: str | None = None,
    calendar_event_id: str | None = None,
    conversation_id: str | None = None,
) -> str:
    # asyncpg requires a datetime object for TIMESTAMPTZ columns, not a string
    appt_dt: datetime | None = None
    if appointment_time:
        try:
            appt_dt = datetime.fromisoformat(appointment_time)
            if appt_dt.tzinfo is None:
                appt_dt = appt_dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            appt_dt = None

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO escalations
                (conversation_id, user_name, user_email, category, reason,
                 call_booked, appointment_time, calendar_event_id, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'open')
            RETURNING id
            """,
            conversation_id, user_name, user_email, category, reason,
            appt_dt is not None,
            appt_dt,
            calendar_event_id,
        )
    return str(row["id"])
