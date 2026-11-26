"""Central configuration. Every other module imports its settings from here."""
import os

from dotenv import load_dotenv

# Load variables from the .env file into the process environment
load_dotenv()


def _get_int(name: str, default: int) -> int:
    """Read an integer environment variable, ignoring any inline '# comment'."""
    raw = os.getenv(name, str(default)).split("#")[0].strip()
    return int(raw)


# LLM settings (LiteLLM reads OPENAI_API_KEY from the environment itself)
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")

# Storage settings
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SQLITE_PATH = os.getenv("SQLITE_PATH", "db/orders.db")

# Conversation memory settings
WINDOW_SIZE = _get_int("WINDOW_SIZE", 10)
SUMMARY_TRIGGER = _get_int("SUMMARY_TRIGGER", 10)

# Safety limit so the agent cannot loop on tool calls forever
MAX_TOOL_ROUNDS = 5
