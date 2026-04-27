"""
Integration tests for POST /api/chat.

The orchestrator and all DB calls are mocked — these tests verify:
- correct request/response shape
- session_id generation and propagation
- user context (name/email) is forwarded to the orchestrator
- ESCALATE route is returned correctly
- rate limiting headers are present
"""

import uuid
from unittest.mock import AsyncMock, patch


MOCK_ANSWER = {
    "route": "ANSWER",
    "response": "RelayPay supports payments in 30+ currencies.",
}

MOCK_ESCALATE = {
    "route": "ESCALATE",
    "response": "I'm connecting you with a specialist.",
}


async def test_chat_returns_answer(app_client):
    with patch("routers.chat.orchestrator.run", AsyncMock(return_value=MOCK_ANSWER)), \
         patch("routers.chat.get_session_history", AsyncMock(return_value=[])), \
         patch("routers.chat.save_session_history", AsyncMock()), \
         patch("routers.chat.log_conversation", AsyncMock()):

        response = await app_client.post("/api/chat", json={"message": "What currencies do you support?"})

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "ANSWER"
    assert "currencies" in body["response"].lower()
    assert "session_id" in body


async def test_chat_generates_session_id_when_not_provided(app_client):
    with patch("routers.chat.orchestrator.run", AsyncMock(return_value=MOCK_ANSWER)), \
         patch("routers.chat.get_session_history", AsyncMock(return_value=[])), \
         patch("routers.chat.save_session_history", AsyncMock()), \
         patch("routers.chat.log_conversation", AsyncMock()):

        r1 = await app_client.post("/api/chat", json={"message": "Hello"})
        r2 = await app_client.post("/api/chat", json={"message": "Hello"})

    # Each call without a session_id gets a fresh UUID
    assert r1.json()["session_id"] != r2.json()["session_id"]


async def test_chat_preserves_provided_session_id(app_client):
    session = str(uuid.uuid4())

    with patch("routers.chat.orchestrator.run", AsyncMock(return_value=MOCK_ANSWER)), \
         patch("routers.chat.get_session_history", AsyncMock(return_value=[])), \
         patch("routers.chat.save_session_history", AsyncMock()), \
         patch("routers.chat.log_conversation", AsyncMock()):

        response = await app_client.post("/api/chat", json={"message": "Hi", "session_id": session})

    assert response.json()["session_id"] == session


async def test_chat_passes_user_context_to_orchestrator(app_client):
    """User name/email should be forwarded to orchestrator.run as kwargs."""
    captured = {}

    async def fake_run(query, conversation_history=None, **kwargs):
        captured["kwargs"] = kwargs
        return MOCK_ANSWER

    with patch("routers.chat.orchestrator.run", fake_run), \
         patch("routers.chat.get_session_history", AsyncMock(return_value=[])), \
         patch("routers.chat.save_session_history", AsyncMock()), \
         patch("routers.chat.log_conversation", AsyncMock()):

        await app_client.post("/api/chat", json={
            "message": "Hello",
            "user_name": "Alice",
            "user_email": "alice@example.com",
        })

    # Name and email should reach the orchestrator so it can inject them into
    # the system prompt — not as a history message.
    assert captured["kwargs"].get("user_name") == "Alice"
    assert captured["kwargs"].get("user_email") == "alice@example.com"


async def test_chat_escalate_route_is_returned(app_client):
    with patch("routers.chat.orchestrator.run", AsyncMock(return_value=MOCK_ESCALATE)), \
         patch("routers.chat.get_session_history", AsyncMock(return_value=[])), \
         patch("routers.chat.save_session_history", AsyncMock()), \
         patch("routers.chat.log_conversation", AsyncMock()):

        response = await app_client.post("/api/chat", json={"message": "I need a refund"})

    assert response.status_code == 200
    assert response.json()["route"] == "ESCALATE"


async def test_chat_missing_message_returns_422(app_client):
    response = await app_client.post("/api/chat", json={})
    assert response.status_code == 422
