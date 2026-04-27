import logging
from dataclasses import dataclass

from agents import RunContextWrapper, function_tool

from agent.rag import retrieve
from agent.notifier import notify_escalation
from agent.calendar_service import check_availability, create_event
from db import create_escalation
from observability import log_event, get_session_id

logger = logging.getLogger(__name__)


@dataclass
class SupportContext:
    conversation_id: str | None = None
    mode: str = "chat"
    escalated: bool = False


@function_tool
async def search_knowledge_base(ctx: RunContextWrapper[SupportContext], query: str) -> str:
    """Search the RelayPay knowledge base for product information, pricing, policies,
    compliance rules, and FAQs. Always call this before answering any product question.

    Args:
        query: A specific search query to find relevant documentation.
    """
    docs = await retrieve(query)

    if not docs:
        log_event("kb_search", query=query, hits=0, session_id=get_session_id())
        return "No relevant documentation found for this query."

    top_score = docs[0]["relevance"] if docs else 0
    log_event("kb_search", query=query, hits=len(docs), top_score=round(top_score, 3),
              session_id=get_session_id())

    return "\n\n".join(
        f"[Source: {d['source']} | Relevance: {d['relevance']}]\n{d['text']}"
        for d in docs
    )


@function_tool
async def check_calendar_availability(
    ctx: RunContextWrapper[SupportContext],
    preferred_date: str,
) -> str:
    """Check available 30-minute support call slots within 7 days of a preferred date.
    Returns a list of free time slots (weekdays, 09:00–17:00 UTC).

    Args:
        preferred_date: ISO 8601 date or datetime to start searching from, e.g. 2025-06-10.
    """
    logger.info("Tool: check_calendar_availability | preferred_date=%r", preferred_date)
    result = await check_availability(preferred_date)
    return result["result"]


@function_tool
async def create_calendar_event(
    ctx: RunContextWrapper[SupportContext],
    attendee_email: str,
    start_time: str,
    summary: str | None = None,
) -> str:
    """Book a 30-minute support call on the calendar and send the invite to the customer.

    Args:
        attendee_email: Customer's email address.
        start_time: ISO 8601 datetime for the meeting start, e.g. 2025-06-10T14:00:00.
        summary: Optional meeting title. Defaults to 'RelayPay Support Call'.
    """
    logger.info(
        "Tool: create_calendar_event | attendee=%s | start=%s", attendee_email, start_time
    )
    result = await create_event(
        attendee_email=attendee_email,
        start_time=start_time,
        summary=summary or "RelayPay Support Call",
    )
    return result["result"]


@function_tool
async def escalate_to_human(
    ctx: RunContextWrapper[SupportContext],
    user_name: str,
    user_email: str,
    category: str,
    reason: str,
    appointment_time: str | None = None,
    calendar_event_id: str | None = None,
) -> str:
    """Record a support escalation and notify the support team. Call this AFTER
    you have already checked availability and created the calendar event using
    the Google Calendar tools. Do not call this until the meeting is booked.

    Args:
        user_name: Full name of the customer.
        user_email: Email address of the customer.
        category: One of: compliance, account, dispute, other.
        reason: A concise summary of why escalation is needed.
        appointment_time: ISO 8601 datetime of the booked appointment.
        calendar_event_id: The Google Calendar event ID after booking.
    """
    escalation_id = await create_escalation(
        user_name=user_name,
        user_email=user_email,
        category=category,
        reason=reason,
        appointment_time=appointment_time,
        calendar_event_id=calendar_event_id,
        conversation_id=ctx.context.conversation_id,
    )

    notify_escalation(
        user_name=user_name,
        user_email=user_email,
        category=category,
        reason=reason,
        appointment_time=appointment_time,
        escalation_id=escalation_id,
    )

    log_event(
        "escalation",
        escalation_id=escalation_id,
        customer_email=user_email,
        category=category,
        has_appointment=appointment_time is not None,
        session_id=get_session_id(),
    )
    ctx.context.escalated = True
    return f"Escalation recorded (ID: {escalation_id}). Support team has been notified."
