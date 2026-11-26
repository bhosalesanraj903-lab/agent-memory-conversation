# Agent Conversation Memory Demo

An e-commerce support chatbot whose conversations are stored in Redis, so a chat continues even after you stop and start the service. For how it works and why, see [documentation.md](documentation.md).

## 1. Prerequisites
- Python 3.10 or newer
- Docker Desktop, installed and running
- An OpenAI API key

## 2. Set up

Run every command from the project root folder.

**Step 1. Create a virtual environment and install dependencies**
*** For windows cmd prompt, the commands might differ, please check online***
```bash
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
```

**Step 2. Create your `.env` file**
```bash
cp .env.example .env
```
Open `.env` and set your key:
```
OPENAI_API_KEY=sk-...
```
Leave the other values as they are.

**Step 3. Start Redis**
```bash
docker compose up -d
```

**Step 4. Check that Redis is reachable**
```bash
python3 -m memory.redis_client
```
Expected output: `Redis OK at redis://localhost:6379/0`

**Step 5. Create the demo order data (optional)**

The server creates it automatically on first start. To create or reset it manually:
```bash
python3 -m db.seed
```

## 3. Run

**Step 6. Start the server**
```bash
python3 main.py
```
Wait for the line `Uvicorn running on http://127.0.0.1:8000`. This can take around 20 seconds.

**Step 7. Open the chat UI**

Go to http://localhost:8000 in your browser.

The API docs are at http://localhost:8000/docs.

## 4. Try it

1. Pick **Carol Lee** in the customer dropdown.
2. Ask: `Show me my last 3 orders`
3. Ask: `Why is my coffee maker order delayed?`
4. Ask: `When will it arrive now?`
5. Click **+ New chat** and ask about another order. Both chats appear in the left sidebar.
6. Stop the server (`Ctrl+C`), start it again with `python main.py`, and reload the page. Your chats are still there. Open one and ask `What was the reason for the delay again?`

Customers and the orders they own:

| Customer | Orders |
|---|---|
| Alice Johnson (C001) | ORD-1001, ORD-1002 |
| Bob Smith (C002) | ORD-1003, ORD-1004 |
| Carol Lee (C003) | ORD-1005 (delayed), ORD-1006 (cancelled) |


## 6. Look inside Redis
```bash
docker exec -it agent-memory-redis redis-cli
```
Then, for example:
```
KEYS *
ZREVRANGE user:C003:sessions 0 -1
HGETALL session:<session_id>:meta
LRANGE session:<session_id>:messages 0 -1
```

## 7. Stop and clean up
```bash
# stop the server: Ctrl+C
docker compose stop        # stop Redis, keep all chats
docker compose down        # remove the container, keep all chats
docker compose down -v     # remove the container AND delete all stored chats
```
