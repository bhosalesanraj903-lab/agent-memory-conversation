"""Retrieval: decides which part of the stored history is sent to the LLM as context.

Strategy: rolling summary + sliding window.
  - messages older than `summarized_upto` are represented by the session's summary
  - messages from `summarized_upto` onwards are sent verbatim (at least the last WINDOW_SIZE of them)
Redis keeps the full history; only this slice goes to the LLM, so the prompt stays bounded.
"""
from config.settings import WINDOW_SIZE
from memory.conversation import history, storage


def get_window_start(session_id: str) -> int:
    """Index of the first message of the sliding window (the last WINDOW_SIZE messages).

    The start never lands on an orphaned 'tool' result: a tool message is only valid right after the
    assistant message that requested it, so we step back until that assistant message is included.
    """
    start = max(0, storage.count_messages(session_id) - WINDOW_SIZE)
    while start > 0 and storage.load_messages(session_id, start, start)[0]["role"] == "tool":
        start -= 1
    return start


def build_context(session_id: str, system_message: dict) -> list[dict]:
    """Build the LLM context for an existing session: system message, summary (if any), then recent messages."""
    meta = storage.get_session_meta(session_id)
    summarized_upto = int(meta.get("summarized_upto", 0))

    # Start at the window, but never later than the first message not yet covered by the summary,
    # otherwise messages between the summary and the window would be invisible to the LLM.
    start = min(get_window_start(session_id), summarized_upto)
    recent = [history.to_llm_message(m) for m in storage.load_messages(session_id, start, -1)]

    context = [system_message]
    if meta.get("summary"):
        context.append({"role": "system", "content": f"Summary of the earlier conversation:\n{meta['summary']}"})
    context += recent

    print(f"  [memory] context = system + {'summary + ' if meta.get('summary') else ''}"
          f"{len(recent)} recent of {storage.count_messages(session_id)} stored messages")
    return context
