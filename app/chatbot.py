"""The chatbot: retrieve context, ask Claude, run tools if Claude asks for them.

Usage:
    .venv/bin/python -m app.chatbot "What is the return window?"
    .venv/bin/python -m app.chatbot            # interactive mode

answer() returns everything a test needs (answer, retrieved chunks, tool calls,
tokens, latency, trace id), not just the text. That is what makes the app testable.
Every call is also one Langfuse trace when tracing is enabled (see app/tracing.py).
"""

import json
import os
import sys
import time

import anthropic

from app import config, guardrails, tracing
from app.prompts import build_user_message, get_system_prompt
from app.retriever import retrieve
from app.tools import TOOLS, execute_tool

MAX_TOOL_ROUNDS = 3  # safety net: never loop forever on tool calls
# Extra trace tags, e.g. TRACE_TAGS=eval,baseline to find eval runs in Langfuse
TRACE_TAGS = [t for t in os.getenv("TRACE_TAGS", "").split(",") if t]

_client = anthropic.Anthropic()


def answer(question: str) -> dict:
    settings = {"chat_model": config.CHAT_MODEL, "prompt_variant": config.PROMPT_VARIANT,
                "guardrail": config.GUARDRAIL, "chunk_size": config.CHUNK_SIZE, "top_k": config.TOP_K}
    with tracing.trace_attributes(trace_name="belevico-chat", tags=TRACE_TAGS, metadata={k: str(v) for k, v in settings.items()}):
        with tracing.observe("belevico-chat", as_type="agent", input={"question": question}) as root:
            result = _answer(question)
            root.update(output=result["answer"], metadata={
                "blocked": result.get("blocked"),
                "tool_calls": len(result["tool_calls"]),
                "input_tokens": result["input_tokens"],
                "output_tokens": result["output_tokens"],
            })
            result["trace_id"] = tracing.current_trace_id()
    return result


def _answer(question: str) -> dict:
    start = time.perf_counter()

    # Guardrail 1: block known attacks before spending any LLM call on them
    if config.GUARDRAIL:
        with tracing.observe("input-guardrail", as_type="guardrail", input=question) as span:
            reason = guardrails.check_input(question)
            span.update(output={"blocked": reason is not None, "reason": reason},
                        level="WARNING" if reason else "DEFAULT")
        if reason:
            return {"question": question, "answer": guardrails.BLOCKED_MESSAGE, "blocked": reason,
                    "contexts": [], "sources": [], "tool_calls": [],
                    "input_tokens": 0, "output_tokens": 0, "latency_s": round(time.perf_counter() - start, 2)}

    with tracing.observe("retrieval", as_type="retriever", input={"query": question, "top_k": config.TOP_K}) as span:
        contexts = retrieve(question)
        span.update(output=[{"source": c["source"], "score": c["score"], "text": c["text"]} for c in contexts])

    system_prompt = get_system_prompt(config.PROMPT_VARIANT)
    messages = [{"role": "user", "content": build_user_message(question, contexts)}]
    tool_calls, input_tokens, output_tokens = [], 0, 0

    for _ in range(MAX_TOOL_ROUNDS + 1):
        with tracing.observe("claude", as_type="generation", model=config.CHAT_MODEL,
                             model_parameters={"max_tokens": 2048, "effort": "low"},
                             input={"system": system_prompt, "messages": _jsonable(messages)}) as gen:
            response = _client.messages.create(
                model=config.CHAT_MODEL,
                max_tokens=2048,
                system=system_prompt,
                tools=TOOLS,
                messages=messages,
                output_config={"effort": "low"},  # support chat: low effort is enough and cheaper
            )
            usage = response.usage
            gen.update(
                output=[_block_dict(b) for b in response.content],
                usage_details={"input": usage.input_tokens, "output": usage.output_tokens},
                cost_details=tracing.cost(config.CHAT_MODEL, usage.input_tokens, usage.output_tokens),
                metadata={"stop_reason": response.stop_reason},
            )
        input_tokens += usage.input_tokens
        output_tokens += usage.output_tokens

        if response.stop_reason != "tool_use":
            break

        # Claude asked for one or more tools: run them and send all results back in one message
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            with tracing.observe(f"tool:{block.name}", as_type="tool", input=block.input) as span:
                executed = sum(1 for c in tool_calls if not c.get("blocked"))
                if config.GUARDRAIL and executed >= guardrails.MAX_ORDER_LOOKUPS:
                    # Guardrail 2: hard limit on lookups per message (stops enumeration)
                    output = f'{{"error": "Lookup limit reached: at most {guardrails.MAX_ORDER_LOOKUPS} orders per message."}}'
                    tool_calls.append({"name": block.name, "input": block.input, "output": output, "blocked": True})
                    is_error = True
                else:
                    # Guardrail 3 (inside execute_tool): strip instruction-like text from tool results
                    output, is_error = execute_tool(block.name, block.input, sanitize=config.GUARDRAIL)
                    tool_calls.append({"name": block.name, "input": block.input, "output": output})
                span.update(output=json.loads(output), level="WARNING" if is_error else "DEFAULT")
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


def _block_dict(block) -> dict:
    """SDK content block -> plain dict for the trace, without the long encrypted thinking signature."""
    data = block.model_dump(exclude_none=True) if hasattr(block, "model_dump") else dict(block)
    data.pop("signature", None)
    return data


def _jsonable(messages: list[dict]) -> list[dict]:
    """Messages -> plain dicts, so the trace shows exactly what was sent."""
    return [
        {"role": m["role"], "content": m["content"] if isinstance(m["content"], str)
         else [_block_dict(b) for b in m["content"]]}
        for m in messages
    ]


def _print_result(result: dict) -> None:
    print(f"\nAnswer: {result['answer']}\n")
    print("Retrieved:", ", ".join(f"{src} ({score})" for src, score in result["sources"]))
    for call in result["tool_calls"]:
        print(f"Tool call: {call['name']}({call['input']}) -> {call['output']}")
    print(f"Tokens: in={result['input_tokens']} out={result['output_tokens']} | {result['latency_s']}s")
    if result.get("trace_id"):
        print(f"Trace: {tracing.trace_url(result['trace_id'])}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        _print_result(answer(" ".join(sys.argv[1:])))
    else:
        print("Belevico assistant. Empty line to quit.")
        while question := input("\nYou: ").strip():
            _print_result(answer(question))
