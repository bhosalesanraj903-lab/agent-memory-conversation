# Agent Conversation Memory: Project Documentation

## 1. Purpose

This is a demo for software engineers. It shows how to manage **conversation memory** for an AI agent the way production systems do: persist every message, list past chats in a sidebar, resume a chat after a restart, and keep the LLM prompt small however long the chat gets.

The business use case is deliberately small so the memory design stays in focus: an e-commerce support agent with three tools (list recent orders, get order details, get shipment status).

**Not the goal:** production readiness. The code is simple on purpose. Section 10 lists what a production system would add.

**Scope:** conversation memory only: storing, listing, resuming and retrieving chat history.

## 2. Architecture

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

| Component | Responsibility |
|---|---|
| `api/` | Routes and request/response schemas. Calls the chat service. |
| `agent/chat_service.py` | Orchestrates one turn. The single place where memory and the agent meet. |
| `agent/support_agent.py` | Calls the LLM, executes tool calls, loops until it has a final answer. |
| `tools/order_tools.py` | The three tools and their JSON schemas. |
| `memory/conversation/` | Everything about conversation history (see section 4). |
| `memory/redis_client.py` | One shared Redis connection. |
| `db/` | SQLite business data: customers, orders, items, shipments. |
| `llm/llm_client.py` | The only place that calls LiteLLM. |
| `config/` | Settings and all prompts. |
| `ui/` | The chat page. |

The CLI (`agent/cli.py`) and the API both call `chat_turn`, so there is one implementation of the memory logic.

## 3. One chat turn

1. The UI sends `{user_id, session_id?, message}` to `POST /chat`. With no `session_id`, a new session is created.
2. **Retrieval:** the context is built from the system prompt, the session's summary (if any), and the recent messages.
3. The new user message is appended to that context.
4. **Agent:** the LLM is called. If it asks for tools, they run and the results go back to the LLM. This repeats until it returns text (at most 5 LLM calls per user message).
5. **Storage:** the user message and everything the agent produced (tool-call messages, tool results, the final reply) are appended to Redis in one atomic step.
6. **Housekeeping:** if the chat still has the default title, one LLM call generates a title from the first message. If enough old messages have piled up, one LLM call folds them into the summary.
7. The reply, session id and title go back to the UI.

Storage happens after the agent succeeds. If the LLM call fails, nothing is saved and no unanswered user message is left in the history.

## 4. The memory design

### 4.1 Redis data model

| Key | Type | Content |
|---|---|---|
| `session:{sid}:messages` | List | One JSON message per entry, appended with `RPUSH` |
| `session:{sid}:meta` | Hash | `user_id`, `title`, `summary`, `summarized_upto`, `created_at`, `updated_at`, `message_count` |
| `user:{uid}:sessions` | Sorted Set | Member = session id, score = last-updated time |

Why these types:
- **List** is append-only and ordered, which is what a conversation is. `LRANGE` reads any slice cheaply, which retrieval needs.
- **Hash** holds small, individually updatable fields (the title and summary change independently of the messages).
- **Sorted Set** gives the sidebar its order. Every append updates the score, so the most recently active chat rises to the top. `ZREVRANGE` returns the newest first.

Redis runs in Docker with a named volume and AOF persistence (`appendonly yes`), so data survives a container restart and `docker compose down`. Only `down -v` deletes it.

The API server holds no conversation state. Resuming a chat means loading it by `session_id`, so any server instance could handle any request.

### 4.2 Message format (`history.py`)

A stored message is the same dict the LLM API uses, plus a timestamp:

```json
{"role": "assistant", "content": null,
 "tool_calls": [{"id": "call_1", "type": "function",
                 "function": {"name": "get_shipment_status", "arguments": "{\"order_id\": \"ORD-1001\"}"}}],
 "ts": "2026-10-27T01:16:27+00:00"}
```

Tool calls and tool results are stored, not just the text. That makes replay faithful and lets the model see what its tools returned earlier. `ts` is stripped before a message goes back to the LLM (`to_llm_message`). The UI shows only user text and final assistant replies (`is_visible_in_ui`), so tool plumbing stays hidden.

### 4.3 Retrieval: window plus rolling summary (`retrieval.py`)

Redis keeps the **full** history forever. The LLM sees only a slice:

```
[ system prompt ]
[ summary of older messages ]      ← only once a summary exists
[ recent messages, verbatim ]
```

