"""Compare Promptfoo red team runs: defended-attack rate per plugin and per strategy.

Run:
    .venv/bin/python redteam/summarize.py before hardened defended

Reads redteam/output/<label>.json. "Defended" = the grader passed the test (attack failed).
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def load(label: str) -> list[dict]:
    rows = json.loads((OUTPUT_DIR / f"{label}.json").read_text(encoding="utf-8"))["results"]["results"]
    return [{
        "plugin": r["testCase"]["metadata"].get("pluginId"),
        "strategy": r["testCase"]["metadata"].get("strategyId") or "basic",
        "passed": bool(r.get("success")),
        "error": bool(r.get("error")),
        "blocked": "can't help with that request" in (r.get("response") or {}).get("output", ""),
    } for r in rows]


def rate(rows: list[dict]) -> str:
    return f"{sum(r['passed'] for r in rows)}/{len(rows)}"


def table(runs: dict, key: str) -> str:
    groups = sorted({r[key] for rows in runs.values() for r in rows})
    lines = [f"| {key} | " + " | ".join(runs) + " |", "|---|" + "---|" * len(runs)]
    for g in groups:
        lines.append(f"| {g} | " + " | ".join(rate([r for r in rows if r[key] == g]) for rows in runs.values()) + " |")
    lines.append("| **total** | " + " | ".join(rate(rows) for rows in runs.values()) + " |")
    lines.append("| blocked by input filter | " + " | ".join(str(sum(r["blocked"] for r in rows)) for rows in runs.values()) + " |")
    return "\n".join(lines)


if __name__ == "__main__":
    runs = {label: load(label) for label in sys.argv[1:] or ["before"]}
    print(table(runs, "plugin"))
    print()
    print(table(runs, "strategy"))
