import numpy as np
from openai import OpenAI
from db import get_pool
import config

_embed_client: OpenAI | None = None


def _get_embed_client() -> OpenAI:
    global _embed_client
    if _embed_client is None:
        _embed_client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _embed_client


def _embed(text: str) -> np.ndarray:
    floats = _get_embed_client().embeddings.create(
        model=config.EMBED_MODEL,
        input=[text],
    ).data[0].embedding
    return np.array(floats, dtype=np.float32)


async def retrieve(query: str, top_k: int = 5) -> list[dict]:
    embedding = _embed(query)
    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT source, url, content,
                   1 - (embedding <=> $1::vector) AS relevance
            FROM documents
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            embedding, top_k,
        )

    return [
        {
            "text": r["content"],
            "source": r["source"],
            "url": r["url"],
            "relevance": round(float(r["relevance"]), 4),
        }
        for r in rows
    ]
