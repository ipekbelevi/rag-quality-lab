"""Score the same saved answers with RAGAS and compare with DeepEval.

Run:
    .venv/bin/python -m evals.run_ragas --label baseline

Reads results/answers_<label>.json, writes results/ragas_<label>.json, and prints
a side-by-side table with results/deepeval_<label>.json if it exists.
Same answers + same judge model, so differences come from the metric definitions.
"""

import argparse
import asyncio
import json

from openai import AsyncOpenAI
from ragas.embeddings import OpenAIEmbeddings
from ragas.llms import llm_factory
from ragas.metrics.collections import AnswerRelevancy, ContextPrecisionWithReference, ContextRecall, Faithfulness

from app import config
from app.prompts import get_system_prompt

RESULTS_DIR = config.PROJECT_ROOT / "results"
MAX_CONCURRENCY = 8

# RAGAS metric name -> matching DeepEval metric name
PAIRS = {
    "faithfulness": "Faithfulness",
    "answer_relevancy": "Answer Relevancy",
    "context_precision": "Contextual Precision",
    "context_recall": "Contextual Recall",
}


async def score_record(record: dict, metrics: dict, system_context: str, limit: asyncio.Semaphore) -> dict:
    async with limit:
        q, a, ctx, ref = record["question"], record["answer"], record["contexts"], record["expected_output"]
        results = await asyncio.gather(
            metrics["faithfulness"].ascore(user_input=q, response=a, retrieved_contexts=ctx + [system_context]),
            metrics["answer_relevancy"].ascore(user_input=q, response=a),
            metrics["context_precision"].ascore(user_input=q, reference=ref, retrieved_contexts=ctx),
            metrics["context_recall"].ascore(user_input=q, retrieved_contexts=ctx, reference=ref),
            return_exceptions=True,  # one failed metric call should not kill the run
        )
    scores = {}
    for name, result in zip(metrics, results):
        scores[name] = None if isinstance(result, Exception) else round(float(result.value), 3)
    print(f"{record['id']}: {scores}")
    return {"id": record["id"], "category": record["category"], **scores}


async def run(label: str) -> list[dict]:
    run_data = json.loads((RESULTS_DIR / f"answers_{label}.json").read_text(encoding="utf-8"))
    records = [r for r in run_data["records"] if r["category"] != "out_of_scope"]
    system_context = "Assistant instructions:\n" + get_system_prompt(run_data["settings"]["prompt_variant"])

    client = AsyncOpenAI()
    llm = llm_factory(config.JUDGE_MODEL, client=client)
    embeddings = OpenAIEmbeddings(client=client, model=config.EMBEDDING_MODEL)
    metrics = {
        "faithfulness": Faithfulness(llm=llm),
        "answer_relevancy": AnswerRelevancy(llm=llm, embeddings=embeddings),
        "context_precision": ContextPrecisionWithReference(llm=llm),
        "context_recall": ContextRecall(llm=llm),
    }
    limit = asyncio.Semaphore(MAX_CONCURRENCY)
    return await asyncio.gather(*(score_record(r, metrics, system_context, limit) for r in records))


def mean(values: list) -> float:
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 3) if values else float("nan")


def compare(label: str, rows: list[dict]) -> None:
    deepeval_path = RESULTS_DIR / f"deepeval_{label}.json"
    if not deepeval_path.exists():
        return
    de_rows = json.loads(deepeval_path.read_text(encoding="utf-8"))["rows"]
    de_scores = {(r["id"], r["metric"]): r["score"] for r in de_rows}

    print(f"\n{'Metric':<20}{'RAGAS':>8}{'DeepEval':>10}   items differing by > 0.3")
    for ragas_name, de_name in PAIRS.items():
        ragas_mean = mean([r[ragas_name] for r in rows])
        de_mean = mean([de_scores.get((r["id"], de_name)) for r in rows])
        diffs = [
            f"{r['id']}({r[ragas_name]}/{de_scores[(r['id'], de_name)]})" for r in rows
            if r[ragas_name] is not None and de_scores.get((r["id"], de_name)) is not None
            and abs(r[ragas_name] - de_scores[(r["id"], de_name)]) > 0.3
        ]
        print(f"{ragas_name:<20}{ragas_mean:>8.3f}{de_mean:>10.3f}   {', '.join(diffs) or '-'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    label = parser.parse_args().label
    rows = asyncio.run(run(label))
    summary = {name: mean([r[name] for r in rows]) for name in PAIRS}
    (RESULTS_DIR / f"ragas_{label}.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    failed = sum(1 for r in rows for name in PAIRS if r[name] is None)
    print(f"\nWrote results/ragas_{label}.json ({failed} metric calls failed)")
    compare(label, rows)
