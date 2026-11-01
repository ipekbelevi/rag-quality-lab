# Token and cost report

Scope: **API usage only** (chatbot, judge, embeddings, red-team grader). Developer time, laptop time and the Langfuse free tier are not included.

Two kinds of numbers appear below:
- **Measured**: read from files in `results/` and `redteam/output/` (token counts returned by the APIs).
- **Estimated**: runs whose tokens were not saved (agent/safety runs, DeepEval and RAGAS judge calls, runs that were later overwritten). Estimates are marked ≈ and the assumptions are listed.

The exact invoice is on the provider dashboards (OpenAI → Usage, Anthropic → Console → Usage). Everything here should land within about ±30% of those numbers.

## Prices used

| Model | Role | Input $/1M tokens | Output $/1M tokens |
|---|---|---|---|
| claude-haiku-5-5 | the chatbot (system under test) | 0.10 | 0.50 |
| gpt-4.1-mini | judge, test-data generator, red-team attacker and grader | 0.40 (assumed) | 1.60 (assumed) |
| text-embedding-3-small | retrieval + RAGAS answer relevancy | 0.02 (assumed) | – |

Check the OpenAI prices on the pricing page before reusing this table; they change.

## 1. What the project spent

### Chatbot (Claude Haiku 5.5)

| Workload | Calls | Input tokens | Output tokens | Cost | Source |
|---|---|---|---|---|---|
| Golden-set answer runs (7 files × 30 questions) | 210 | 337,231 | 35,874 | $0.052 | measured |
| Agent + safety runs (286 runs, 165 tool calls) | ≈430 LLM calls | ≈600,000 | ≈45,000 | ≈$0.08 | estimated (≈2,000 in / 150 out per run, tool runs need 2 calls) |
| Promptfoo red team (4 runs × 112 attacks) | 448 | 814,965 | 82,131 | $0.12 | measured |
| Overwritten runs, demos, smoke tests, CLI checks | ≈100 | ≈150,000 | ≈15,000 | ≈$0.02 | estimated |
| **Chatbot total** | **≈1,200** | **≈1.9M** | **≈0.18M** | **≈$0.28** | |

### Judge and generators (GPT-4.1-mini)

| Workload | LLM calls | Tokens (in / out) | Cost | Source |
|---|---|---|---|---|
| Golden dataset generation (1 structured-output call) | 1 | 4,471 / 2,256 | $0.005 | measured |
| DeepEval RAG metrics: 8 runs × 130 evaluations = 1,040 evaluations (5 metrics with retrieved chunks in the prompt) | ≈2,600 | ≈4.0M / 0.35M | ≈$2.15 | estimated (≈2.5 calls and ≈3,800 input tokens per evaluation) |
| DeepEval agent + safety metrics: 469 LLM-judged evaluations (Task Completion, GEval, Bias, Toxicity; Tool Correctness and the custom checks are free) | ≈900 | ≈1.0M / 0.10M | ≈$0.56 | estimated |
| RAGAS second opinion: 25 answers × 4 metrics | ≈250 | ≈0.35M / 0.04M | ≈$0.20 | estimated |
| Promptfoo attack generation + grading (4 runs) | ≈140 | 154,062 / 12,582 + generation 2,548 / 465 | $0.08 | measured |
| **Judge total** | **≈3,900** | **≈5.5M / 0.5M** | **≈$3.0** | |

### Embeddings (text-embedding-3-small)

5 index builds (≈20k tokens) + ≈1,500 query embeddings (≈30k tokens) + RAGAS (≈10k) ≈ 60,000 tokens ≈ **$0.001**.

### Total

| | Cost | Share |
|---|---|---|
| Chatbot (the thing being tested) | ≈$0.28 | ≈8% |
| Judge + generators (the testing) | ≈$3.0 | ≈92% |
| Embeddings | ≈$0.001 | 0% |
| **Whole project, 8 phases + security re-verification** | **≈$3.3** (range $2.5–4.5) | |

**The main finding: testing an LLM app costs about 10× more than running it.** Every answer is judged by 5 metrics, each metric makes 2–3 judge calls, and each judge call carries the retrieved context. The judge model, not the chatbot model, decides the eval bill.

### Unit costs measured in this project (for the scaling section)

| Unit | Cost | Notes |
|---|---|---|
| One chatbot answer (Haiku, hardened prompt, top-4 chunks) | ≈$0.0003 | ≈1,900 input / 170 output tokens; tool-using answers ≈2× |
| One golden-set item through 5 RAG metrics | ≈$0.0085 | gpt-4.1-mini judge; one 30-item run ≈ $0.25 |
| One agent or safety item through an LLM-judged metric | ≈$0.0012 | Task Completion / GEval / Bias / Toxicity |
| One red-team attack (chatbot + grader) | ≈$0.0005 | Promptfoo, local generation |
| One full CI quality-gate run (30 + 12 + 13 items) | ≈$0.40 | measured ≈ 5–6 min |

