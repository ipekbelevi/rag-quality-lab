# RAG Quality Lab

Repository: https://github.com/ipekbelevi/rag-quality-lab

**TL;DR**
- I built the **complete QA layer around an LLM app**: evals, agent tests, red teaming, tracing, CI gate.
- The chatbot is **only the test subject**. The work is the testing.
- **8 phases, ~$3.5 of API usage, every step documented with numbers.**

---

## 1. What and why

**What:** a small RAG support chatbot for a **fictional** coffee company (Belevico), plus everything needed to **prove its quality and catch regressions**.

**Why fictional:** the model cannot know Belevico's policies → **every invented detail is a visible hallucination.**

**Why this project:** LLM apps don't fail like normal software.
- Same question → **different answer each time**
- **Invented facts** that sound right
- **Hidden instructions** inside a message
- `assert answer == expected` catches **none** of this

---

## 2. The plan: 8 phases

```
 Phase 0        Phase 1        Phase 2         Phase 3          Phase 4
 SETUP    ──►   RAG BOT   ──►  GOLDEN SET ──►  EVALS       ──►  AGENT TESTS
 2 providers,   14 docs,       30 Q&A,         DeepEval +       tool correctness,
 pinned         Chroma,        LLM-generated,  RAGAS, gate,     task completion,
 versions       1 tool         human-reviewed  break-it tests   3 repeats
                                                                      │
                                                                      ▼
 Phase 7        Phase 6        Phase 5                        + Security review
 CI GATE   ◄──  TRACING   ◄──  SECURITY                         dependency audit,
 GitHub         Langfuse,      Promptfoo red team,              code fixes,
 Actions,       scores on      OWASP LLM Top 10,                accepted risks
 3 gates        traces         bias/toxicity, defenses
```

**Rule in every phase:** before → change **one thing** → measure again → write it down.

---

## 3. How the app works

```
 customer question
        │
        ▼
 ┌─────────────────┐  attack / too long
 │ INPUT GUARDRAIL │ ─────────────────────►  polite refusal  (no LLM call, $0)
 └────────┬────────┘
          ▼
 ┌─────────────────┐
 │    RETRIEVER    │  top-4 chunks from 14 help-center docs (Chroma + embeddings)
 └────────┬────────┘
          ▼
 ┌─────────────────┐        ┌──────────────────────────┐
 │  CLAUDE (LLM)   │ ◄────► │ ORDER-STATUS TOOL        │
 │  answers only   │        │ fake table, validated    │
 │  from chunks    │        │ input, max 2 lookups,    │
 └────────┬────────┘        │ customer notes hidden    │
          ▼                 └──────────────────────────┘
       answer ─────────────────────────────────────────►  LANGFUSE TRACE
                                                          (steps, tokens, cost, scores)
```

**Design choice:** plain Python, no LangChain → every retrieval, prompt and tool step is **visible and easy to break on purpose**.

---

## 4. The test layers

```
 ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
 │ GOLDEN SET    │ │ AGENT CASES   │ │ SAFETY CASES  │ │ RED TEAM      │ │ UNIT TESTS    │
 │ 30 Q&A        │ │ 12 cases × 3  │ │ 13 cases × 3  │ │ 112 attacks   │ │ 64 tests      │
 │ DeepEval+RAGAS│ │ DeepEval      │ │ DeepEval +    │ │ Promptfoo     │ │ guardrails    │
 │ judge: GPT    │ │ tool + task   │ │ custom checks │ │ OWASP LLM     │ │ free, no keys │
 └───────┬───────┘ └───────┬───────┘ └───────┬───────┘ └───────────────┘ └───────────────┘
         └─────────────────┴─────────────────┘
                           ▼
            QUALITY GATE:  mean score per metric ≥ threshold → else the build FAILS
```

| Layer | Checks | Who decides |
|---|---|---|
| **RAG answers** | faithfulness, relevancy, context precision/recall, hallucination, correct refusal | LLM judge (GPT-4.1-mini) |
| **Agent** | right tool + right parameters (**exact match, no judge**), task completed | code + judge |
| **Safety** | bias, toxicity, enumeration limit, forbidden text, policy | judge + **deterministic** checks |
| **Red team** | prompt injection (direct + indirect), prompt leakage, data disclosure, excessive agency | Promptfoo grader + **my own reading** |

---

## 5. What I found (the numbers that matter)

**Golden dataset**
- LLM-generated draft → **~30% needed human correction**
- One reference answer was **itself a hallucination** → would have failed a *correct* bot
- Review decisions are **versioned in code with reasons**

