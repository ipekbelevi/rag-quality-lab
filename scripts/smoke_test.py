"""Smoke test: one tiny call to each model we depend on.

Run after filling in .env:
    .venv/bin/python scripts/smoke_test.py

Checks that both API keys work and prints tokens + latency per call,
the two numbers every later cost estimate is built from.
Total cost of one run: far below $0.01.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic
import openai

from app import config


def check_chat_model() -> None:
    """System under test: Claude answers a trivial prompt."""
    client = anthropic.Anthropic()
    start = time.perf_counter()
    response = client.messages.create(
        model=config.CHAT_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": "Reply with exactly one word: OK"}],
    )
    elapsed = time.perf_counter() - start
    text = "".join(block.text for block in response.content if block.type == "text")
    print(f"[chat]  {config.CHAT_MODEL}: {text.strip()!r}")
    print(f"        input={response.usage.input_tokens} output={response.usage.output_tokens} tokens, {elapsed:.2f}s")


def check_judge_model() -> None:
    """Evaluator: GPT answers the same trivial prompt."""
    client = openai.OpenAI()
    start = time.perf_counter()
    response = client.chat.completions.create(
        model=config.JUDGE_MODEL,
        messages=[{"role": "user", "content": "Reply with exactly one word: OK"}],
    )
    elapsed = time.perf_counter() - start
    print(f"[judge] {config.JUDGE_MODEL}: {response.choices[0].message.content.strip()!r}")
    print(f"        input={response.usage.prompt_tokens} output={response.usage.completion_tokens} tokens, {elapsed:.2f}s")


def check_embedding_model() -> None:
    """Embeddings: turn a sentence into a vector (used by retrieval and some RAGAS metrics)."""
    client = openai.OpenAI()
    start = time.perf_counter()
    response = client.embeddings.create(model=config.EMBEDDING_MODEL, input="Where is my order?")
    elapsed = time.perf_counter() - start
    vector = response.data[0].embedding
    print(f"[embed] {config.EMBEDDING_MODEL}: vector of {len(vector)} dims, first 3 = {[round(v, 4) for v in vector[:3]]}")
    print(f"        input={response.usage.prompt_tokens} tokens, {elapsed:.2f}s")


def check_keys_present() -> bool:
    """Fail fast with a clear message instead of a cryptic SDK TypeError."""
    missing = [k for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY") if not os.getenv(k)]
    for key in missing:
        print(f"[FAIL]  {key} is empty. Fill it in {config.PROJECT_ROOT / '.env'}")
    return not missing


if __name__ == "__main__":
    if not check_keys_present():
        sys.exit(1)
    failed = False
    for check in (check_chat_model, check_judge_model, check_embedding_model):
        try:
            check()
        except (anthropic.AuthenticationError, openai.AuthenticationError) as e:
            print(f"[FAIL]  {check.__name__}: API key rejected. Check .env. ({e.__class__.__name__})")
            failed = True
        except (anthropic.NotFoundError, openai.NotFoundError) as e:
            print(f"[FAIL]  {check.__name__}: model name not found. Check the model in .env. ({e})")
            failed = True
        except (anthropic.APIError, openai.APIError) as e:
            print(f"[FAIL]  {check.__name__}: {e.__class__.__name__}: {e}")
            failed = True
    sys.exit(1 if failed else 0)
