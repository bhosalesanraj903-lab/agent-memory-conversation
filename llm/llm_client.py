"""Thin wrapper around LiteLLM so the rest of the code never calls the provider directly."""
import time

import litellm

from config.settings import LLM_MODEL

LLM_TIMEOUT_SECONDS = 30  # fail fast instead of hanging for minutes
llm_call_count = 0        # total LLM requests made by this process, printed for visibility


def chat(messages: list[dict], tools: list[dict] | None = None):
    """Send messages (and optional tool schemas) to the LLM and return the assistant message object.

    Exactly one request is made: retries are disabled and the call times out after 30 seconds.
    """
    global llm_call_count
    llm_call_count += 1
    print(f"  [llm] call #{llm_call_count} -> {LLM_MODEL} ({len(messages)} messages)")
    started = time.time()

    kwargs = {"model": LLM_MODEL, "messages": messages, "temperature": 0,
              "timeout": LLM_TIMEOUT_SECONDS, "num_retries": 0}
    if tools:
        kwargs["tools"] = tools
    response = litellm.completion(**kwargs)

    print(f"  [llm] call #{llm_call_count} finished in {time.time() - started:.1f}s")
    return response.choices[0].message
