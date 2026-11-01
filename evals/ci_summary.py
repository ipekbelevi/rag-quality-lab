"""Markdown summary of all three gates for one run (used as the GitHub Actions job summary).

Run:
    .venv/bin/python -m evals.ci_summary --label ci >> "$GITHUB_STEP_SUMMARY"
"""

import argparse
import json

from app import config
from evals.gate import SUITES


def summary(label: str) -> str:
    lines = [f"## LLM quality gate: `{label}`", ""]
    all_passed = True
    for suite, (prefix, gate) in SUITES.items():
        path = config.PROJECT_ROOT / "results" / f"{prefix}_{label}.json"
        if not path.exists():
            lines += [f"### {suite}: not run", ""]
            continue
        scores = json.loads(path.read_text(encoding="utf-8"))["summary"]
        lines += [f"### {suite}", "", "| Metric | Mean | Gate | Items passed | |", "|---|---|---|---|---|"]
        for metric, minimum in gate.items():
            s = scores.get(metric)
            ok = s is not None and s["mean"] >= minimum
            all_passed &= ok
            mean = "-" if s is None else f"{s['mean']:.3f}"
            items = "-" if s is None else f"{s['passed']}/{s['total']}"
            lines.append(f"| {metric} | {mean} | ≥{minimum} | {items} | {'✅' if ok else '❌'} |")
        lines.append("")
    lines.append("**Result: " + ("all gates passed ✅**" if all_passed else "gate failed ❌**"))
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    print(summary(parser.parse_args().label))
