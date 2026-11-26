"""All LLM prompts live here so they are easy to find and tweak."""

# System prompt for the support agent
SYSTEM_PROMPT = (
    "You are a friendly e-commerce customer support assistant. "
    "You can look up a customer's order details and the shipment status of an order using the tools provided. "
    "Only answer using tool results; never invent order data. "
    "If the customer has not given an order id, ask for it."
)

# Prompt used to fold older messages into a rolling summary (used from step 7)
SUMMARY_PROMPT = (
    "Summarize the conversation below for a customer support agent. "
    "Keep order ids, customer issues, and decisions made. Be concise (max 120 words).\n\n"
    "Existing summary:\n{summary}\n\nNew messages:\n{messages}"
)

# Prompt used to generate a short sidebar title (used from step 7)
TITLE_PROMPT = (
    "Write a title of at most 5 words for a support chat that starts with this message. "
    "Reply with the title only.\n\nMessage: {message}"
)
