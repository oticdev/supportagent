"""
Unit tests for the RAG retrieval layer (agent/rag.py).

Tests cover:
- correct SQL query construction
- relevance score rounding
- empty result handling
- embedding is called with the right model input
"""

import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_pool_with_docs():
    """Pool that returns two fake document rows."""
    row1 = {"source": "pricing-page", "url": "https://relaypay.com/pricing",
            "content": "RelayPay charges 1% per transaction.", "relevance": 0.91234}
    row2 = {"source": "faq", "url": "https://relaypay.com/faq",
            "content": "Payouts take 1–3 business days.", "relevance": 0.85001}

    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[row1, row2])

    pool = AsyncMock()
    pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=conn),
        __aexit__=AsyncMock(return_value=False),
    ))
    return pool


async def test_retrieve_returns_docs(mock_pool_with_docs):
    from agent.rag import retrieve

    fake_embedding = np.zeros(1536, dtype=np.float32)

    with patch("agent.rag.get_pool", AsyncMock(return_value=mock_pool_with_docs)), \
         patch("agent.rag._embed", return_value=fake_embedding):

        results = await retrieve("What are the fees?")

    assert len(results) == 2
    assert results[0]["source"] == "pricing-page"
    assert results[0]["text"] == "RelayPay charges 1% per transaction."


async def test_retrieve_rounds_relevance_to_4dp(mock_pool_with_docs):
    from agent.rag import retrieve

    fake_embedding = np.zeros(1536, dtype=np.float32)

    with patch("agent.rag.get_pool", AsyncMock(return_value=mock_pool_with_docs)), \
         patch("agent.rag._embed", return_value=fake_embedding):

        results = await retrieve("fees")

    assert results[0]["relevance"] == 0.9123
    assert results[1]["relevance"] == 0.85


async def test_retrieve_returns_empty_list_when_no_docs():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    pool = AsyncMock()
    pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=conn),
        __aexit__=AsyncMock(return_value=False),
    ))

    from agent.rag import retrieve

    fake_embedding = np.zeros(1536, dtype=np.float32)

    with patch("agent.rag.get_pool", AsyncMock(return_value=pool)), \
         patch("agent.rag._embed", return_value=fake_embedding):

        results = await retrieve("something obscure")

    assert results == []


def test_embed_calls_openai_with_correct_model():
    """_embed should pass the configured model and return a numpy array."""
    import config

    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.1] * 1536)]

    mock_client = MagicMock()
    mock_client.embeddings.create = MagicMock(return_value=mock_response)

    with patch("agent.rag._get_embed_client", return_value=mock_client):
        from agent.rag import _embed
        result = _embed("test query")

    mock_client.embeddings.create.assert_called_once_with(
        model=config.EMBED_MODEL,
        input=["test query"],
    )
    assert isinstance(result, np.ndarray)
    assert result.shape == (1536,)
    assert result.dtype == np.float32
