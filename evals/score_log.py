"""Collects metric scores during a pytest run and writes them to results/.

Tests call add(); conftest.py calls write() when the session ends.
The JSON output feeds the DeepEval vs RAGAS comparison and the README table.
"""

import json
from collections import defaultdict
from pathlib import Path

ROWS: list[dict] = []


def add(record: dict, metrics: list) -> None:
    for metric in metrics:
        ROWS.append({
            "id": record["id"],
            "category": record["category"],
            "metric": metric.__name__,
            "score": None if metric.score is None else round(metric.score, 3),
            "threshold": metric.threshold,
            "passed": bool(metric.is_successful()),
            "reason": metric.reason,
        })


def summarize(rows: list[dict]) -> dict:
    by_metric = defaultdict(list)
    for row in rows:
        by_metric[row["metric"]].append(row)
    return {
        name: {
            "mean": round(sum(r["score"] or 0 for r in metric_rows) / len(metric_rows), 3),
            "passed": sum(r["passed"] for r in metric_rows),
            "total": len(metric_rows),
        }
        for name, metric_rows in sorted(by_metric.items())
    }


def write(path: Path, answers_file: str) -> dict:
    summary = summarize(ROWS)
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(
        {"answers_file": answers_file, "summary": summary, "rows": ROWS}, ensure_ascii=False, indent=2,
    ), encoding="utf-8")
    return summary
