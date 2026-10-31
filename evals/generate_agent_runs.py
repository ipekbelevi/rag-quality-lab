"""Run every agent case several times and save what the agent did.

Run:
    .venv/bin/python -m evals.generate_agent_runs --label baseline --repeats 3

Writes results/agent_runs_<label>.json. Repeats matter: the agent itself is
non-deterministic, so one green run does not prove it calls the right tool every time.
"""

import argparse
import json
from datetime import datetime

from app import config
from app.chatbot import answer

CASES_PATH = config.PROJECT_ROOT / "data" / "agent" / "agent_cases.json"
RESULTS_DIR = config.PROJECT_ROOT / "results"


def generate(label: str, repeats: int) -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    runs = []
    for case in cases:
        for rep in range(1, repeats + 1):
            result = answer(case["input"])
            runs.append({
                **case,
                "rep": rep,
                "answer": result["answer"],
                "tool_calls": result["tool_calls"],
                "latency_s": result["latency_s"],
            })
            called = [f"{c['name']}({c['input'].get('order_id')})" for c in result["tool_calls"]] or ["no tool"]
            print(f"{case['id']} rep{rep}: {', '.join(called)}")

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"agent_runs_{label}.json"
    out_path.write_text(json.dumps({
        "label": label,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "settings": {"chat_model": config.CHAT_MODEL, "prompt_variant": config.PROMPT_VARIANT, "repeats": repeats},
        "runs": runs,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {len(runs)} runs to {out_path.relative_to(config.PROJECT_ROOT)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    generate(args.label, args.repeats)
