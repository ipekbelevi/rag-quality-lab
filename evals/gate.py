"""Quality gate: compare mean DeepEval scores of a run with the gate thresholds.

Run (after the pytest suite has written results/deepeval_<label>.json):
    .venv/bin/python -m evals.gate --label baseline

Exit code 0 = gate passed, 1 = gate failed. CI uses the exit code to break the build.
"""

import argparse
import json
import sys

from app import config
from evals.thresholds import GATE


def check_gate(label: str) -> bool:
    path = config.PROJECT_ROOT / "results" / f"deepeval_{label}.json"
    summary = json.loads(path.read_text(encoding="utf-8"))["summary"]
    passed = True
    print(f"Quality gate: {label}")
    print(f"{'Metric':<24}{'mean':>7}{'gate':>7}  items passed")
    for metric, minimum in GATE.items():
        s = summary.get(metric)
        if s is None:
            print(f"{metric:<24}{'-':>7}{minimum:>7.2f}  MISSING")
            passed = False
            continue
        ok = s["mean"] >= minimum
        passed &= ok
        print(f"{metric:<24}{s['mean']:>7.3f}{minimum:>7.2f}  {s['passed']}/{s['total']}  {'OK' if ok else 'FAIL'}")
    print("GATE PASSED" if passed else "GATE FAILED")
    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    sys.exit(0 if check_gate(parser.parse_args().label) else 1)
