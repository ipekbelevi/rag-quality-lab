"""Apply the human review decisions to the draft and write the approved golden set.

Run:
    .venv/bin/python scripts/apply_golden_review.py

Input:  data/golden/golden_draft.json  (LLM-generated, unreviewed)
Output: data/golden/golden_v1.json     (reviewed, every item approved)

Every change is recorded here with a reason, so the history of the
test oracle stays auditable in git.
"""

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from scripts.generate_golden import validate

DRAFT_PATH = config.GOLDEN_DIR / "golden_draft.json"
OUTPUT_PATH = config.GOLDEN_DIR / "golden_v1.json"
FINAL_COUNTS = {"factual": 15, "multi_hop": 4, "out_of_scope": 5, "trap": 6}

# Field updates on existing items: id -> (changes, reason)
FIXES = {
    "G17": ({
        "question": "My Forte shows error E-42. Will the warranty cover it, and do I get a machine while it's being repaired?",
        "expected_output": "E-42 is a pump failure: stop using the machine and contact support; it is usually covered by warranty. "
                           "Warranty repairs take about 10 business days, and Belevico Forte owners get a free loaner machine during the repair.",
        "source_docs": ["12-troubleshooting-error-codes.md", "07-warranty.md"],
        "rationale": "Combines an error code with warranty repair rules that only apply to Forte.",
    }, "Replaced: original answer came from a single document (fake multi_hop)."),
    "G19": ({
        "question": "I'm a Pod Club member and just bought a Belevico Forte. How many Bean Points do I get for it?",
        "expected_output": "Belevico Forte costs ₺12,990. Pod Club members earn 2 Bean Points per ₺10, so you earn 2,598 Bean Points.",
        "source_docs": ["02-products.md", "09-bean-points-loyalty.md"],
        "rationale": "Needs a price from one document and a points rule from another, plus a calculation.",
    }, "Replaced: fake multi_hop, second source doc was unrelated."),
    "G21": ({
        "category": "factual",
        "expected_output": "No. Belevico only delivers within Turkey and does not ship internationally.",
        "source_docs": ["01-about-belevico.md", "04-shipping-and-delivery.md"],
        "rationale": "Checks that the bot answers a delivery-area question from the docs.",
    }, "Recategorized out_of_scope -> factual: the docs do answer this."),
    "G22": ({
        "expected_output": "The help center has no information about coffee mugs. Besides machines and pods, the only accessory mentioned "
                           "is the Belevico DescalePro descaler (₺159). For other products, contact support@belevico.example.",
    }, "Reference said 'no accessory info', but DescalePro is documented."),
    "G27": ({
        "expected_output": "No. Belevico machines only accept Belevico Pods; third-party pods are not supported and trigger error E-23. "
                           "Damage caused by third-party pods is not covered by the warranty.",
        "source_docs": ["02-products.md", "12-troubleshooting-error-codes.md", "07-warranty.md"],
    }, "Removed unsupported claim 'may damage the machine'; added the warranty fact the docs do state."),
    "G29": ({
        "expected_output": "The help center does not set a limit on skipping deliveries in a row. You can skip a single delivery up to "
                           "3 days before the billing date, or pause the subscription for up to 3 months at a time.",
    }, "Reference hallucinated a rule ('single delivery only'); docs set no limit on consecutive skips."),
}

REMOVE = {
    "G15": "Valid, removed to keep the set at 30; doc 01 is covered by G01 and G21.",
    "G16": "Valid, removed to keep the set at 30; doc 02 is covered by G02, G19 and others.",
}

ADD = [
    ({"id": "G30", "category": "out_of_scope", "question": "do u have a student discount?",
      "expected_output": "There is no information about a student discount in the help center. Please contact support@belevico.example.",
      "source_docs": [], "rationale": "Plausible pricing question with no answer in the docs (casual phrasing)."},
     "Added: draft had only 4 of 5 out_of_scope items."),
    ({"id": "G31", "category": "out_of_scope", "question": "Are you hiring? I'd love to work as a barista in your showroom.",
      "expected_output": "There is no information about jobs or hiring in the help center. Please contact support@belevico.example.",
      "source_docs": [], "rationale": "Off-topic but realistic request; the bot must not invent a careers page."},
     "Added: replaces G21 after it moved to factual."),
    ({"id": "G32", "category": "trap", "question": "I have 30 days to return my Aria, right?",
      "expected_output": "No. The return window is 21 days from delivery, and the machine must be returned in its original packaging "
                         "with all accessories. (30 days is the deadline for registering a machine for Belevico Care+.)",
      "source_docs": ["06-returns-and-refunds.md", "07-warranty.md"],
      "rationale": "Number-confusion trap: 21-day returns vs 30-day Care+ registration."},
     "Added: draft had no number-confusion trap although the prompt asked for one."),
]

APPROVAL_NOTE = "Approved as generated."


def apply_review() -> list[dict]:
    draft = json.loads(DRAFT_PATH.read_text(encoding="utf-8"))["items"]
    items = []
    for item in draft:
        if item["id"] in REMOVE:
            continue
        changes, note = FIXES.get(item["id"], ({}, APPROVAL_NOTE))
        items.append({**item, **changes, "approved": True, "review_note": note})
    for new_item, note in ADD:
        items.append({**new_item, "approved": True, "review_note": note})
    return items


if __name__ == "__main__":
    items = apply_review()
    problems = validate(items, FINAL_COUNTS)
    if problems:
        print("Validation failed:")
        for problem in problems:
            print("  -", problem)
        sys.exit(1)
    OUTPUT_PATH.write_text(json.dumps(
        {"version": "v1", "reviewed_on": str(date.today()), "reviewed_by": "human (project owner)",
         "generator_model": config.JUDGE_MODEL, "items": items},
        ensure_ascii=False, indent=2,
    ), encoding="utf-8")
    edited = sum(1 for i in items if i["review_note"] != APPROVAL_NOTE)
    print(f"Wrote {len(items)} approved items to {OUTPUT_PATH.relative_to(config.PROJECT_ROOT)}")
    print("Counts:", dict(Counter(i["category"] for i in items)))
    print(f"Unchanged: {len(items) - edited} | edited or added: {edited} | removed: {len(REMOVE)}")
