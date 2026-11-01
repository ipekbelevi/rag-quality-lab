#!/usr/bin/env bash
# The LLM quality gate: the exact steps CI runs on every PR. Run it locally the same way:
#   ./scripts/ci_eval.sh            (label "ci", agent cases run once)
#   REPEATS=3 ./scripts/ci_eval.sh  (nightly-style: agent and safety cases 3 times)
#
# pytest shows WHICH items failed and why (diagnostics, never breaks the build on its own:
# an LLM judge is noisy per item). gate.py compares the MEAN scores with the gate
# thresholds in evals/thresholds.py and is what breaks the build.
# Cost per run: about $0.40 (judge gpt-4.1-mini, chatbot claude-haiku-5-5).
set -uo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-.venv/bin/python}"
LABEL="${LABEL:-ci}"
REPEATS="${REPEATS:-1}"

# Production settings: test what users actually get
export PROMPT_VARIANT="${PROMPT_VARIANT:-hardened}"
export GUARDRAIL="${GUARDRAIL:-on}"
export TRACE_TAGS="${TRACE_TAGS:-ci}"

set -e
echo "::group::Build vector index"
"$PY" -m app.ingest
echo "::endgroup::"

echo "::group::Run chatbot on golden set, agent cases and safety cases"
"$PY" -m evals.generate_answers --label "$LABEL"
"$PY" -m evals.generate_agent_runs --label "$LABEL" --repeats "$REPEATS"
"$PY" -m evals.generate_agent_runs --label "$LABEL" --repeats "$REPEATS" --cases data/safety/safety_cases.json --prefix safety_runs
echo "::endgroup::"
set +e

echo "::group::Score with DeepEval (diagnostics)"
ANSWERS_FILE="results/answers_$LABEL.json" \
AGENT_RUNS_FILE="results/agent_runs_$LABEL.json" \
SAFETY_RUNS_FILE="results/safety_runs_$LABEL.json" \
  "$PY" -m pytest evals/ -q -p no:warnings --tb=line -o cache_dir=.pytest_cache
echo "::endgroup::"

status=0
for suite in rag agent safety; do
  "$PY" -m evals.gate --label "$LABEL" --suite "$suite" || status=1
done
exit $status
