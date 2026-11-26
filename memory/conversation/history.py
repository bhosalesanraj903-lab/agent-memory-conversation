"""The conversation history format: how one chat message is represented and stored.

A stored message is the same dict the LLM API uses (role, content, tool_calls, tool_call_id)
plus a timestamp `ts`. It is serialised to a JSON string so it fits in a Redis list.
"""
import json
from datetime import datetime, timezone

# Fields the LLM API understands. Anything else (like our `ts`) is stripped before calling the LLM.
LLM_FIELDS = ("role", "content", "tool_calls", "tool_call_id")


def make_message(message: dict) -> dict:
    """Turn an LLM-format message into a storable message by adding a UTC timestamp."""
    stored = {k: message[k] for k in LLM_FIELDS if k in message}
    stored["ts"] = datetime.now(timezone.utc).isoformat()
    return stored


def to_json(stored: dict) -> str:
    """Serialise a stored message to the JSON string kept in the Redis list."""
    return json.dumps(stored)


def from_json(raw: str) -> dict:
    """Parse a JSON string from the Redis list back into a stored message dict."""
    return json.loads(raw)


def to_llm_message(stored: dict) -> dict:
    """Convert a stored message back to the plain format the LLM API accepts (drops `ts`)."""
    return {k: stored[k] for k in LLM_FIELDS if k in stored}


def is_visible_in_ui(stored: dict) -> bool:
    """True for messages the customer should see: user text and final assistant replies (not tool plumbing)."""
    if stored["role"] == "user":
        return True
    return stored["role"] == "assistant" and not stored.get("tool_calls") and bool(stored.get("content"))
