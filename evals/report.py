"""Print a markdown table of mean DeepEval scores across runs (baseline vs experiments).

Run:
    .venv/bin/python -m evals.report baseline chunk_small missing_doc weak_prompt

Cells below the gate threshold are marked with ❌.
"""

import json
import sys

from app import config
from evals.thresholds import GATE


def report(labels: list[str]) -> str:
    summaries = {
        label: json.loads((config.PROJECT_ROOT / "results" / f"deepeval_{label}.json").read_text(encoding="utf-8"))["summary"]
        for label in labels
    }
    lines = ["| Metric (gate) | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
    for metric, minimum in GATE.items():
        cells = []
        for label in labels:
            s = summaries[label].get(metric)
            cells.append("-" if s is None else f"{s['mean']:.2f}" + (" ❌" if s["mean"] < minimum else ""))
        lines.append(f"| {metric} (≥{minimum}) | " + " | ".join(cells) + " |")
    verdicts = ["PASS" if all(summaries[l].get(m, {"mean": 0})["mean"] >= t for m, t in GATE.items()) else "**FAIL**"
                for l in labels]
    lines.append("| **Gate** | " + " | ".join(verdicts) + " |")
    return "\n".join(lines)


if __name__ == "__main__":
    print(report(sys.argv[1:] or ["baseline"]))
