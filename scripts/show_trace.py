"""Print one Langfuse trace as a timeline tree in the terminal.

Run:
    .venv/bin/python scripts/show_trace.py <trace_id>

Shows each step (retrieval, LLM call, tool, guardrail) with its start offset,
duration, tokens, cost and a short view of input/output: the same data as the Langfuse UI.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402,F401  (loads .env)
from langfuse import get_client  # noqa: E402

FIELDS = "basic,io,model,usage,metrics,trace_context"


def short(value, limit: int = 110) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = text.replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "…"


def parse(raw):
    """The v2 API returns input/output as raw strings; decode JSON when possible."""
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return raw


def show(trace_id: str) -> None:
    rows = get_client().api.observations.get_many(trace_id=trace_id, fields=FIELDS, limit=100).data
    obs = [r if isinstance(r, dict) else r.dict() for r in rows]
    if not obs:
        print("No observations yet (ingestion can take a few seconds).")
        return
    obs.sort(key=lambda o: o["startTime"])
    t0 = obs[0]["startTime"]
    children = {}
    for o in obs:
        children.setdefault(o.get("parentObservationId"), []).append(o)

    root = children[None][0]
    total_cost = sum(o.get("totalCost") or 0 for o in obs)
    total_in = sum((o.get("usageDetails") or {}).get("input", 0) for o in obs)
    total_out = sum((o.get("usageDetails") or {}).get("output", 0) for o in obs)
    print(f"Trace {trace_id}  tags={root.get('tags')}")
    print(f"Total: {root.get('latency')}s | tokens in={total_in} out={total_out} | cost ${total_cost:.6f}\n")

    def walk(node, depth):
        offset = (node["startTime"] - t0).total_seconds()
        line = f"{'  ' * depth}+{offset:5.2f}s  {node['latency'] or 0:5.2f}s  {node['type']:<10} {node['name']}"
        if node["type"] == "GENERATION":
            u = node.get("usageDetails") or {}
            line += f"  [{node.get('model')}, in={u.get('input')} out={u.get('output')}, ${node.get('totalCost') or 0:.6f}]"
        if node.get("level") not in (None, "DEFAULT"):
            line += f"  level={node['level']}"
        print(line)
        pad = "  " * depth + " " * 22
        if node.get("input") is not None and node["type"] != "GENERATION":
            print(f"{pad}in:  {short(parse(node['input']))}")
        if node.get("output") is not None:
            print(f"{pad}out: {short(parse(node['output']))}")
        for child in children.get(node["id"], []):
            walk(child, depth + 1)

    walk(root, 0)


if __name__ == "__main__":
    show(sys.argv[1])
