import logging

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
import config

logger = logging.getLogger(__name__)

set_tracing_disabled(True)  # not using OpenAI tracing since we're on OpenRouter


async def run(
    query: str,
    conversation_history: list | None = None,
    conversation_id: str | None = None,
    mode: str = "chat",
) -> dict:
    context = SupportContext(conversation_id=conversation_id, mode=mode)
    prompt = CHAT_SYSTEM_PROMPT.format(support_email=config.SUPPORT_EMAIL or "support@relaypay.com")

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
    result = await Runner.run(agent, input=input_messages, context=context)

    route = "ESCALATE" if context.escalated else "ANSWER"
    logger.info("Agent finished | route=%s | query=%r", route, query)

    return {
        "route": route,
        "response": result.final_output,
    }
