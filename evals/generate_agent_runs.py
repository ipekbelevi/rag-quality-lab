"""Run every case of a case file several times and save what the agent did.

Run:
    .venv/bin/python -m evals.generate_agent_runs --label baseline --repeats 3
    .venv/bin/python -m evals.generate_agent_runs --label baseline --cases data/safety/safety_cases.json --prefix safety_runs

Writes results/<prefix>_<label>.json (default prefix agent_runs). Repeats matter: the agent
itself is non-deterministic, so one green run does not prove it behaves the same every time.
"""

import argparse
import json
from datetime import datetime

from app import config
from app.chatbot import answer

DEFAULT_CASES = "data/agent/agent_cases.json"
RESULTS_DIR = config.PROJECT_ROOT / "results"


def generate(label: str, repeats: int, cases_file: str = DEFAULT_CASES, prefix: str = "agent_runs") -> None:
    cases = json.loads((config.PROJECT_ROOT / cases_file).read_text(encoding="utf-8"))["cases"]
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
    out_path = RESULTS_DIR / f"{prefix}_{label}.json"
    out_path.write_text(json.dumps({
        "label": label,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "settings": {"chat_model": config.CHAT_MODEL, "prompt_variant": config.PROMPT_VARIANT,
                     "guardrail": config.GUARDRAIL, "repeats": repeats, "cases_file": cases_file},
        "runs": runs,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {len(runs)} runs to {out_path.relative_to(config.PROJECT_ROOT)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--cases", default=DEFAULT_CASES)
    parser.add_argument("--prefix", default="agent_runs")
    args = parser.parse_args()
    generate(args.label, args.repeats, args.cases, args.prefix)
