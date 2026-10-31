"""pytest setup for the eval suite: telemetry off, scores saved and summarized at the end."""

import os

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

from pathlib import Path  # noqa: E402

from evals import score_log  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANSWERS_FILE = os.getenv("ANSWERS_FILE", "results/answers_baseline.json")
LABEL = Path(ANSWERS_FILE).stem.removeprefix("answers_")


def pytest_terminal_summary(terminalreporter):
    if not score_log.ROWS:
        return
    summary = score_log.write(PROJECT_ROOT / "results" / f"deepeval_{LABEL}.json", ANSWERS_FILE)
    terminalreporter.write_sep("=", f"DeepEval scores: {LABEL}")
    for name, s in summary.items():
        terminalreporter.write_line(f"{name:<28} mean={s['mean']:.3f}  passed {s['passed']}/{s['total']}")
