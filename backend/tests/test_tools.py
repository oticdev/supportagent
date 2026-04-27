"""
Unit tests for agent tools (agent/tools.py).

These tests mock all external dependencies (DB, RAG, calendar, Slack)
and verify the tools return correct formatted strings and set the right
flags on the SupportContext.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from agent.tools import SupportContext


def _make_ctx(conversation_id="test-session-123", mode="chat"):
    """Create a lightweight RunContextWrapper-like object."""
    ctx = MagicMock()
    ctx.context = SupportContext(conversation_id=conversation_id, mode=mode)
    return ctx


# ── search_knowledge_base ─────────────────────────────────────────────────────

async def test_search_knowledge_base_returns_formatted_results():
    from agent.tools import search_knowledge_base

    fake_docs = [
        {"source": "pricing", "url": "https://relaypay.com/pricing",
         "text": "1% fee per transaction.", "relevance": 0.95},
        {"source": "faq", "url": "https://relaypay.com/faq",
         "text": "Payouts in 1–3 days.", "relevance": 0.88},
    ]

    with patch("agent.tools.retrieve", AsyncMock(return_value=fake_docs)):
        result = await search_knowledge_base.on_invoke_tool(
            _make_ctx(), '{"query": "transaction fee"}'
        )

    assert "pricing" in result
    assert "1% fee per transaction" in result
    assert "0.95" in result


async def test_search_knowledge_base_returns_not_found_message():
    from agent.tools import search_knowledge_base

    with patch("agent.tools.retrieve", AsyncMock(return_value=[])):
        result = await search_knowledge_base.on_invoke_tool(
            _make_ctx(), '{"query": "something unknown"}'
        )

    assert "No relevant documentation found" in result


# ── escalate_to_human ─────────────────────────────────────────────────────────

async def test_escalate_sets_escalated_flag_on_context():
    from agent.tools import escalate_to_human

    ctx = _make_ctx()

    with patch("agent.tools.create_escalation", AsyncMock(return_value="esc-uuid-001")), \
         patch("agent.tools.notify_escalation", MagicMock()):

        await escalate_to_human.on_invoke_tool(ctx, """{
            "user_name": "Alice",
            "user_email": "alice@example.com",
            "category": "dispute",
            "reason": "Incorrect charge",
            "appointment_time": null,
            "calendar_event_id": null
        }""")

    assert ctx.context.escalated is True


async def test_escalate_returns_escalation_id_in_message():
    from agent.tools import escalate_to_human

    ctx = _make_ctx()

    with patch("agent.tools.create_escalation", AsyncMock(return_value="esc-uuid-999")), \
         patch("agent.tools.notify_escalation", MagicMock()):

        result = await escalate_to_human.on_invoke_tool(ctx, """{
            "user_name": "Bob",
            "user_email": "bob@example.com",
            "category": "account",
            "reason": "Account locked",
            "appointment_time": null,
            "calendar_event_id": null
        }""")

    assert "esc-uuid-999" in result
    assert "Support team has been notified" in result


# ── check_calendar_availability ───────────────────────────────────────────────

async def test_check_calendar_availability_passes_date_through():
    from agent.tools import check_calendar_availability

    mock_result = {"result": "Available: Mon 10:00, Tue 14:00"}

    with patch("agent.tools.check_availability", AsyncMock(return_value=mock_result)):
        result = await check_calendar_availability.on_invoke_tool(
            _make_ctx(), '{"preferred_date": "2025-06-10"}'
        )

    assert "Available" in result


# ── create_calendar_event ─────────────────────────────────────────────────────

async def test_create_calendar_event_returns_confirmation():
    from agent.tools import create_calendar_event

    mock_result = {"result": "Event created: evt_abc123"}

    with patch("agent.tools.create_event", AsyncMock(return_value=mock_result)):
        result = await create_calendar_event.on_invoke_tool(
            _make_ctx(), """{
                "attendee_email": "user@example.com",
                "start_time": "2025-06-10T14:00:00",
                "summary": "RelayPay Support Call"
            }"""
        )

    assert "evt_abc123" in result
