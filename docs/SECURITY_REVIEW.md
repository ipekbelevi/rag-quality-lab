# Security review (2026-11-01)

Scope: the repository, its dependencies, the CI setup and the chatbot's data flows. The order database is fake and the company is fictional, so the review is about **how the project would behave with real data**, not about data that is at risk today.

Method: `git log` secret scan over the full history, `pip-audit` on a clean install of `requirements.txt`, `npm audit` in `redteam/`, a read-through of the workflow file and of `app/`.

## Summary

| Area | Status | Highest-priority action |
|---|---|---|
| Secrets in the repo | ✅ none, ever | Add a secret scanner (pre-commit or GitHub push protection) |
| Python dependencies | ⚠️ 14 advisories in 5 packages, none exploitable in this setup | Pin `langchain-openai>=1.1.14`, add `pip-audit` to CI |
| Node dependencies (Promptfoo) | ⚠️ 9 advisories (5 high) in a local dev tool | Upgrade Promptfoo when a fix is out; never run it in CI with secrets |
| GitHub Actions | ✅ least privilege, fork-safe | Pin actions to commit SHAs |
| Chatbot: authorization | ❌ anyone can read any order | Verify ownership before returning order details |
| Chatbot: abuse / cost | ❌ no input limit, no rate limit | Max input length, per-session limits, spend caps |
| Chatbot: injection defenses | ⚠️ regex-only filters | Keep the code limits; add a model-based guardrail |
| Tracing / privacy | ⚠️ full user text goes to Langfuse cloud | PII masking and retention settings before real traffic |

## 1. Secrets and repository hygiene

- Full git history: 0 key-like strings. `.env` is ignored and was never committed. `.env.example` has empty values.
- Nothing in the tracked files points at personal accounts (no e-mails, no Langfuse project ids).
- **Recommendations**
  - Install `gitleaks` as a pre-commit hook, or enable GitHub secret scanning with push protection (free on public repos).
  - Use separate API keys for CI with a monthly spend cap in the provider console.

## 2. Dependencies (supply chain)

### Python (`pip-audit`, clean install)

| Package | Advisories | Relevant here? | Action |
|---|---|---|---|
| chromadb 1.5.9 | 4 (RCE and tenant-isolation bugs in the **Chroma HTTP server**) | No: the project uses the embedded `PersistentClient`, no server is exposed | Do not deploy Chroma as a server on this version; watch for a fix |
| langchain-openai 1.1.9 | 1 (SSRF in image token counting) | No: not used; pulled in by RAGAS | Pin `langchain-openai==1.1.14` (fix available) |
| ragas 0.4.3 | 1 (multimodal file/URL helper) | No: multimodal metrics are not used | Watch for a fix |
| diskcache 5.6.3 | 1 (pickle in cache files) | Low: needs write access to the local cache dir | Keep cache dirs out of shared storage |
| setuptools 79.0.1 | 2 | No: build tool only | `pip install -U setuptools` in the venv/CI |

### Node (`npm audit` in `redteam/`)

9 advisories (5 high, 4 moderate) in Promptfoo's transitive dependencies (`proxy-agent`/`basic-ftp`, `glob`/`minimatch`, `@hono/node-server`). Promptfoo is a local developer tool that is not part of the application and does not run in CI. Upgrade when a fixed Promptfoo release exists; keep `node_modules` out of the repo (it is).

### Recommendations

- Add a free `dependency-audit` CI job: `pip-audit` and `npm audit --audit-level=high`.
- Generate a lock file for transitive Python pins (`pip-compile` or `uv lock`); `requirements.txt` pins only top-level packages.
- Enable Dependabot or Renovate.

## 3. GitHub Actions

Good: `permissions: contents: read`; `pull_request` (not `pull_request_target`), so fork PRs never see secrets; the paid job is skipped for forks; secrets are only read into env vars; `cancel-in-progress` limits accidental spend.

- **Pin actions to commit SHAs** (`actions/checkout@<sha>`) instead of `@v7` tags. A moved tag is a known supply-chain attack path.
- Artifacts contain the bot's answers and retrieved chunks. Fine for fictional data; with real data, do not upload raw answers.

## 4. Application-level findings (LLM-specific)

