"""The chat route: sends one customer message to the agent."""
from fastapi import APIRouter, HTTPException

from agent.chat_service import chat_turn
from api.routes_sessions import require_user
from api.schemas import ChatRequest, ChatResponse
from memory.conversation import storage

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    """Run one chat turn (memory retrieval -> agent -> memory storage) and return the agent's reply."""
    require_user(body.user_id)
    try:
        session_id, reply = chat_turn(body.user_id, body.session_id, body.message)
    except PermissionError as exc:  # session belongs to someone else or does not exist
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # LLM timeout, bad API key, etc.
        raise HTTPException(status_code=502, detail=f"Agent error: {exc}")
    title = storage.get_session_meta(session_id)["title"]
    return ChatResponse(session_id=session_id, title=title, reply=reply)
