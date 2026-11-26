"""The three tools exposed to the agent, plus their OpenAI-style JSON schemas.

Every tool function receives the logged-in `customer_id`. It is injected by `run_tool`
from the session, never chosen by the LLM, so a customer can only read their own data.
"""
import json

from db.database import get_connection


def list_recent_orders(customer_id: str, limit: int = 5) -> dict:
    """Tool 1: list the customer's most recent orders (newest first) with a short summary of each."""
    limit = max(1, min(int(limit), 20))  # keep the result size sensible
    conn = get_connection()
    orders = conn.execute(
        """SELECT order_id, order_date, status, total FROM orders
           WHERE customer_id = ? ORDER BY order_date DESC, order_id DESC LIMIT ?""",
        (customer_id, limit),
    ).fetchall()
    result = []
    for o in orders:
        items = conn.execute("SELECT product, quantity FROM order_items WHERE order_id = ?", (o["order_id"],)).fetchall()
        result.append({**dict(o), "items": [f"{i['quantity']} x {i['product']}" for i in items]})
    conn.close()
    return {"orders": result}


def get_order_details(customer_id: str, order_id: str) -> dict:
    """Tool 2: get one of the customer's orders with products, billing/payment details and cancellation info."""
    conn = get_connection()
    row = conn.execute(
        """SELECT o.*, c.name AS customer_name
           FROM orders o JOIN customers c ON c.customer_id = o.customer_id
           WHERE o.order_id = ? AND o.customer_id = ?""",  # ownership check
        (order_id.upper(), customer_id),
    ).fetchone()
    if row is None:
        conn.close()
        return {"error": f"Order {order_id} not found"}
    items = conn.execute(
        "SELECT product, sku, quantity, unit_price FROM order_items WHERE order_id = ?",
        (order_id.upper(),),
    ).fetchall()
    conn.close()
    order = {k: v for k, v in dict(row).items() if v is not None}  # drop empty fields to save tokens
    order["items"] = [dict(i) for i in items]
    return order


def get_shipment_status(customer_id: str, order_id: str) -> dict:
    """Tool 3: get shipment status (carrier, location, ETA, delay reason, new delivery date) of the customer's order."""
    conn = get_connection()
    row = conn.execute(
        """SELECT s.* FROM shipments s JOIN orders o ON o.order_id = s.order_id
           WHERE s.order_id = ? AND o.customer_id = ?""",  # ownership check
        (order_id.upper(), customer_id),
    ).fetchone()
    conn.close()
    if row is None:
        return {"error": f"No shipment found for order {order_id} (it may not have shipped yet, was cancelled, or does not exist)"}
    return {k: v for k, v in dict(row).items() if v is not None}


# Tool schemas in the format LiteLLM/OpenAI expect. customer_id is deliberately not exposed to the LLM.
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_recent_orders",
            "description": "List the logged-in customer's most recent orders, newest first. Use when the customer asks about their orders without giving an order id.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "How many recent orders to list (default 5)"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_details",
            "description": "Get a customer order by order id: products with prices, billing and payment details, order status, and cancellation/refund info.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string", "description": "Order id, e.g. ORD-1001"}},
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_shipment_status",
            "description": "Get the current shipment status of an order by order id: carrier, tracking, location, delivery dates, and delay reason if delayed.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string", "description": "Order id, e.g. ORD-1001"}},
                "required": ["order_id"],
            },
        },
    },
]

# Maps the tool name the LLM returns to the Python function to run
TOOL_FUNCTIONS = {
    "list_recent_orders": list_recent_orders,
    "get_order_details": get_order_details,
    "get_shipment_status": get_shipment_status,
}


def run_tool(name: str, arguments_json: str, customer_id: str) -> str:
    """Execute a tool by name with the LLM's JSON arguments, injecting the session's customer_id; returns a JSON string."""
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return json.dumps({"error": f"Unknown tool {name}"})
    try:
        args = json.loads(arguments_json or "{}")
        args.pop("customer_id", None)  # never trust a customer_id supplied by the LLM
        result = func(customer_id=customer_id, **args)
    except Exception as exc:  # bad arguments from the LLM are reported back to it, not crashed on
        result = {"error": f"Tool call failed: {exc}"}
    return json.dumps(result)
