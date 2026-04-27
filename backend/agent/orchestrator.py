import logging
import time

from openai import AsyncOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel, set_tracing_disabled

from agent.tools import (
    SupportContext,
    search_knowledge_base,
    check_calendar_availability,
    create_calendar_event,
    escalate_to_human,
)
from agent.prompts import CHAT_SYSTEM_PROMPT
from observability import log_event, set_request_context
import config

logger = logging.getLogger(__name__)

set_tracing_disabled(True)  # not using OpenAI tracing since we're on OpenRouter


async def run(
    query: str,
    conversation_history: list | None = None,
    conversation_id: str | None = None,
    mode: str = "chat",
    user_name: str | None = None,
    user_email: str | None = None,
) -> dict:
    context = SupportContext(conversation_id=conversation_id, mode=mode)
    # Propagate session_id into log context so every line in this run is tagged
    set_request_context(request_id="", session_id=conversation_id or "")

    # Build a customer context block so the agent knows the user's details
    # upfront and won't ask for them again during escalation.
    if user_name or user_email:
        parts = []
        if user_name:
            parts.append(f"Name: {user_name}")
        if user_email:
            parts.append(f"Email: {user_email}")
        customer_context = (
            f"\n\n## Customer details (already known — do not ask again)\n"
            + "\n".join(f"- {p}" for p in parts)
            + "\nAddress the customer by their first name and use these details "
            "during the escalation sequence."
        )
    else:
        customer_context = ""

    prompt = CHAT_SYSTEM_PROMPT.format(
        support_email=config.SUPPORT_EMAIL or "support@relaypay.com",
        customer_context=customer_context,
    )

    input_messages = []
    if conversation_history:
        input_messages.extend(conversation_history)
    input_messages.append({"role": "user", "content": query})

    agent = Agent(
        name="RelayPay Support Agent",
        instructions=prompt,
        model=OpenAIChatCompletionsModel(
            model=config.LLM_MODEL,
            openai_client=AsyncOpenAI(
                api_key=config.OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1",
            ),
        ),
        tools=[
            search_knowledge_base,
            check_calendar_availability,
            create_calendar_event,
            escalate_to_human,
        ],
    )
    t0 = time.perf_counter()
    result = await Runner.run(agent, input=input_messages, context=context)
    latency_ms = round((time.perf_counter() - t0) * 1000)

    route = "ESCALATE" if context.escalated else "ANSWER"
    log_event(
        "agent_turn",
        route=route,
        latency_ms=latency_ms,
        session_id=conversation_id,
        mode=mode,
    )

    return {
        "route": route,
        "response": result.final_output,
    }
