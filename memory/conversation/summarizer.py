"""LLM-powered helpers that keep long conversations manageable: rolling summary and chat titles."""
from config.prompts import SUMMARY_PROMPT, TITLE_PROMPT
from config.settings import SUMMARY_TRIGGER
from llm.llm_client import chat
from memory.conversation import retrieval, storage

DEFAULT_TITLE = "New chat"


def format_for_summary(messages: list[dict]) -> str:
    """Render stored messages as plain text lines for the summarizer prompt."""
    lines = []
    for m in messages:
        if m["role"] == "user":
            lines.append(f"Customer: {m['content']}")
        elif m["role"] == "tool":
            lines.append(f"Tool result: {m['content'][:800]}")  # truncate long tool output
        elif m.get("tool_calls"):
            calls = ", ".join(f"{c['function']['name']}({c['function']['arguments']})" for c in m["tool_calls"])
            lines.append(f"Agent called tool: {calls}")
        else:
            lines.append(f"Agent: {m['content']}")
    return "\n".join(lines)


def maybe_summarize(session_id: str) -> bool:
    """Fold messages that fell out of the window into the rolling summary once enough have piled up.

    Returns True if a new summary was written. Raw messages stay in Redis; only `summary` and
    `summarized_upto` (how many of the oldest messages the summary covers) change.
    """
    meta = storage.get_session_meta(session_id)
    summarized_upto = int(meta["summarized_upto"])
    window_start = retrieval.get_window_start(session_id)

    overflow = window_start - summarized_upto  # messages older than the window that are not summarized yet
    if overflow < SUMMARY_TRIGGER:
        return False

    old_messages = storage.load_messages(session_id, summarized_upto, window_start - 1)
    prompt = SUMMARY_PROMPT.format(summary=meta["summary"] or "(none)", messages=format_for_summary(old_messages))
    summary = chat([{"role": "user", "content": prompt}]).content.strip()

    storage.update_session_meta(session_id, summary=summary, summarized_upto=window_start)
    print(f"  [memory] summarized messages {summarized_upto}..{window_start - 1} into the rolling summary")
    return True


def maybe_set_title(session_id: str, first_user_text: str) -> None:
    """Generate a short sidebar title for a chat that still has the default title."""
    if storage.get_session_meta(session_id)["title"] != DEFAULT_TITLE:
        return
    reply = chat([{"role": "user", "content": TITLE_PROMPT.format(message=first_user_text)}])
    title = reply.content.strip().strip('"').strip("'")[:60] or DEFAULT_TITLE
    storage.update_session_meta(session_id, title=title)
    print(f"  [memory] chat title set to: {title}")