**Evals**
- Same answers scored twice → **5 of 130 pass/fail results flipped**
- → gate uses **mean scores**, thresholds = **baseline − measured noise**
- DeepEval vs RAGAS: **same metric name ≠ same metric** (RAGAS gives **0** to an honest "I don't know")
- Broke the system 3 ways (tiny chunks, deleted doc, weak prompt) → **gate failed all 3**, dropping metric **pointed at the broken layer**

**Agent tests**
- Broken tool description: task completion **0.96 → 0.91** (barely moves)
- but tool correctness **1.00 → 0.27**, tool calls **+85%**, latency **+55%**
- → **outcome-only testing would have missed it**

**Security**
- Promptfoo said **112/112 defended** → I read the outputs → bot could **enumerate order numbers**
- Turned it into **deterministic regression tests**
- Added 3 defense layers: **hardened prompt → input filter → code-level limits + allowlist**
- Security regression scores **0.50 → 1.00**; **30 attacks blocked before any LLM call**
- Re-ran the full suite: **no regression for normal users** (cost: **+17% tokens**)

**Observability**
- Tracing showed **2× the real token count** (duplicate SDK spans) → caught by **cross-checking the app's own counter**
- Eval scores now **attached to traces** → one click from a low score to its retrieval, prompt and judge reason

**CI**
- Same script **locally and in CI**, production settings, **3 gates**
- **≈ $0.40 and 5–6 minutes per run**; free unit tests first; path filters + run cancellation
- Separate **dependency + secret audit** workflow (gitleaks, pip-audit, npm audit)

**Cost**
- Whole project **≈ $3.5**; **~90% is the judge**, not the chatbot
- Unit costs measured → **scaling model** for real datasets and live traffic (`docs/COST_REPORT.md`)

---

## 6. Lessons (one line each)

- **Every red test is not a bug** → some are measurement errors.
- **The judge is a noisy instrument** → gate on averages, calibrate thresholds.
- **The golden set is the test oracle** → it must be verified before it verifies anything.
- **Measure the process, not only the result** (agent tests).
- **A 100% green security report proves nothing** → read the outputs.
- **Prompts ask, code guarantees** → defense in depth.
- **Observability data needs testing too.**
- **Cost is a quality attribute** → measure it, report it.

---

## 7. Honest limits

- Small datasets (**30 / 12 / 13** items)
- **One** inexpensive judge model
- **Single-turn** chat only
- **Regex** input filter (cheap first layer, not a real defense)
- **No ownership check** on order lookups → documented product decision, **not quietly fixed**
- Learning project, **not a production system**

---

## 8. Repository structure

```
rag-quality-lab/
├── app/            chatbot, retriever, ingest, tools, prompts, guardrails, tracing
├── data/
│   ├── docs/       14 fictional help-center documents
│   ├── golden/     golden_draft.json (LLM) → golden_v1.json (human-reviewed)
│   ├── agent/      12 agent cases (expected tool calls + task)
│   └── safety/     13 bias / toxicity / security cases
├── evals/          DeepEval tests, RAGAS runner, thresholds, gate, reports
├── redteam/        Promptfoo config (OWASP LLM Top 10), attacks, before/after summary
├── results/        every saved run: answers, scores, comparisons
├── tests/          64 unit tests for the guardrails (free)
├── scripts/        smoke test, golden set generation + review, CI script, audit, trace viewer
├── docs/           overview, security review, cost report, this brief
└── .github/        LLM quality gate + dependency/secret audit workflows
```

**Tools:** DeepEval · RAGAS · Promptfoo · Langfuse · pytest · GitHub Actions · Anthropic SDK (Claude Haiku 5.5) · OpenAI SDK (GPT-4.1-mini, text-embedding-3-small) · Chroma · Python

**Run it:** `cp .env.example .env` (your own keys) → `python -m app.ingest` → `./scripts/ci_eval.sh`. No keys are stored in the repo.

---

## 9. Prompt for an AI assistant

Copy the block below into any AI assistant (interview prep, cover letter, LinkedIn post, portfolio page, talk outline). Edit the last line to say what you want produced.

