"""Writes a sample conversation to Redis so you can inspect it with redis-cli.

Run from the project root: python -m scripts.demo_storage          (leaves the data in Redis)
                           python -m scripts.demo_storage --clean   (deletes the demo sessions)
"""
import sys

from memory.conversation import storage

DEMO_USER = "C001"


def main() -> None:
    """Create two demo sessions for one user, store messages in them, and print what was read back."""
    if "--clean" in sys.argv:
        for s in storage.list_sessions(DEMO_USER):
            storage.delete_session(s["session_id"])
        print("Deleted all sessions of", DEMO_USER)
        return

    first = storage.create_session(DEMO_USER)
    storage.append_messages(first, [
        {"role": "user", "content": "Where is ORD-1001?"},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_1", "type": "function",
             "function": {"name": "get_shipment_status", "arguments": '{"order_id": "ORD-1001"}'}}]},
        {"role": "tool", "tool_call_id": "call_1", "content": '{"status": "In Transit"}'},
        {"role": "assistant", "content": "Your order is in transit via FedEx."},
    ])
    second = storage.create_session(DEMO_USER)  # created later, so it should list first
    storage.append_messages(second, [{"role": "user", "content": "Show my last 2 orders"}])

    print("Sessions (newest first):")
    for s in storage.list_sessions(DEMO_USER):
        print("  ", s)
    print("\nStored messages of the first session:")
    for m in storage.load_messages(first):
        print("  ", m)
    print(f"\nInspect with:\n  docker exec -it agent-memory-redis redis-cli\n"
          f"  LRANGE session:{first}:messages 0 -1\n  HGETALL session:{first}:meta\n"
          f"  ZREVRANGE user:{DEMO_USER}:sessions 0 -1 WITHSCORES")


if __name__ == "__main__":
    main()
