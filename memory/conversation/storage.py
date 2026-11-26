"""Stores conversations in Redis.

Redis data model:
  session:{sid}:messages   LIST        one JSON message per entry, appended with RPUSH
  session:{sid}:meta       HASH        user_id, title, summary, summarized_upto, created_at, updated_at, message_count
  user:{uid}:sessions      SORTED SET  member = session id, score = last-updated time (drives the sidebar order)
"""
import time
import uuid

from memory.conversation import history
from memory.redis_client import get_redis


def messages_key(session_id: str) -> str:
    """Redis key of the list holding a session's messages."""
    return f"session:{session_id}:messages"


def meta_key(session_id: str) -> str:
    """Redis key of the hash holding a session's metadata."""
    return f"session:{session_id}:meta"


def user_sessions_key(user_id: str) -> str:
    """Redis key of the sorted set indexing all of a user's sessions."""
    return f"user:{user_id}:sessions"


def create_session(user_id: str) -> str:
    """Create an empty session for a user and return its new session id."""
    r = get_redis()
    session_id = uuid.uuid4().hex
    now = time.time()
    r.hset(meta_key(session_id), mapping={
        "user_id": user_id,
        "title": "New chat",
        "summary": "",
        "summarized_upto": 0,  # how many of the oldest messages are already folded into `summary`
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
    })
    r.zadd(user_sessions_key(user_id), {session_id: now})
    return session_id


def append_messages(session_id: str, messages: list[dict]) -> None:
    """Append LLM-format messages (user, assistant, tool) to the end of a session's history."""
    r = get_redis()
    meta = get_session_meta(session_id)
    now = time.time()
    pipe = r.pipeline()  # send all commands together so the update is atomic
    for message in messages:
        pipe.rpush(messages_key(session_id), history.to_json(history.make_message(message)))
    pipe.hincrby(meta_key(session_id), "message_count", len(messages))
    pipe.hset(meta_key(session_id), "updated_at", now)
    pipe.zadd(user_sessions_key(meta["user_id"]), {session_id: now})  # moves the chat to the top of the sidebar
    pipe.execute()


def load_messages(session_id: str, start: int = 0, end: int = -1) -> list[dict]:
    """Load stored messages from a session (whole history by default; start/end are list indexes)."""
    raw_messages = get_redis().lrange(messages_key(session_id), start, end)
    return [history.from_json(raw) for raw in raw_messages]


def count_messages(session_id: str) -> int:
    """Return how many messages a session holds (the length of its Redis list)."""
    return get_redis().llen(messages_key(session_id))


def get_session_meta(session_id: str) -> dict:
    """Return a session's metadata as a dict (empty dict if the session does not exist)."""
    return get_redis().hgetall(meta_key(session_id))


def update_session_meta(session_id: str, **fields) -> None:
    """Update metadata fields of a session, e.g. title or summary."""
    get_redis().hset(meta_key(session_id), mapping=fields)


def list_sessions(user_id: str, limit: int = 50) -> list[dict]:
    """List a user's sessions, most recently active first (this feeds the sidebar)."""
    r = get_redis()
    session_ids = r.zrevrange(user_sessions_key(user_id), 0, limit - 1)
    sessions = []
    for sid in session_ids:
        meta = r.hgetall(meta_key(sid))
        if meta:  # skip ids whose data has expired or was deleted
            sessions.append({"session_id": sid, "title": meta["title"],
                             "updated_at": float(meta["updated_at"]),
                             "message_count": int(meta["message_count"])})
    return sessions


def session_belongs_to(session_id: str, user_id: str) -> bool:
    """True if the session exists and was created by this user (stops users opening each other's chats)."""
    return get_session_meta(session_id).get("user_id") == user_id


def delete_session(session_id: str) -> None:
    """Delete a session's messages, metadata, and its entry in the user's session index."""
    r = get_redis()
    user_id = get_session_meta(session_id).get("user_id")
    if user_id:
        r.zrem(user_sessions_key(user_id), session_id)
    r.delete(messages_key(session_id), meta_key(session_id))