- **Sliding window:** the last `WINDOW_SIZE` messages (default 10).
- **Rolling summary:** messages older than the window are folded into one summary by the LLM, once `SUMMARY_TRIGGER` of them (default 10) have accumulated. The new summary is built from the old summary plus the newly aged-out messages, so it rolls forward instead of growing.
- **`summarized_upto`:** how many of the oldest messages the summary already covers. This one number is the bookmark that ties the summary and the window together.

Two rules keep this correct:

1. **No gap.** Recent messages start at the *earlier* of the window start and `summarized_upto`. Without this, messages that left the window but are not yet summarized would be invisible to the LLM until the next summary.
2. **No orphaned tool results.** The API rejects a `tool` message that does not directly follow the assistant message that requested it. If the window would start on a tool result, it steps back to include the request. The summary boundary always lands on such a safe point.

Worked example from a test run with `WINDOW_SIZE=4` and `SUMMARY_TRIGGER=4` over 7 turns (16 stored messages):

| After turn | Stored | Summary covers | Messages sent to the LLM |
|---|---|---|---|
| 1–2 | 4 – 6 | nothing | all |
| 3 | 8 | messages 0–3 | summary + 4 recent |
| 5 | 12 | messages 0–7 | summary + 4–6 recent |
| 7 | 16 | messages 0–11 | summary + 4–6 recent |

With 16 messages stored, the LLM never received more than 9. With the defaults, the bounded size is roughly `WINDOW_SIZE` to `WINDOW_SIZE + SUMMARY_TRIGGER` messages plus the summary.

### 4.4 Titles

