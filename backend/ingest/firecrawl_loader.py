import hashlib
import logging

from firecrawl import Firecrawl
from openai import OpenAI

from db import get_pool
import config

logger = logging.getLogger(__name__)

NOTION_PAGES = [
    {
        "url": "https://jasper-lifeboat-de7.notion.site/RelayPay-Product-Features-Overview-33efe287d593807d8018d74b131fda6c",
        "name": "Product Features",
    },
    {
        "url": "https://jasper-lifeboat-de7.notion.site/RelayPay-Policies-Compliance-33efe287d59380f5be86f595f2038ee6",
        "name": "Policies & Compliance",
    },
    {
        "url": "https://jasper-lifeboat-de7.notion.site/RelayPay-Frequently-Asked-Questions-FAQ-33efe287d59380aba8b0ce96194352fe",
        "name": "FAQ",
    },
    {
        "url": "https://jasper-lifeboat-de7.notion.site/RelayPay-Release-Notes-Known-Limitations-33efe287d59380e8b441c703a0aa5cf0",
        "name": "Release Notes",
    },
]


def _chunk_text(text: str, chunk_size: int = 400, overlap: int = 40) -> list[str]:
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunks.append(" ".join(words[i : i + chunk_size]))
        i += chunk_size - overlap
    return [c for c in chunks if c.strip()]


def _embed_chunks(chunks: list[str]) -> list[list[float]]:
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    resp = client.embeddings.create(
        model=config.EMBED_MODEL,
        input=chunks,
    )
    return [e.embedding for e in resp.data]


async def ingest_all(force: bool = False) -> dict:
    firecrawl = Firecrawl(api_key=config.FIRECRAWL_API_KEY)
    pool = await get_pool()
    pages_updated = 0

    if force:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM documents")
        logger.info("Force mode: wiped all documents")

    for page in NOTION_PAGES:
        logger.info("Scraping page: %s", page["name"])

        try:
            result = firecrawl.scrape(page["url"], formats=["markdown"])
            markdown = result.markdown or ""
        except Exception:
            logger.exception("Firecrawl failed for page: %s", page["name"])
            continue

        if not markdown.strip():
            logger.warning("Empty content returned for page: %s", page["name"])
            continue

        content_hash = hashlib.md5(markdown.encode()).hexdigest()

        if not force:
            async with pool.acquire() as conn:
                existing_hash = await conn.fetchval(
                    "SELECT content_hash FROM documents WHERE source = $1 LIMIT 1",
                    page["name"],
                )

            if existing_hash == content_hash:
                logger.info("No changes for '%s' — skipping", page["name"])
                continue

            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM documents WHERE source = $1", page["name"])
            logger.info("Content changed for '%s' — re-embedding", page["name"])
        else:
            logger.info("Force re-ingesting '%s'", page["name"])

        chunks = _chunk_text(markdown)
        logger.info("Embedding %d chunks for page: %s", len(chunks), page["name"])

        try:
            embeddings = _embed_chunks(chunks)
        except Exception:
            logger.exception("Embedding failed for page: %s", page["name"])
            continue

        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO documents (source, url, content, content_hash, embedding)
                VALUES ($1, $2, $3, $4, $5)
                """,
                [
                    (page["name"], page["url"], chunk, content_hash, emb)
                    for chunk, emb in zip(chunks, embeddings)
                ],
            )

        logger.info("Ingested %d chunks for page: %s", len(chunks), page["name"])
        pages_updated += 1

    logger.info("Ingest complete — %d/%d pages updated", pages_updated, len(NOTION_PAGES))
    return {"pages_updated": pages_updated, "total_pages": len(NOTION_PAGES)}
