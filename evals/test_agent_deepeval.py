"""DeepEval agent tests: right tool, right parameters, task completed.

Run (scores saved agent runs, does not call the chatbot):
    .venv/bin/pytest evals/test_agent_deepeval.py

One test per (case, repetition). Two layers:
- Tool Correctness: deterministic exact match of tool names AND input parameters
  against the hand-written spec. No LLM judge, so the threshold can be 1.0.
- Task Completion: LLM judge checks the answer against the case's task description.
Cases with expected_tools = null accept more than one behaviour: only task completion is checked.
"""

import json

import pytest
from deepeval.metrics import TaskCompletionMetric, ToolCorrectnessMetric
from deepeval.test_case import LLMTestCase, ToolCall, ToolCallParams

from app import config
from evals import thresholds as T
from evals.conftest import AGENT_RUNS_FILE, PROJECT_ROOT
from evals.runner import run_checks

RUNS = json.loads((PROJECT_ROOT / AGENT_RUNS_FILE).read_text(encoding="utf-8"))["runs"]


def to_tool_calls(calls: list[dict]) -> list[ToolCall]:
    """Our format ({name, input} or {name, input_parameters}) -> DeepEval ToolCall objects."""
    return [ToolCall(name=c["name"], input_parameters=c.get("input") or c.get("input_parameters")) for c in calls]


@pytest.mark.parametrize("run", RUNS, ids=[f"{r['id']}-rep{r['rep']}" for r in RUNS])
def test_agent_case(run):
    test_case = LLMTestCase(
        input=run["input"],
        actual_output=run["answer"],
        tools_called=to_tool_calls(run["tool_calls"]),
        expected_tools=to_tool_calls(run["expected_tools"] or []),
    )
    checks = [(TaskCompletionMetric(threshold=T.TASK_COMPLETION, task=run["task"], model=config.JUDGE_MODEL), test_case)]
    if run["expected_tools"] is not None:
        tool_correctness = ToolCorrectnessMetric(
            threshold=T.TOOL_CORRECTNESS,
            evaluation_params=[ToolCallParams.INPUT_PARAMETERS],  # compare parameters, not only names
            should_exact_match=True,  # no extra and no missing calls
        )
        checks.insert(0, (tool_correctness, test_case))
    run_checks(run, checks, suite="agent")
