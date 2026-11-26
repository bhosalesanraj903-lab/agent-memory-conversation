"""Creates the shared Redis connection used by all memory components.

Run a connectivity check from the project root: python -m memory.redis_client
"""
import redis

from config.settings import REDIS_URL

_client: redis.Redis | None = None  # one shared connection pool for the whole process


def get_redis() -> redis.Redis:
    """Return the shared Redis client, creating it on first use (strings are decoded to str)."""
    global _client
    if _client is None:
        _client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    return _client


def ping() -> bool:
    """Return True if Redis is reachable, False otherwise."""
    try:
        return bool(get_redis().ping())
    except redis.exceptions.ConnectionError:
        return False


if __name__ == "__main__":
    if ping():
        print(f"Redis OK at {REDIS_URL}")
    else:
        print(f"Cannot reach Redis at {REDIS_URL}. Is it running? Try: docker compose up -d")
