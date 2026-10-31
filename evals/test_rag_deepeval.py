"""DeepEval RAG tests, pytest style: one test per golden item.

Run (scores saved answers, does not call the chatbot):
    .venv/bin/pytest evals/test_rag_deepeval.py
    ANSWERS_FILE=results/answers_weak_prompt.json .venv/bin/pytest evals/test_rag_deepeval.py

In-scope items (factual, multi_hop, trap) get 5 RAG metrics.
Out-of-scope items get a GEval "refusal" metric: there is no right context to recall,
so the only correct behaviour is to say "I don't know" without inventing anything.
"""

import json

import pytest
from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    FaithfulnessMetric,
    GEval,
    HallucinationMetric,
)
from deepeval.test_case import LLMTestCase, SingleTurnParams

from app import config
from app.prompts import get_system_prompt
from evals import thresholds as T
from evals.conftest import ANSWERS_FILE, PROJECT_ROOT
from evals.runner import run_checks

RUN = json.loads((PROJECT_ROOT / ANSWERS_FILE).read_text(encoding="utf-8"))
RECORDS = RUN["records"]
IN_SCOPE = [r for r in RECORDS if r["category"] != "out_of_scope"]
OUT_OF_SCOPE = [r for r in RECORDS if r["category"] == "out_of_scope"]
JUDGE = config.JUDGE_MODEL
# The bot may also rely on facts we gave it in the system prompt (support email,
# "I can check orders"). Faithfulness must see that source too, or it flags them as invented.
SYSTEM_PROMPT_CONTEXT = "Assistant instructions:\n" + get_system_prompt(RUN["settings"]["prompt_variant"])

REFUSAL_CRITERIA = (
    "The question is about something the Belevico help center does not cover. "
    "The actual output must clearly say that this information is not available, "
    "must NOT invent any policy, price, product, program or other details, "
    "and may point the customer to Belevico support."
)


def load_docs(names: list[str]) -> list[str]:
    """Full text of the source documents: the ground truth for the hallucination check."""
    return [(config.DOCS_DIR / name).read_text(encoding="utf-8") for name in names]


def check(record: dict, checks: list[tuple]) -> None:
    run_checks(record, checks, suite="rag")


@pytest.mark.parametrize("record", IN_SCOPE, ids=[r["id"] for r in IN_SCOPE])
def test_grounded_answer(record):
    rag_case = LLMTestCase(
        input=record["question"],
        actual_output=record["answer"],
        expected_output=record["expected_output"],
        retrieval_context=record["contexts"],
        context=load_docs(record["source_docs"]),
    )
    faithfulness_case = LLMTestCase(
        input=record["question"],
        actual_output=record["answer"],
        retrieval_context=record["contexts"] + [SYSTEM_PROMPT_CONTEXT],
    )
    check(record, [
        # penalize_ambiguous_claims: a claim that is merely "not in the sources" also fails.
        # Without it, an invented gift card program would pass because it contradicts nothing.
        (FaithfulnessMetric(threshold=T.FAITHFULNESS, model=JUDGE, penalize_ambiguous_claims=True), faithfulness_case),
        (AnswerRelevancyMetric(threshold=T.ANSWER_RELEVANCY, model=JUDGE), rag_case),
        (ContextualPrecisionMetric(threshold=T.CONTEXTUAL_PRECISION, model=JUDGE), rag_case),
        (ContextualRecallMetric(threshold=T.CONTEXTUAL_RECALL, model=JUDGE), rag_case),
        (HallucinationMetric(threshold=T.HALLUCINATION, model=JUDGE), rag_case),
    ])


@pytest.mark.parametrize("record", OUT_OF_SCOPE, ids=[r["id"] for r in OUT_OF_SCOPE])
def test_out_of_scope_refusal(record):
    test_case = LLMTestCase(input=record["question"], actual_output=record["answer"])
    refusal = GEval(
        name="Refusal",
        criteria=REFUSAL_CRITERIA,
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        threshold=T.REFUSAL,
        model=JUDGE,
    )
    check(record, [(refusal, test_case)])
