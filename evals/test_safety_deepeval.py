"""Safety tests: bias, toxicity and security regressions found by the red team.

Run (scores saved runs, does not call the chatbot):
    .venv/bin/pytest evals/test_safety_deepeval.py
    SAFETY_RUNS_FILE=results/safety_runs_defended.json .venv/bin/pytest evals/test_safety_deepeval.py

- bias      -> DeepEval BiasMetric (share of unbiased opinions, higher = better)
- toxicity  -> DeepEval ToxicityMetric (share of non-toxic opinions, higher = better)
- security  -> deterministic checks (tool call limit, forbidden text) + a GEval criterion
"""

import json

import pytest
from deepeval.metrics import BiasMetric, GEval, ToxicityMetric
from deepeval.test_case import LLMTestCase, SingleTurnParams, ToolCall

from app import config
from evals import thresholds as T
from evals.conftest import PROJECT_ROOT, SAFETY_RUNS_FILE
from evals.custom_metrics import ForbiddenText, ToolCallLimit
from evals.runner import run_checks

RUNS = json.loads((PROJECT_ROOT / SAFETY_RUNS_FILE).read_text(encoding="utf-8"))["runs"]
JUDGE = config.JUDGE_MODEL


@pytest.mark.parametrize("run", RUNS, ids=[f"{r['id']}-rep{r['rep']}" for r in RUNS])
def test_safety_case(run):
    test_case = LLMTestCase(
        input=run["input"],
        actual_output=run["answer"],
        # Only lookups that actually ran count; calls stopped by the guardrail are not data access
        tools_called=[ToolCall(name=c["name"], input_parameters=c["input"]) for c in run["tool_calls"] if not c.get("blocked")],
    )
    if run["type"] == "bias":
        checks = [(BiasMetric(threshold=T.BIAS, model=JUDGE), test_case)]
    elif run["type"] == "toxicity":
        checks = [(ToxicityMetric(threshold=T.TOXICITY, model=JUDGE), test_case)]
    else:
        checks = [(GEval(
            name="Security Policy",
            criteria=run["criteria"],
            evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
            threshold=T.SECURITY_POLICY,
            model=JUDGE,
        ), test_case)]
        if "max_tool_calls" in run:
            checks.append((ToolCallLimit(run["max_tool_calls"]), test_case))
        if "forbidden" in run:
            checks.append((ForbiddenText(run["forbidden"]), test_case))
    run_checks(run, checks, suite="safety")
