"""Generate a DRAFT golden dataset from the help center docs with an LLM.

Run:
    .venv/bin/python scripts/generate_golden.py

Writes data/golden/golden_draft.json. Every item starts with approved=false:
nothing enters the eval suite until a human has reviewed it.

The generator is the OpenAI judge model, not the chatbot's model (Claude),
so the system under test does not write its own exam questions.
"""

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openai
from pydantic import BaseModel

from app import config

TARGET_COUNTS = {"factual": 16, "multi_hop": 4, "out_of_scope": 5, "trap": 5}
OUTPUT_PATH = config.GOLDEN_DIR / "golden_draft.json"


class GoldenItem(BaseModel):
    category: Literal["factual", "multi_hop", "out_of_scope", "trap"]
    question: str
    expected_output: str
    source_docs: list[str]
    rationale: str


class GoldenSet(BaseModel):
    items: list[GoldenItem]


GENERATION_PROMPT = """You are a QA engineer building a golden test dataset for a RAG customer support chatbot.
The chatbot answers questions about Belevico using ONLY the help center documents below.

Create exactly {total} test items:
- {factual} "factual": answerable from ONE document. Cover every document at least once.
- {multi_hop} "multi_hop": need facts from TWO documents, or a small calculation (e.g. points earned for a purchase).
- {out_of_scope} "out_of_scope": realistic questions a coffee company customer might ask, but the answer is NOT in any document.
  expected_output: the assistant should say it does not have this information and point to support@belevico.example. source_docs: [].
- {trap} "trap": questions designed to make a model hallucinate. Use false premises (e.g. assuming a policy or feature that does not exist)
  or mix up similar numbers from different documents (e.g. 21 vs 30 days). expected_output must correct the premise using the documents.

Rules:
- Phrase questions like real customers: varied length and tone, some casual, one or two with a small typo.
- expected_output: a short, correct reference answer using ONLY facts from the documents, with exact numbers, prices and time periods.
- source_docs: the file names the answer comes from.
- rationale: one sentence on what this item tests.

DOCUMENTS:
{documents}"""


def load_documents() -> str:
    return "\n\n".join(
        f'<document file="{p.name}">\n{p.read_text(encoding="utf-8")}\n</document>'
        for p in sorted(config.DOCS_DIR.glob("*.md"))
    )


def generate() -> list[dict]:
    prompt = GENERATION_PROMPT.format(total=sum(TARGET_COUNTS.values()), documents=load_documents(), **TARGET_COUNTS)
    response = openai.OpenAI().chat.completions.parse(
        model=config.JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format=GoldenSet,  # structured output: the reply must match the schema
    )
    usage = response.usage
    print(f"Generator: {config.JUDGE_MODEL} | tokens in={usage.prompt_tokens} out={usage.completion_tokens}")

    items = []
    for i, item in enumerate(response.choices[0].message.parsed.items, start=1):
        items.append({"id": f"G{i:02d}", **item.model_dump(), "approved": False, "review_note": ""})
    return items


def validate(items: list[dict], expected_counts: dict = TARGET_COUNTS) -> list[str]:
    """Cheap automatic checks before the human review. Returns a list of problems."""
    problems = []
    known_docs = {p.name for p in config.DOCS_DIR.glob("*.md")}
    counts = Counter(item["category"] for item in items)
    for category, target in expected_counts.items():
        if counts[category] != target:
            problems.append(f"{category}: expected {target}, got {counts[category]}")
    questions = [item["question"].strip().lower() for item in items]
    if len(set(questions)) != len(questions):
        problems.append("duplicate questions found")
    for item in items:
        unknown = set(item["source_docs"]) - known_docs
        if unknown:
            problems.append(f"{item['id']}: unknown source docs {unknown}")
        if item["category"] == "out_of_scope" and item["source_docs"]:
            problems.append(f"{item['id']}: out_of_scope item should have no source docs")
        if item["category"] != "out_of_scope" and not item["source_docs"]:
            problems.append(f"{item['id']}: missing source docs")
    covered = {doc for item in items for doc in item["source_docs"]}
    for doc in sorted(known_docs - covered):
        problems.append(f"document never used: {doc}")
    return problems


if __name__ == "__main__":
    items = generate()
    OUTPUT_PATH.write_text(json.dumps(
        {"version": "draft", "generated_on": str(date.today()), "generator_model": config.JUDGE_MODEL, "items": items},
        ensure_ascii=False, indent=2,
    ), encoding="utf-8")
    print(f"Wrote {len(items)} items to {OUTPUT_PATH.relative_to(config.PROJECT_ROOT)}")
    print("Counts:", dict(Counter(item["category"] for item in items)))
    problems = validate(items)
    print("Automatic checks:", "OK" if not problems else "")
    for problem in problems:
        print("  -", problem)
