"""Orchestrates one chat turn: memory retrieval -> agent -> memory storage.

Both the CLI (now) and the FastAPI routes (step 8) call `chat_turn`, so the memory logic lives in one place.
"""
from agent.support_agent import build_system_message, run_agent
from memory.conversation import retrieval, storage, summarizer


def chat_turn(user_id: str, session_id: str | None, text: str) -> tuple[str, str]:
    """Handle one user message and return (session_id, assistant_reply).

    A new session is created when session_id is None. A session that belongs to another user is rejected.
    """
    if session_id is None:
        session_id = storage.create_session(user_id)
    elif not storage.session_belongs_to(session_id, user_id):
        raise PermissionError(f"Session {session_id} does not exist for user {user_id}")

    user_message = {"role": "user", "content": text}

    # 1. Retrieval: load the relevant history from Redis and build the LLM context
    context = retrieval.build_context(session_id, build_system_message(user_id))
    context.append(user_message)

    # 2. Agent: call the LLM (and tools) on top of that context
    new_messages = run_agent(user_id, context)

    # 3. Storage: persist the user message and everything the agent produced.
    #    Done only after the agent succeeds, so a failed LLM call leaves no dangling user message.
    storage.append_messages(session_id, [user_message] + new_messages)

    # 4. Housekeeping: title the chat and summarize old messages. These are nice-to-have, so a failure
    #    here must not lose the reply the customer is waiting for.
    try:
        summarizer.maybe_set_title(session_id, text)
        summarizer.maybe_summarize(session_id)
    except Exception as exc:
        print(f"  [memory] housekeeping skipped: {exc}")
    return session_id, new_messages[-1]["content"]
