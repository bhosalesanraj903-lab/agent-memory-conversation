"""FastAPI entry point. Run from the project root: python main.py   (docs at http://localhost:8000/docs)"""
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api import routes_chat, routes_sessions
from config.settings import SQLITE_PATH
from db.seed import seed_database
from memory.redis_client import ping


@asynccontextmanager
async def lifespan(app: FastAPI):
    """On startup: seed the SQLite demo data if missing and make sure Redis is reachable."""
    if not os.path.exists(SQLITE_PATH):
        seed_database()
        print("Seeded demo database.")
    if not ping():
        print("WARNING: cannot reach Redis. Run: docker compose up -d")
    yield


app = FastAPI(title="Support Agent Memory Demo", lifespan=lifespan)
app.include_router(routes_sessions.router)
app.include_router(routes_chat.router)


@app.get("/health")
def health() -> dict:
    """Report whether the API is up and Redis is reachable."""
    return {"status": "ok", "redis": ping()}


# Serve the chat UI (added in step 9) if it exists
if os.path.exists("ui/index.html"):
    app.mount("/", StaticFiles(directory="ui", html=True), name="ui")


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000)
