"""Promptfoo custom provider: lets Promptfoo send attack prompts to our chatbot.

Promptfoo calls call_api() once per attack. Which defenses are active is decided by
env vars set when promptfoo is started (PROMPT_VARIANT, GUARDRAIL), so the same
attack set can be replayed against the bot before and after a defense.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.chatbot import answer  # noqa: E402


def call_api(prompt, options, context):
    try:
        result = answer(prompt)
    except Exception as e:  # report errors as errors, not as model output
        # Details stay in the local log; the caller only gets the error class (no URLs, ids or payloads)
        print(f"provider error: {type(e).__name__}: {e}", file=sys.stderr)
        return {"error": f"internal error ({type(e).__name__})"}
    return {
        "output": result["answer"],
        "metadata": {
            "tool_calls": result["tool_calls"],
            "retrieved_sources": [src for src, _ in result["sources"]],
        },
        "tokenUsage": {
            "prompt": result["input_tokens"],
            "completion": result["output_tokens"],
            "total": result["input_tokens"] + result["output_tokens"],
        },
    }
