"""Terminal chat for the agent, backed by Redis memory. Run from the project root:

  python -m agent.cli --user C001                  start a new chat
  python -m agent.cli --user C001 --list           list this user's past chats
  python -m agent.cli --user C001 --session <id>   resume a past chat (works after restarting the program)
"""
import argparse

from agent.chat_service import chat_turn
from memory.conversation import history, storage


def print_past_chats(user_id: str) -> None:
    """Print the user's saved chats, most recent first."""
    sessions = storage.list_sessions(user_id)
    if not sessions:
        print("No saved chats yet.")
    for s in sessions:
        print(f"{s['session_id']}  {s['message_count']:>3} msgs  {s['title']}")


def print_recent_history(session_id: str) -> None:
    """Show the last few visible messages when resuming a chat."""
    visible = [m for m in storage.load_messages(session_id) if history.is_visible_in_ui(m)]
    for m in visible[-6:]:
        label = "You" if m["role"] == "user" else "Agent"
        print(f"{label}: {m['content']}")
    print()


def main() -> None:
    """Parse arguments, then chat in a loop; every turn is saved to and loaded from Redis."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="C001", help="customer id: C001, C002 or C003")
    parser.add_argument("--session", help="resume this session id")
    parser.add_argument("--list", action="store_true", help="list this user's chats and exit")
    args = parser.parse_args()

    if args.list:
        print_past_chats(args.user)
        return

    session_id = args.session
    if session_id:
        if not storage.session_belongs_to(session_id, args.user):
            print(f"Session {session_id} not found for {args.user}.")
            return
        print(f"Resuming session {session_id}\n")
        print_recent_history(session_id)
    else:
        print("New chat (the session id is printed after your first message).")
    print(f"Chatting as {args.user}. Type 'exit' to quit.\n")

    while True:
        text = input("You: ").strip()
        if text.lower() in ("exit", "quit"):
            break
        if not text:
            continue
        session_id, reply = chat_turn(args.user, session_id, text)
        print(f"Agent: {reply}\n(session: {session_id})\n")


if __name__ == "__main__":
    main()
