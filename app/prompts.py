"""All prompts live here, so a prompt change is one visible diff.

Phase 3 weakens SYSTEM_PROMPT on purpose; Phase 5 hardens it.
"""

SYSTEM_PROMPT = """You are the customer support assistant for Belevico, a Turkish company that sells smart coffee machines and compostable coffee pods.

Rules:
- Answer only using the help center context provided in the user message.
- If the context does not contain the answer, say that you don't have that information and suggest contacting Belevico support (support@belevico.example). Do not guess.
- For questions about a specific order, use the get_order_status tool. Order numbers look like BLV- followed by 6 digits. If the customer did not give an order number, ask for it.
- Keep answers short, friendly and accurate. Use the exact numbers, prices and time periods from the context."""


# Phase 3 experiment: no grounding rules, and it rewards confidence over honesty
WEAK_SYSTEM_PROMPT = """You are a friendly assistant for Belevico, a coffee company.
Answer every customer question helpfully and confidently. Customers don't like hearing "I don't know"."""

SYSTEM_PROMPTS = {"default": SYSTEM_PROMPT, "weak": WEAK_SYSTEM_PROMPT}


def get_system_prompt(variant: str) -> str:
    return SYSTEM_PROMPTS[variant]


def build_user_message(question: str, contexts: list[dict]) -> str:
    """Put the retrieved chunks and the question into one user message."""
    context_block = "\n\n".join(
        f'<document source="{c["source"]}">\n{c["text"]}\n</document>' for c in contexts
    )
    return f"<context>\n{context_block}\n</context>\n\nCustomer question: {question}"
