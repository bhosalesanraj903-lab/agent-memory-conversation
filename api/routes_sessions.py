"""Routes for users and for browsing past chats (the sidebar and chat replay)."""
from fastapi import APIRouter, HTTPException

from api.schemas import Message, NewSessionRequest, SessionSummary
from db.seed import list_customers
from memory.conversation import history, storage

router = APIRouter()


def require_user(user_id: str) -> None:
    """Raise 404 if the customer id is not one of the seeded customers."""
    if user_id not in [c["customer_id"] for c in list_customers()]:
        raise HTTPException(status_code=404, detail=f"Unknown user {user_id}")


@router.get("/users")
def get_users() -> list[dict]:
    """List the demo customers for the user picker."""
    return list_customers()


@router.get("/users/{user_id}/sessions", response_model=list[SessionSummary])
def get_user_sessions(user_id: str) -> list[dict]:
    """List a user's past chats, most recent first (the sidebar)."""
    require_user(user_id)
    return storage.list_sessions(user_id)


@router.post("/sessions", response_model=SessionSummary)
def create_session(body: NewSessionRequest) -> dict:
    """Create an empty chat for a user ('New chat' button)."""
    require_user(body.user_id)
    session_id = storage.create_session(body.user_id)
    return [s for s in storage.list_sessions(body.user_id) if s["session_id"] == session_id][0]


@router.get("/sessions/{session_id}/messages", response_model=list[Message])
def get_session_messages(session_id: str, user_id: str) -> list[dict]:
    """Return the visible messages of a chat so the UI can show it again (user must own the chat)."""
    if not storage.session_belongs_to(session_id, user_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return [m for m in storage.load_messages(session_id) if history.is_visible_in_ui(m)]
