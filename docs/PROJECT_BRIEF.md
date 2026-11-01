# RAG Quality Lab

Repository: https://github.com/ipekbelevi/rag-quality-lab

---

## About this project

I built this project to learn, hands-on, how quality assurance works for applications built on large language models. The system under test is a small retrieval-augmented (RAG) customer-support chatbot for a fictional coffee company, written in plain Python on the Anthropic and OpenAI SDKs with a local Chroma vector store and one order-lookup tool. The chatbot itself is deliberately simple; the substance of the work is the quality layer around it. Over eight phases I built a human-reviewed golden dataset, automated evaluations with DeepEval and RAGAS, agent and tool-calling tests, a security assessment with Promptfoo red teaming mapped to the OWASP Top 10 for LLM applications, bias and toxicity checks, end-to-end tracing with Langfuse, and a GitHub Actions quality gate that blocks a pull request when quality drops. The company is fictional on purpose: the model cannot know its policies in advance, so every invented detail is a visible hallucination rather than a plausible guess.

The method followed classic testing discipline applied to a non-deterministic system. The golden dataset was generated with an LLM and then reviewed item by item; roughly a third of the draft needed correction, including one reference answer that was itself a hallucination, which is why the review decisions are versioned in code with their reasons. The chatbot runs on Claude and the judge on GPT-4.1-mini, so no model grades its own family. I scored the same answers with DeepEval and RAGAS and found that identically named metrics measure different things, to the point where RAGAS gives a zero to an honest "I don't have that information". Scoring the same answers twice flipped the pass/fail result of 5 of 130 checks, so the quality gate is built on mean scores with thresholds derived from the measured baseline and its noise, and per-item failures are treated as diagnostics. I then broke the system on purpose three ways, with tiny chunks, a deleted document and a weakened prompt, and confirmed that the gate failed each time and that the metric that dropped pointed at the broken layer. Agent tests separate what code can verify (tool name and parameters, exact match, no judge) from what needs a judge (task completion), and run every case three times to measure consistency. The red team reported all 112 attacks defended while the bot could still be used to enumerate order numbers; I found this by reading the outputs, converted it into deterministic regression tests, added three defense layers (hardened prompt, input filter, code-level tool limits with an allowlist on tool output), measured the before-and-after, and re-ran the full suite to confirm the defenses did not degrade normal answers. Tracing initially reported twice the real token count because of duplicate SDK spans, caught by cross-checking against the application's own counter; evaluation scores are now attached to traces so a low score shows its retrieval, prompt and judge reasoning on one screen.

The outcome is a reproducible, documented quality process for an LLM application, with real numbers at every step and a total API cost of about $3.5, roughly 90% of which is the judge rather than the chatbot. The repository contains the test data, every saved run, a plain-English overview, a security review with a dependency audit and a status for each finding, and a cost model that extrapolates the measured unit costs to real datasets and live traffic. Its limits are stated openly: small datasets, a single inexpensive judge, single-turn conversation, a regex input filter, and no ownership check on order lookups, which was left as a documented product decision rather than quietly fixed. What transfers to real work is the approach: an eval suite that is independent of the system it tests, a golden set treated as a test oracle that must itself be verified, thresholds that are calibrated rather than guessed, security findings turned into regression tests, observability data that is itself tested, and a gate that runs with production settings on every change at a known cost.

---

## Prompt for an AI assistant

Copy the block below into any AI assistant (for interview preparation, a cover letter, a LinkedIn post, a portfolio page or a talk outline). Edit the last line to say what you want produced.

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
