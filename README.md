# Agent conversation memory

An e-commerce support chatbot that keeps its conversations in Redis. Every message is saved, past chats show up in a sidebar, a chat picks up where it left off after the server restarts, and the prompt sent to the LLM stays small no matter how long the chat gets.

The support use case is kept small on purpose so the memory design stays in focus. The agent has three tools: list recent orders, get order details, and get shipment status. This is a teaching demo, not production code. See [Known limitations](#known-limitations) for what a real system would add, and [documentation.md](documentation.md) for the full design write-up.

## How it works

```
Browser (HTML/CSS/JS)
    │  REST/JSON
FastAPI  (api/)            ── thin HTTP layer, no business logic
    │
Chat service (agent/chat_service.py)   ── one chat turn: retrieve → agent → store
    ├── Memory (memory/conversation/)
    │      history.py     message format
    │      storage.py     write/read Redis
    │      retrieval.py   choose what the LLM sees
    │      summarizer.py  rolling summary + chat titles
    │            │
    │          Redis (Docker)
    └── Agent (agent/support_agent.py) ── LLM tool-calling loop
           │            │
       LiteLLM ──► OpenAI      Tools (tools/) ──► SQLite (db/)
```

Each message goes through `chat_turn` in `agent/chat_service.py`. Both the API and the CLI (`agent/cli.py`) call it, so the memory logic lives in one place:

1. Load the context: the system prompt, the chat's summary if it has one, and the recent messages.
2. Run the agent. If the LLM asks for tools, they run and the results go back to it, up to 5 LLM calls per message.
3. Save the user message, the tool calls, the tool results and the final reply to Redis in one atomic step. This happens only after the agent succeeds, so a failed LLM call leaves no unanswered message in the history.
4. Housekeeping: give a new chat a title, and fold old messages into the summary once enough have piled up. If either fails, the customer still gets the reply.

### What Redis stores

| Key | Type | Content |
|---|---|---|
| `session:{sid}:messages` | List | One JSON message per entry, in order |
| `session:{sid}:meta` | Hash | `user_id`, `title`, `summary`, `summarized_upto`, timestamps, `message_count` |
| `user:{uid}:sessions` | Sorted set | Session IDs scored by last update, so the newest chat is at the top of the sidebar |

Redis runs in Docker with append-only persistence and a named volume, so chats survive a container restart and `docker compose down`. The API server keeps no conversation state of its own.

Tool calls and tool results are stored along with the text. The model can see what its tools returned earlier, and the UI hides that plumbing and shows only the customer's messages and the final replies.

### What the LLM sees

Redis keeps the full history. The LLM gets a slice of it:

```
[ system prompt ]
[ summary of older messages ]      ← only once a summary exists
[ recent messages, verbatim ]
```

- The sliding window is the last `WINDOW_SIZE` messages (default 10).
- Once `SUMMARY_TRIGGER` messages (default 10) have fallen out of the window, one LLM call folds them into the summary. The new summary is built from the old summary plus those messages, so it rolls forward and doesn't keep growing.
- `summarized_upto` records how many of the oldest messages the summary covers. Recent messages start at whichever is earlier, the window start or `summarized_upto`, so no message drops out of view between summaries.
- The window never starts on a tool result without the assistant message that requested it, because the OpenAI API rejects that.

With the defaults, the summary first appears at around 20 stored messages, and the prompt stays at roughly 10 to 20 messages plus the summary after that.

### Data isolation

The LLM never chooses the customer. `customer_id` comes from the session and is added by `run_tool`. It isn't in the tool schemas, and if the LLM sends one anyway, it's thrown away. Order lookups filter on the owner, so asking about another customer's order returns "not found". Chats follow the same rule: opening another user's session returns 404.

## Prerequisites

- Python 3.10 or newer. Server start is quicker on 3.12 or 3.13; LiteLLM imports slowly on 3.14.
- Docker (Docker Desktop or OrbStack), running
- An OpenAI API key

## Setup

Run every command from the project root.

1. Create a virtual environment and install the dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

   On Windows, activate with `.venv\Scripts\activate` instead.

2. Create your `.env` file and add your key:

   ```bash
   cp .env.example .env
   ```

   ```
   OPENAI_API_KEY=sk-...
   ```

3. Start Redis and check that it's reachable:

   ```bash
   docker compose up -d
   python -m memory.redis_client
   ```

   Expected output: `Redis OK at redis://localhost:6379/0`

4. Start the server:

   ```bash
   python main.py
   ```

   Wait for `Uvicorn running on http://127.0.0.1:8000`, which can take about 20 seconds. The demo order database is created on first start. To reset it later, run `python -m db.seed`.

5. Open http://localhost:8000 for the chat UI, or http://localhost:8000/docs for the API docs.

## Try it

1. Pick **Carol Lee** in the customer dropdown.
2. Ask `Show me my last 3 orders`.
3. Ask `Why is my coffee maker order delayed?`
4. Ask `When will it arrive now?`
5. Click **+ New chat** and ask about another order. Both chats show up in the sidebar.
6. Stop the server with Ctrl+C, start it again, and reload the page. Open the first chat and ask `What was the reason for the delay again?`

Watch the server terminal while you chat. The `[memory]`, `[llm]` and `[tool]` lines show what was loaded and called, for example `[memory] context = system + summary + 11 recent of 22 stored messages`. To see summarization sooner, set `WINDOW_SIZE=4` and `SUMMARY_TRIGGER=4` in `.env` and restart.

### Demo data

| Order | Customer | Details |
|---|---|---|
| ORD-1001 | Alice Johnson (C001) | Two products, a discount, tax and shipping; in transit |
| ORD-1002 | Alice Johnson (C001) | Processing; no shipment yet |
| ORD-1003 | Bob Smith (C002) | Delivered |
| ORD-1004 | Bob Smith (C002) | Out for delivery today |
| ORD-1005 | Carol Lee (C003) | Delayed: a snowstorm closed the Denver hub; new date Nov 2 (was Oct 24) |
| ORD-1006 | Carol Lee (C003) | Cancelled: customer found a lower price; refund of 90.23 pending |

## API

| Method and path | Purpose |
|---|---|
| `GET /users` | Customers for the user picker |
| `GET /users/{id}/sessions` | A user's chats, newest first |
| `POST /sessions` | Create an empty chat |
| `GET /sessions/{id}/messages?user_id=` | Visible messages of a chat |
| `POST /chat` | Send `{user_id, session_id?, message}`; returns `{session_id, title, reply}` |
| `GET /health` | API and Redis status |

## Configuration

Set these in `.env`. Defaults are in `config/settings.py`, and all prompts are in `config/prompts.py`.

| Variable | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | none | Your OpenAI key |
| `LLM_MODEL` | `openai/gpt-4o-mini` | LiteLLM model name |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis location |
| `SQLITE_PATH` | `db/orders.db` | Order database |
| `WINDOW_SIZE` | 10 | Recent messages sent verbatim |
| `SUMMARY_TRIGGER` | 10 | Messages outside the window that trigger a new summary |

The code also sets a limit of 5 LLM calls per message, a 30-second LLM timeout, and no automatic retries.

## Look inside Redis

```bash
docker exec -it agent-memory-redis redis-cli
```

```
KEYS *
ZREVRANGE user:C003:sessions 0 -1
HGETALL session:<session_id>:meta
LRANGE session:<session_id>:messages 0 -1
```

`python -m scripts.demo_storage` writes sample chats you can inspect this way.

## Troubleshooting

- The first LLM call can be slow. On the machine this was developed on, the first OpenAI request took over 80 seconds and later ones took about 1 second. The same delay happened with the OpenAI SDK alone, so it's connection setup (DNS, IPv6, VPN or proxy), not this code. Send one message before a demo.
- `mcp` is in `requirements.txt` even though the project doesn't use MCP. This LiteLLM version imports it when tools are passed.
- Run scripts as modules from the project root (`python -m db.seed`). Running `python db/database.py` fails with `No module named 'config'`.
- Redis has to be running before the server starts. `/health` shows whether it's reachable.

## Known limitations

- No authentication. Users pick a customer from a dropdown; a real system would take `user_id` from a verified login.
- No expiry or deletion. Redis grows without limit, and there are no endpoints to delete or rename a chat.
- No concurrency control. Two messages sent at the same time in one chat could interleave, and two summaries could race.
- The window counts messages, not tokens, so long tool results can still make the prompt large.
- A summary can drop or distort details. For example, it keeps facts but loses the order in which the customer asked things.
- Messages include billing details, with no encryption or PII redaction.
- Replies arrive all at once, without streaming.
- Logging is plain `print` output, with no tracing or token and cost metrics.

## Project structure

```
├── main.py                  FastAPI entry point
├── docker-compose.yml       Redis with volume + AOF
├── config/                  settings.py, prompts.py
├── api/                     routes_chat.py, routes_sessions.py, schemas.py
├── agent/                   chat_service.py, support_agent.py, cli.py
├── tools/                   order_tools.py
├── llm/                     llm_client.py
├── memory/
│   ├── redis_client.py
│   └── conversation/        history.py, storage.py, retrieval.py, summarizer.py
├── db/                      database.py, seed.py (orders.db is generated)
├── scripts/                 demo_storage.py
└── ui/                      index.html, style.css, app.js
```

## Stop and clean up

```bash
docker compose stop        # stop Redis, keep all chats
docker compose down        # remove the container, keep all chats
docker compose down -v     # remove the container and delete all stored chats
```
