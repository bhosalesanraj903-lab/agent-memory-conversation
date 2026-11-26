"""Request and response shapes of the API (validated automatically by FastAPI)."""
from pydantic import BaseModel


class ChatRequest(BaseModel):
    """Body of POST /chat. Leave session_id empty to start a new chat."""
    user_id: str
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    """Reply of POST /chat: the agent's answer plus the session it belongs to."""
    session_id: str
    title: str
    reply: str


class NewSessionRequest(BaseModel):
    """Body of POST /sessions."""
    user_id: str


class SessionSummary(BaseModel):
    """One row of the sidebar list."""
    session_id: str
    title: str
    updated_at: float
    message_count: int


class Message(BaseModel):
    """One message shown in the chat window."""
    role: str
    content: str
    ts: str
