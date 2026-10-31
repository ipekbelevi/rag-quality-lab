"""Shared helper for the DeepEval test files: measure metrics, log scores, assert."""

import asyncio

from deepeval.utils import get_or_create_event_loop

from evals import score_log

LOOP = get_or_create_event_loop()  # one event loop for the whole pytest session


def run_checks(record: dict, checks: list[tuple], suite: str) -> None:
    """checks: (metric, test_case) pairs. All metrics run concurrently, then we assert."""
    async def _run():
        await asyncio.gather(*(metric.a_measure(test_case) for metric, test_case in checks))
    LOOP.run_until_complete(_run())

    metrics = [metric for metric, _ in checks]
    score_log.add(record, metrics, suite)
    failures = [
        f"{m.__name__}: {m.score:.2f} (threshold {m.threshold}) -> {m.reason}"
        for m in metrics if not m.is_successful()
    ]
    question = record.get("question") or record.get("input")
    assert not failures, f"{question}\nAnswer: {record['answer']}\n" + "\n".join(failures)
