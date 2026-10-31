"""pytest setup for the eval suite: telemetry off, scores saved and summarized at the end.

Which saved run to score is chosen with env vars:
    ANSWERS_FILE      (RAG tests,    default results/answers_baseline.json)
    AGENT_RUNS_FILE   (agent tests,  default results/agent_runs_baseline.json)
    SAFETY_RUNS_FILE  (safety tests, default results/safety_runs_baseline.json)
"""

import os

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

from pathlib import Path  # noqa: E402

from evals import score_log  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANSWERS_FILE = os.getenv("ANSWERS_FILE", "results/answers_baseline.json")
AGENT_RUNS_FILE = os.getenv("AGENT_RUNS_FILE", "results/agent_runs_baseline.json")
SAFETY_RUNS_FILE = os.getenv("SAFETY_RUNS_FILE", "results/safety_runs_baseline.json")

# suite -> (output file prefix, source file the scores belong to, source file prefix)
SUITES = {
    "rag": ("deepeval", ANSWERS_FILE, "answers_"),
    "agent": ("agent", AGENT_RUNS_FILE, "agent_runs_"),
    "safety": ("safety", SAFETY_RUNS_FILE, "safety_runs_"),
}


def pytest_terminal_summary(terminalreporter):
    for suite, (prefix, source_file, source_prefix) in SUITES.items():
        rows = [r for r in score_log.ROWS if r["suite"] == suite]
        if not rows:
            continue
        label = Path(source_file).stem.removeprefix(source_prefix)
        summary = score_log.write(PROJECT_ROOT / "results" / f"{prefix}_{label}.json", source_file, rows)
        terminalreporter.write_sep("=", f"DeepEval scores ({suite}): {label}")
        for name, s in summary.items():
            terminalreporter.write_line(f"{name:<28} mean={s['mean']:.3f}  passed {s['passed']}/{s['total']}")
