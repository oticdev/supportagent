import uuid
from fastapi import APIRouter, Request
from pydantic import BaseModel
from main import limiter

from agent import orchestrator
from db import get_session_history, save_session_history, delete_session, log_conversation
from observability import set_request_context

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
    set_request_context(request_id="", session_id=session_id)
    history = await get_session_history(session_id)

    result = await orchestrator.run(
        query=req.message,
        conversation_history=history,
        conversation_id=session_id,
        mode="chat",
        user_name=req.user_name,
        user_email=req.user_email,
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