After the first exchange, one LLM call turns the first user message into a title of at most 5 words. It happens once, in the same request as the reply. If it fails, the title stays "New chat" and is retried on the next turn (using that turn's message).

## 5. Tools and data isolation

| Tool | Returns |
|---|---|
| `list_recent_orders(limit)` | The customer's newest N orders: id, date, status, total, item names |
| `get_order_details(order_id)` | Products with prices, billing breakdown, payment, addresses, cancellation and refund info |
| `get_shipment_status(order_id)` | Carrier, tracking, location, shipped/original/new delivery dates, delay reason |

**The LLM never chooses the customer.** `customer_id` comes from the logged-in session and is injected by `run_tool`. It is not in the tool schemas, and a `customer_id` supplied by the LLM is discarded. Order lookups also filter on the owner, so asking for another customer's order returns "not found". The same rule applies to memory: `session_belongs_to` stops a user opening someone else's chat (404 from the API).

## 6. Business data (SQLite)

Seeded by `db/seed.py`. The data is rich enough for conversations of 5–6 turns:

| Order | Customer | Interesting because |
|---|---|---|
| ORD-1001 | Alice | Two products, a discount, tax and shipping; in transit |
| ORD-1002 | Alice | Processing; no shipment yet |
| ORD-1003 | Bob | Delivered |
| ORD-1004 | Bob | Out for delivery today |
| ORD-1005 | Carol | **Delayed**: snowstorm closed the Denver hub; new date Nov 2 (was Oct 24) |
| ORD-1006 | Carol | **Cancelled**: customer found a lower price; refund of 90.23 pending |

Running `python -m db.seed` drops and recreates the tables, so it is safe to repeat.

## 7. API

| Method and path | Purpose |
|---|---|
| `GET /users` | Customers for the user picker |
| `GET /users/{id}/sessions` | The sidebar: a user's chats, newest first |
| `POST /sessions` | Create an empty chat |
| `GET /sessions/{id}/messages?user_id=` | Visible messages of a chat, for replay |
| `POST /chat` | Send a message; returns `{session_id, title, reply}` |
| `GET /health` | API and Redis status |

Interactive docs: `/docs`.

## 8. Configuration

Set in `.env` (see `.env.example`); defaults live in `config/settings.py`.

| Variable | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | none | Your OpenAI key |
| `LLM_MODEL` | `openai/gpt-4o-mini` | LiteLLM model name. The `openai/` prefix names the provider explicitly. |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis location |
| `SQLITE_PATH` | `db/orders.db` | Business database |
| `WINDOW_SIZE` | 10 | Recent messages sent verbatim |
| `SUMMARY_TRIGGER` | 10 | Aged-out messages that trigger a new summary |

Fixed in code: at most 5 LLM calls per user message (`MAX_TOOL_ROUNDS`), a 30-second LLM timeout, and no automatic retries (`llm/llm_client.py`). Prompts are in `config/prompts.py`.

**To see summarization quickly**, set `WINDOW_SIZE=4` and `SUMMARY_TRIGGER=4`, then watch the `[memory]` lines in the server terminal.

## 9. Design decisions and trade-offs

| Decision | Why | Trade-off |
|---|---|---|
| Keep the full history; send a slice | Full audit trail and replay; the prompt stays bounded | Redis grows without limit (no TTL yet) |
| Window **plus** summary, not window alone | Old facts (order ids, decisions) survive | Extra LLM call; the summary can drop or distort details |
| Message-count window, not token-count | Easy to explain and read | Long tool results can still make a window large |
| Store tool calls and results | Faithful replay; the model keeps its tool context | More storage and tokens than text only |
| Summarize after saving the reply | The customer is not blocked on a failure | A turn that triggers a summary takes one extra LLM call |
| Housekeeping failures are swallowed | A failed title or summary must not lose a reply | Failures are only visible in logs |
| Sessions created lazily on the first message | No empty "New chat" rows in the sidebar | `POST /sessions` exists but the UI does not use it |
| List + Hash + Sorted Set on plain Redis | Simple, standard, no modules | No similarity search over history (not needed here) |
| One `chat_turn` for CLI and API | One implementation of the memory flow | None for a demo |
| LLM timeout and no retries | One request is exactly one call; failures are visible | A transient network error fails the turn |

## 10. Known limitations (what production would add)

- **No authentication.** Users pick a customer from a dropdown. A real system derives `user_id` from a verified login.
- **No expiry or deletion.** Add Redis TTLs, a retention policy, and delete/rename endpoints.
- **No concurrency control.** Two simultaneous messages in one session could interleave, and two summarizations could race. Use a per-session lock or a stream with ordering.
- **Token budgeting.** Window by tokens, not message count, and cap tool result size.
- **Summary quality.** A summary can lose or distort facts. Production systems evaluate summaries and sometimes pin key facts separately.
- **Privacy.** Messages include billing details. Production needs encryption, PII redaction and access auditing.
- **Streaming.** Replies arrive all at once. Production chat streams tokens.
- **Observability.** Only `print` logging. Production needs tracing, token and cost metrics.

## 11. Things to know when running the demo

- **The first LLM call can be slow.** On the development machine the first request to OpenAI took over 80 seconds, then later calls took about 1 second. The same delay occurs with the OpenAI SDK alone, so it is connection setup (DNS, IPv6, VPN or proxy), not this code. Send one message before presenting.
- **Server start takes about 20 seconds.** Importing LiteLLM is slow, especially on Python 3.14. Python 3.12 or 3.13 is quicker.
- **`mcp` is in `requirements.txt` on purpose.** This LiteLLM version imports it when tools are passed, even though this project uses no MCP.
- **Run commands from the project root,** and use `python -m package.module` for scripts. Running `python db/database.py` fails with `No module named 'config'`.
- **Redis must be running** before the server starts. `/health` shows whether it is reachable.
- **Console logs explain the memory behaviour:** `[llm] call #N`, `[tool] ...`, and `[memory] context = system + summary + N recent of M stored messages`.

## 12. Project structure

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
├── scripts/                 demo_storage.py (writes sample chats for redis-cli inspection)
└── ui/                      index.html, style.css, app.js
```

## 13. How the project was built

The project was built in ten steps, each meant to be committed and tagged. Checking out a tag shows the project at that point, which helps when teaching the progression.

| Tag | What it adds |
|---|---|
| `v0.1-scaffold` | Folders, config, prompts |
| `v0.2-business-data` | SQLite schema and seed data |
| `v0.3-agent-no-memory` | Tools and the agent loop; no memory (the "before" picture) |
| `v0.4-redis-infra` | Redis in Docker, connection helper |
| `v0.5-history-storage` | Message format and Redis storage |
| `v0.6-retrieval-window` | Sliding-window retrieval; chats survive a restart |
| `v0.7-summary-and-titles` | Rolling summary and generated titles |
| `v0.8-api` | FastAPI routes |
| `v0.9-chat-ui` | The chat UI |
| `v1.0-docs` | README and this document |
