"""The chatbot: retrieve context, ask Claude, run tools if Claude asks for them.

Usage:
    .venv/bin/python -m app.chatbot "What is the return window?"
    .venv/bin/python -m app.chatbot            # interactive mode

answer() returns everything a test needs (answer, retrieved chunks, tool calls,
tokens, latency), not just the text. That is what makes the app testable.
"""

import sys
import time

import anthropic

from app import config
from app.prompts import SYSTEM_PROMPT, build_user_message
from app.retriever import retrieve
from app.tools import TOOLS, execute_tool

MAX_TOOL_ROUNDS = 3  # safety net: never loop forever on tool calls

_client = anthropic.Anthropic()


def answer(question: str) -> dict:
    start = time.perf_counter()
    contexts = retrieve(question)
    messages = [{"role": "user", "content": build_user_message(question, contexts)}]
    tool_calls, input_tokens, output_tokens = [], 0, 0

    for _ in range(MAX_TOOL_ROUNDS + 1):
        response = _client.messages.create(
            model=config.CHAT_MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
            output_config={"effort": "low"},  # support chat: low effort is enough and cheaper
        )
        input_tokens += response.usage.input_tokens
        output_tokens += response.usage.output_tokens

        if response.stop_reason != "tool_use":
            break

        # Claude asked for one or more tools: run them and send all results back in one message
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type == "tool_use":
                output, is_error = execute_tool(block.name, block.input)
                tool_calls.append({"name": block.name, "input": block.input, "output": output})
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": output, "is_error": is_error})
        messages.append({"role": "user", "content": results})

    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if response.stop_reason == "refusal" or not text:
        text = "Sorry, I can't help with that. Please contact support@belevico.example."

    return {
        "question": question,
        "answer": text,
        "contexts": [c["text"] for c in contexts],
        "sources": [(c["source"], c["score"]) for c in contexts],
        "tool_calls": tool_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_s": round(time.perf_counter() - start, 2),
    }


def _print_result(result: dict) -> None:
    print(f"\nAnswer: {result['answer']}\n")
    print("Retrieved:", ", ".join(f"{src} ({score})" for src, score in result["sources"]))
    for call in result["tool_calls"]:
        print(f"Tool call: {call['name']}({call['input']}) -> {call['output']}")
    print(f"Tokens: in={result['input_tokens']} out={result['output_tokens']} | {result['latency_s']}s")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        _print_result(answer(" ".join(sys.argv[1:])))
    else:
        print("Belevico assistant. Empty line to quit.")
        while question := input("\nYou: ").strip():
            _print_result(answer(question))
