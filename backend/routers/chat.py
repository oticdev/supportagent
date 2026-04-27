import uuid
from fastapi import APIRouter, Request
from pydantic import BaseModel
from main import limiter

from agent import orchestrator
from db import get_session_history, save_session_history, delete_session, log_conversation

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    user_name: str | None = None
    user_email: str | None = None


@router.post("/chat")
@limiter.limit("60/hour")
async def chat(request: Request, req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    history = await get_session_history(session_id)

    # On the first turn inject known user details so the agent greets by name
    # and doesn't ask for info it already has.
    if not history and (req.user_name or req.user_email):
        parts = []
        if req.user_name:
            parts.append(f"Name: {req.user_name}")
        if req.user_email:
            parts.append(f"Email: {req.user_email}")
        context_note = (
            f"[Context: The customer's details are known — {', '.join(parts)}. "
            "Greet them by first name. Do NOT ask for their name or email.]"
        )
        history = [{"role": "system", "content": context_note}]

    result = await orchestrator.run(
        query=req.message,
        conversation_history=history,
        conversation_id=session_id,
        mode="chat",
    )

    history.append({"role": "user", "content": req.message})
    history.append({"role": "assistant", "content": result["response"]})
    await save_session_history(session_id, history)

    await log_conversation(
        session_id=session_id,
        mode="chat",
        transcript=req.message,
        response=result["response"],
        route=result["route"],
        user_email=req.user_email or None,
    )

    return {
        "session_id": session_id,
        "route": result["route"],
        "response": result["response"],
    }


@router.delete("/chat/{session_id}")
async def clear_session(session_id: str):
    await delete_session(session_id)
    return {"cleared": session_id}