| # | Finding | OWASP LLM | Severity (with real data) | Fix |
|---|---|---|---|---|
| A1 | **No ownership check on order lookups.** Any visitor who knows or guesses an order number gets items, tracking number and delivery date. | LLM06 / LLM02 (BOLA) | High | Require a second factor (order e-mail or last 4 digits of the phone) before details are returned; return only status by default; bind lookups to an authenticated session. |
| A2 | **Enumeration is limited per message, not per session.** 2 lookups per message × many messages = a scanner. | LLM06 | Medium | Per-session and per-IP limits; lock after N invalid numbers; alert on `input-guardrail` WARNING spikes in Langfuse. |
| A3 | **No input length limit.** A 100,000-character message is embedded and sent to the model → cost and latency abuse. | LLM10 (unbounded consumption) | Medium | Reject inputs over ~2,000 chars before any API call; keep `max_tokens` low (it is 2048). |
| A4 | **No rate limiting or per-user budget.** | LLM10 | Medium | Request limits per session/IP; provider-side spend caps; a daily budget alarm on cost in Langfuse. |
| A5 | **Input filter is regex-based.** Catches base64 and known phrases; 1 of 28 jailbreak templates and leetspeak passed through to the model. | LLM01 | Medium | Treat it as a cheap first layer only. Add a model-based guardrail (a prompt-injection classifier or a small LLM check) in front of the main model; keep the code limits as the last line. |
| A6 | **Tool-output sanitization is regex-based.** An injected note that avoids the known phrases reaches the model. | LLM01 (indirect) | Medium | Allowlist the fields the model may see (status, items, dates); drop free-text fields such as notes entirely, or pass them clearly labelled as untrusted data. |
| A7 | **Error details returned to the caller** (`provider.py` returns exception class and message). | LLM02 | Low | In a real API, log details server-side and return a generic error. |
| A8 | **Single-turn only.** Multi-turn support would open new injection paths (instructions planted in earlier turns) and growing context cost. | LLM01 / LLM10 | Info | Re-run the red team and add multi-turn cases before adding conversation memory. |
| A9 | **Tool input validation relies on the schema flag** (`strict: true`) and a regex in the tool. | LLM06 | Low | Validate tool inputs with a Pydantic model before executing; never `**unpack` raw model input into a function. |

## 5. Data flows and privacy

- **Langfuse** receives the full question, retrieved chunks, model output and tool results (EU cloud). With real customers this is personal data. Before real traffic: enable PII masking (`mask_otel_spans`), set retention, sign the provider's DPA, and keep `TRACING` off by default in production until this is done.
- **OpenAI and Anthropic** receive the same text (chat, embeddings, judge). Use the providers' zero-data-retention / enterprise options for real customer data, and never send real order data to the judge model in evals.
- **Telemetry**: DeepEval and Promptfoo telemetry are disabled; Promptfoo remote generation is disabled by default.
- **Chroma** stores the help-center documents locally (`chroma_db/`, ignored). These are public documents; no PII.

## 6. Already in place (keep)

- Different model families for bot and judge; deterministic security regression tests; defense in depth (prompt + input filter + tool limits + output sanitization); unit tests for guardrail false positives; least-privilege CI; no secrets in git; telemetry off.

## 7. What was done after this review (same day)

| Finding | Status | Where |
|---|---|---|
| Secret scanner | ✅ gitleaks job on every push/PR and weekly | `.github/workflows/dependency-audit.yml` |
| Dependency audit in CI | ✅ `pip-audit` (blocking, with a documented accepted-risk list) + lockfile-only `npm audit` (warning) | `scripts/audit_deps.sh`, same workflow |
| `langchain-openai` 1.1.14 | ❌ not possible: needs `openai>=2.26`, which breaks `ragas` → `instructor` (`openai<2`). Pinned at 1.1.9 as an accepted risk (code path unused) | `requirements.txt` |
| setuptools | ✅ `>=84.1.0` | `requirements.txt` |
| Actions pinned to SHAs | ✅ both workflows | `.github/workflows/*.yml` |
| A1 ownership check | ⚠️ **not implemented on purpose** (changes the product and the agent spec); warnings in code and README | `app/tools.py`, `app/guardrails.py`, README "Security warnings" |
| A2 per-session limits | ✅ requests, lookups and lockout after 3 failed order numbers (`SessionLimiter`); in-memory, see warning | `app/guardrails.py`, `app/chatbot.py` |
| A3 input length limit | ✅ 2,000 chars, checked before any API call | `app/guardrails.py` |
| A4 rate limiting / budget | ✅ per-session request cap; ⚠️ per-IP limits and provider spend caps are deployment tasks (README warning) | — |
| A5 model-based guardrail | ⚠️ not added (cost/latency per request; needs its own eval); documented as next step | README |
| A6 tool-output allowlist | ✅ only business-owned fields reach the model; customer text is hidden regardless of wording | `app/guardrails.py` `filter_tool_output` |
| A7 error details | ✅ generic error to the caller, details to the local log | `redteam/provider.py` |
| A8 multi-turn | ⚠️ warning only (no multi-turn support) | README |
| A9 tool input validation | ✅ Pydantic model with `extra="forbid"` before any function call | `app/tools.py` |
| PII in traces | ✅ masking of e-mails, phones and card-like numbers on by default; ⚠️ retention/DPA are deployment tasks | `app/tracing.py` |

All changes are covered by unit tests (`tests/test_guardrails.py`, 64 tests, no API calls) and the full gate (`./scripts/ci_eval.sh`) plus a Promptfoo re-run were executed afterwards; see `results/verify_security_fixes.log` and `results/redteam_summary.md`.
