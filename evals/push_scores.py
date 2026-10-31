"""Attach DeepEval scores to the Langfuse traces of the answers they judged.

Run (after generate_answers with tracing on, and the DeepEval pytest run):
    .venv/bin/python -m evals.push_scores --label traced

Reads results/answers_<label>.json (golden id -> trace_id) and results/deepeval_<label>.json
(scores + judge reasons). In Langfuse, a low-scoring answer then shows the retrieved chunks,
the prompt, the answer and the judge's reason on one screen.
"""

import argparse
import json

from app import config, tracing


def push(label: str) -> None:
    if not tracing.ENABLED:
        raise SystemExit("Tracing is off: set Langfuse keys in .env (and TRACING != off).")
    results = config.PROJECT_ROOT / "results"
    answers = json.loads((results / f"answers_{label}.json").read_text(encoding="utf-8"))["records"]
    trace_ids = {a["id"]: a.get("trace_id") for a in answers}
    rows = json.loads((results / f"deepeval_{label}.json").read_text(encoding="utf-8"))["rows"]

    pushed, missing = 0, 0
    for row in rows:
        trace_id = trace_ids.get(row["id"])
        if not trace_id or row["score"] is None:
            missing += 1
            continue
        tracing.score(trace_id, name=row["metric"], value=row["score"],
                      comment=f"{'PASS' if row['passed'] else 'FAIL'} (threshold {row['threshold']}): {row['reason']}")
        pushed += 1
    tracing.flush()
    print(f"Pushed {pushed} scores to Langfuse ({missing} rows without a trace id).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    push(parser.parse_args().label)
