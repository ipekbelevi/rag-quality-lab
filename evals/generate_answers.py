"""Run the chatbot on every golden question and save the answers.

Run:
    .venv/bin/python -m evals.generate_answers --label baseline

Writes results/answers_<label>.json. Scoring (DeepEval, RAGAS) reads this file,
so both tools judge exactly the same answers and re-scoring costs no chatbot calls.
The run settings are saved too, so every result file says how it was produced.
"""

import argparse
import json
from datetime import datetime

from app import config
from app.chatbot import answer

GOLDEN_PATH = config.GOLDEN_DIR / "golden_v1.json"
RESULTS_DIR = config.PROJECT_ROOT / "results"


def generate(label: str) -> None:
    items = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))["items"]
    records, in_tokens, out_tokens = [], 0, 0
    for item in items:
        result = answer(item["question"])
        in_tokens += result["input_tokens"]
        out_tokens += result["output_tokens"]
        records.append({
            "id": item["id"],
            "category": item["category"],
            "question": item["question"],
            "expected_output": item["expected_output"],
            "source_docs": item["source_docs"],
            "answer": result["answer"],
            "contexts": result["contexts"],
            "retrieved_sources": result["sources"],
            "tool_calls": result["tool_calls"],
            "latency_s": result["latency_s"],
            "trace_id": result.get("trace_id"),  # Phase 6: lets us attach eval scores to the trace
        })
        print(f"{item['id']} ({result['latency_s']}s) {result['answer'][:90]!r}")

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"answers_{label}.json"
    out_path.write_text(json.dumps({
        "label": label,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "settings": {
            "chat_model": config.CHAT_MODEL, "chunk_size": config.CHUNK_SIZE, "top_k": config.TOP_K,
            "prompt_variant": config.PROMPT_VARIANT, "excluded_docs": config.EXCLUDE_DOCS,
            "golden_set": GOLDEN_PATH.name,
        },
        "usage": {"input_tokens": in_tokens, "output_tokens": out_tokens},
        "records": records,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {len(records)} answers to {out_path.relative_to(config.PROJECT_ROOT)}")
    print(f"Chatbot tokens: in={in_tokens} out={out_tokens}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True, help="name for this run, e.g. baseline")
    generate(parser.parse_args().label)