## 2. What this costs a company at scale

The formula behind every number: **cost = items × metrics × judge calls per metric × tokens per call × price per token.** The two levers that matter most are the judge model's price and the number of items judged per run.

### Scenario A: PR quality gate with a real golden set

| Golden set | Per run (gpt-4.1-mini judge) | 20 PRs/day, 22 days | Same with a frontier-class judge (≈6× price) |
|---|---|---|---|
| 30 items (this project) | $0.25 | $110 / month | ≈$660 / month |
| 300 items | $2.5 | $1,100 / month | ≈$6,600 / month |
| 1,000 items | $8.5 | $3,700 / month | ≈$22,000 / month |
| 5,000 items | $43 | $19,000 / month | ≈$110,000 / month |

How teams keep this sane:
- **Tiered runs:** a 100–200 item smoke set on every PR, the full set nightly, the 3-repeat reliability set weekly (this repo's workflow already does the PR/weekly split).
- **Cache unchanged answers:** if the prompt, model and index did not change, the answers are identical and do not need re-judging; only re-judge what changed.
- **Deterministic checks first:** tool correctness, forbidden text, schema validation and refusal keywords cost nothing; run them before any judge.
- **Cheap judge for cheap questions:** retrieval metrics (precision/recall) are simple comparisons; use the smallest judge that agrees with human labels on a calibration set.
- **Shorter context in judge prompts:** judge cost scales with `TOP_K × chunk size`; evaluate retrieval on chunk ids where possible, not full text.

### Scenario B: online evaluation of production traffic

Sample live conversations, judge them, attach scores to traces (what Phase 6 set up).

| Traffic | Sample | Judged per day | Monthly judge cost (gpt-4.1-mini, 5 metrics) |
|---|---|---|---|
| 10,000 conversations/day | 5% | 500 | ≈$130 |
| 100,000/day | 5% | 5,000 | ≈$1,300 |
| 100,000/day | 20% | 20,000 | ≈$5,100 |
| 100,000/day | 100% | 100,000 | ≈$25,000 |
| 1,000,000/day | 1% | 10,000 | ≈$2,600 |

A 1–5% random sample plus 100% of flagged conversations (guardrail warnings, low user ratings, long latency) is the usual compromise.

### Scenario C: the chatbot itself (for comparison)

| Traffic | Haiku-class model | Sonnet-class model (≈20× price) | With prompt caching (≈−70% on the fixed prefix) |
|---|---|---|---|
| 10,000 conversations/day | ≈$90 / month | ≈$1,800 / month | ≈$30 / ≈$600 |
| 100,000/day | ≈$900 / month | ≈$18,000 / month | ≈$300 / ≈$6,000 |
| 1,000,000/day | ≈$9,000 / month | ≈$180,000 / month | ≈$3,000 / ≈$60,000 |

In this project 85–90% of every request's input tokens are the same system prompt, tool definition and chunks; prompt caching is the single biggest saving on the serving side.

### Scenario D: red teaming

| Attack set | Per run | Monthly (weekly run) |
|---|---|---|
| 112 attacks (this project) | ≈$0.06 | ≈$0.25 |
| 2,000 attacks (20 plugins × 10 tests × 10 strategies) | ≈$1 | ≈$4 |
| 20,000 attacks with multi-turn strategies (≈5 turns each) | ≈$50 | ≈$200 |

Red teaming is cheap per attack; the cost is in reading the results. Multi-turn and iterative strategies (crescendo, tree-of-attacks) multiply calls by 5–20×.

### Scenario E: a one-off eval with a frontier judge on a big dataset

A 10,000-item dataset × 5 metrics × ≈3 calls × ≈4,000 tokens ≈ 600M tokens. At gpt-4.1-mini prices ≈ $300; at a frontier-class judge (≈$3 / $15 per 1M) ≈ $2,000–2,500 per run. This is why judge choice is validated once against human labels and then fixed.

## 3. Rules of thumb

1. Budget the eval suite as **5–10× the serving cost of the sampled traffic**, more if the judge is a frontier model.
2. The judge bill scales with **items × metrics × context size**; the serving bill scales with **traffic × prompt size**. Different levers, different owners.
3. Put spend caps on every key used by CI and online evals; a misconfigured loop is a cost incident, not a quality incident.
4. Record token usage in every result file (this project did it for answers and red teaming, not for agent runs and judge calls; that gap is why half of this report is estimated).
