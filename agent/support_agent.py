"""The single support agent: calls the LLM, runs tools, and loops until it has a final answer."""
from config.prompts import SYSTEM_PROMPT
from config.settings import MAX_TOOL_ROUNDS
from db.database import get_connection
from llm.llm_client import chat
from tools.order_tools import TOOL_SCHEMAS, run_tool


def build_system_message(customer_id: str) -> dict:
    """Create the system message, telling the agent which customer it is talking to."""
    conn = get_connection()
    row = conn.execute("SELECT name FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()
    conn.close()
    name = row["name"] if row else "Unknown"
    return {"role": "system", "content": f"{SYSTEM_PROMPT}\nThe logged-in customer is {name} ({customer_id})."}


def assistant_message_to_dict(message) -> dict:
    """Convert the LLM's message object into a plain dict (this is the format we will store in Redis later)."""
    result = {"role": "assistant", "content": message.content}
    if message.tool_calls:
        result["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in message.tool_calls
        ]
    return result


def run_agent(customer_id: str, context: list[dict]) -> list[dict]:
    """Run one agent turn on top of `context` and return only the NEW messages it produced.

    `context` is the conversation so far (system message first, ending with the user's message).
    The returned list holds any assistant tool-call messages, tool results, and the final assistant reply.
    """
    working = list(context)  # copy so the caller's list is not modified
    new_messages: list[dict] = []

    for _ in range(MAX_TOOL_ROUNDS):
        reply = assistant_message_to_dict(chat(working, tools=TOOL_SCHEMAS))
        working.append(reply)
        new_messages.append(reply)

        if "tool_calls" not in reply:  # no tool requested -> this is the final answer
            return new_messages

        # Execute every requested tool and feed the results back to the LLM
        for call in reply["tool_calls"]:
            fn = call["function"]
            print(f"  [tool] {fn['name']}({fn['arguments']})")
            result = run_tool(fn["name"], fn["arguments"], customer_id)
            tool_message = {"role": "tool", "tool_call_id": call["id"], "content": result}
            working.append(tool_message)
            new_messages.append(tool_message)

    # Safety net if the LLM keeps calling tools
    fallback = {"role": "assistant", "content": "Sorry, I could not complete that request. Please try again."}
    new_messages.append(fallback)
    return new_messages