```
I want you to help me present a project I built, speaking in my voice (first person).
Treat everything below as my real experience. Do not invent results, tools or numbers
that are not listed here.

PROJECT
RAG Quality Lab: https://github.com/ipekbelevi/rag-quality-lab
A hands-on project in which I built the full quality-assurance layer around an LLM
application. The application is a small RAG customer-support chatbot for a fictional
company; I built it only as the system under test. Building the chatbot is NOT the
achievement. The achievements are the testing, evaluation, security and CI work around it.

MY SUCCESS POINTS (present these, in this order of importance)
1. Automated LLM evaluation with DeepEval and RAGAS: faithfulness, answer relevancy,
   contextual precision and recall, hallucination, and a custom GEval criterion for
   correct refusals. I scored the same answers with both tools and showed that
   same-named metrics measure different things (RAGAS scores an honest "I don't know"
   as 0, DeepEval does not), so I chose metrics by their definitions, not their names.
2. Measuring judge noise and designing the quality gate around it: scoring identical
   answers twice flipped 5 of 130 pass/fail results, so the gate uses mean scores with
   thresholds calibrated from the baseline minus the measured noise; per-item failures
   are diagnostics, not build breakers.
3. Validating the test suite itself: I broke the system on purpose (chunk size 800 to
   120, deleted a document, weakened the system prompt) and showed the gate failed each
   time and the dropping metric identified the broken layer.
4. A human-reviewed golden dataset generated with GenAI: about 30% of the generated
   draft needed correction; one reference answer was itself a hallucination; review
   decisions are versioned in code with reasons (the golden set is the test oracle).
5. Agent and tool-calling tests: deterministic tool-correctness checks (name and
   parameters, exact match, no LLM judge) plus LLM-judged task completion, three
   repeats per case. A broken tool description barely moved task completion
   (0.96 to 0.91) but dropped tool correctness to 0.27 and raised tool calls by 85%
   and latency by 55%: outcome-only testing would have missed it.
6. Security testing and defenses: Promptfoo red teaming mapped to OWASP LLM Top 10
   (prompt injection direct and indirect, system prompt leakage, sensitive data,
   excessive agency), plus bias and toxicity metrics. The tool reported 112/112
   attacks defended while the bot could still enumerate order numbers; I found it by
   reading outputs, turned it into deterministic regression tests, added three defense
   layers (hardened prompt, input filter, code-level limits and an allowlist on tool
   output), measured before/after (security regression scores 0.50 to 1.00) and
   re-ran the full suite to prove no regression for normal users (+17% token cost).
7. Observability with Langfuse: one trace per request with retrieval, LLM calls,
   tokens, cost and tools; evaluation scores attached to traces. I caught the tracing
   itself double-counting tokens (duplicate SDK spans) by cross-checking the app's own
   counter.
8. CI quality gate in GitHub Actions: the same script locally and in CI, production
   settings, three gates (RAG, agent, safety), a free unit-test job first, path filters
   and run cancellation to control cost, a weekly reliability run, actions pinned to
   commit SHAs, a separate dependency and secret audit workflow.
9. Security review of my own project: dependency audit (14 advisories, none
   exploitable, one fix impossible due to a dependency conflict and recorded as an
   accepted risk), code fixes (input length limit, session limits, Pydantic tool
   validation, PII masking in traces), and one finding (no ownership check on orders)
   left deliberately unfixed as a documented product decision.
10. Cost awareness: the whole project cost about $3.5 in API usage, 90% of it the
    judge; I measured unit costs and wrote a scaling model for real datasets and
    live traffic.

WHERE THIS EXPERIENCE IS USEFUL
- Deciding whether an LLM change is safe to release (quality gate pattern).
- Selecting and calibrating evaluation tools and judge models.
- Building test data with GenAI under human review.
- Testing agents and tool use, not only answers.
- Security sign-off for LLM features (OWASP LLM Top 10, red teaming, regression tests).
- Production monitoring and online evaluation (traces with scores).
- Budgeting evaluation and serving costs.

TOOLS: DeepEval, RAGAS, Promptfoo, Langfuse, pytest, GitHub Actions, Anthropic SDK
(Claude Haiku 5.5), OpenAI SDK (GPT-4.1-mini judge, text-embedding-3-small), Chroma, Python.

BACKGROUND: I am a QA engineer working in the AI sector, moving into AI quality;
I am preparing for ISTQB CT-AI and CT-GenAI.

HONEST LIMITS (mention if relevant, never hide): small datasets (30/12/13 items),
one inexpensive judge model, single-turn chat only, regex-based input filter,
a learning project rather than a production system.

TASK: <write here what you want, e.g. "a 90-second interview answer to 'tell me about
a project you are proud of'", "a LinkedIn post", "three STAR-format interview stories",
"a cover-letter paragraph for an AI QA role">
```
