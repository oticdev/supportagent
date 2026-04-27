import logging

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel
from main import limiter

from agent.calendar_service import check_availability, create_event
from agent.rag import retrieve
from agent.notifier import notify_escalation
from agent.prompts import VOICE_INSTRUCTIONS
from db import create_escalation, log_conversation
import config

logger = logging.getLogger(__name__)

router = APIRouter()

REALTIME_MODEL = "gpt-4o-realtime-preview-2024-12-17"


# ── Session creation ──────────────────────────────────────────────────────────

class VoiceSessionRequest(BaseModel):
    user_name: str = ""
    user_email: str = ""


@router.post("/voice/session")
@limiter.limit("10/hour")
async def create_voice_session(request: Request, req: VoiceSessionRequest = VoiceSessionRequest()):
    support_email = config.SUPPORT_EMAIL or "support@relaypay.com"
    instructions = VOICE_INSTRUCTIONS.format(support_email=support_email)

    # Prepend known user details so the agent skips asking for them
    if req.user_name or req.user_email:
        user_ctx = "The customer's details are already known:\n"
        if req.user_name:
            user_ctx += f"- Name: {req.user_name}\n"
        if req.user_email:
            user_ctx += f"- Email: {req.user_email}\n"
        user_ctx += (
            "Greet them by first name. "
            "Do NOT ask for their name or email — you already have them. "
            "Use these details directly when calling escalate_to_human.\n\n"
        )
        instructions = user_ctx + instructions

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.openai.com/v1/realtime/sessions",
            headers={
                "Authorization": f"Bearer {config.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": REALTIME_MODEL,
                "voice": config.TTS_VOICE,
                "instructions": instructions,
                "input_audio_transcription": {
                    "model": "whisper-1",
                    "language": "en",
                },
            },
            timeout=15,
        )
        resp.raise_for_status()

    data = resp.json()
    return {
        "client_secret": data["client_secret"]["value"],
        "instructions": instructions,
    }


# ── Tool dispatch ─────────────────────────────────────────────────────────────

class ToolRequest(BaseModel):
    tool: str
    args: dict = {}


@router.post("/voice/tool")
async def voice_tool(req: ToolRequest):
    match req.tool:
        case "search_knowledge_base":
            return await _tool_search(req.args)
        case "check_calendar_availability":
            result = await check_availability(req.args.get("preferred_date", ""))
            return result
        case "create_calendar_event":
            result = await create_event(
                attendee_email=req.args.get("attendee_email", ""),
                start_time=req.args.get("start_time", ""),
                summary=req.args.get("summary", "RelayPay Support Call"),
            )
            return result
        case "escalate_to_human":
            return await _tool_escalate(req.args)
        case _:
            return {"result": f"Unknown tool: {req.tool}"}


async def _tool_search(args: dict) -> dict:
    docs = await retrieve(args.get("query", ""))
    if not docs:
        return {"result": "No relevant documentation found for this query."}
    result = "\n\n".join(
        f"[Source: {d['source']} | Relevance: {d['relevance']:.2f}]\n{d['text']}"
        for d in docs
    )
    return {"result": result}


async def _tool_escalate(args: dict) -> dict:
    escalation_id = await create_escalation(
        user_name=args.get("user_name", "Unknown"),
        user_email=args.get("user_email", ""),
        category=args.get("category", "other"),
        reason=args.get("reason", ""),
        appointment_time=args.get("appointment_time"),
        calendar_event_id=args.get("calendar_event_id"),
        conversation_id=args.get("conversation_id"),
    )
    notify_escalation(
        user_name=args.get("user_name", "Unknown"),
        user_email=args.get("user_email", ""),
        category=args.get("category", "other"),
        reason=args.get("reason", ""),
        appointment_time=args.get("appointment_time"),
        escalation_id=escalation_id,
    )
    return {"result": f"Escalation recorded (ID: {escalation_id}). Support team has been notified."}
