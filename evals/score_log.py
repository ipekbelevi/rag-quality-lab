"""Collects metric scores during a pytest run and writes them to results/.

Tests call add(); conftest.py calls write() per suite ("rag", "agent") when the session ends.
The JSON output feeds the gate, the DeepEval vs RAGAS comparison and the README table.
"""

import json
from collections import defaultdict
from pathlib import Path

ROWS: list[dict] = []


def add(record: dict, metrics: list, suite: str) -> None:
    for metric in metrics:
        ROWS.append({
            "suite": suite,
            "id": record["id"],
            "rep": record.get("rep"),
            "category": record.get("category") or record.get("type"),
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


def write(path: Path, source_file: str, rows: list[dict]) -> dict:
    summary = summarize(rows)
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(
        {"source_file": source_file, "summary": summary, "rows": rows}, ensure_ascii=False, indent=2,
    ), encoding="utf-8")
    return summary
