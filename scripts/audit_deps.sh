#!/usr/bin/env bash
# Dependency audit: known vulnerabilities in Python and Node dependencies.
# Run locally:  ./scripts/audit_deps.sh       (CI runs the same script, no API keys needed)
#
# pip-audit fails the build on any NEW advisory. The IDs below are ACCEPTED RISKS, each with a
# reason; review this list when upgrading packages (see docs/SECURITY_REVIEW.md, section 2).
set -uo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-.venv/bin/python}"

ACCEPTED_RISKS=(
  # chromadb 1.5.9 (latest): RCE and tenant-isolation bugs in the Chroma HTTP SERVER.
  # Not reachable here: the project uses the embedded PersistentClient, no server is exposed.
  --ignore-vuln PYSEC-2026-311 --ignore-vuln PYSEC-2026-3814 --ignore-vuln PYSEC-2026-3815 --ignore-vuln PYSEC-2026-3813
  # diskcache 5.6.3: pickle in local cache files; needs write access to the cache directory.
  --ignore-vuln PYSEC-2026-2447
  # ragas 0.4.3 (latest): file/URL handling in the multimodal faithfulness module, which is not used.
  --ignore-vuln PYSEC-2026-3046
  # langchain-openai 1.1.9: SSRF in image token counting (not used). The fixed 1.1.14 needs
  # openai>=2.26, which breaks ragas -> instructor (openai<2). Re-check when ragas moves to openai 2.x.
  --ignore-vuln PYSEC-2026-76
)

status=0
echo "== pip-audit (Python)"
"$PY" -m pip_audit --version >/dev/null 2>&1 || "$PY" -m pip install --quiet pip-audit
"$PY" -m pip_audit --progress-spinner off --desc on "${ACCEPTED_RISKS[@]}" || status=1

echo "== npm audit (Promptfoo, local dev tool only; lockfile-based, nothing installed)"
# Non-blocking: promptfoo is not part of the application and never runs in CI.
# Upgrade promptfoo when a release without high-severity advisories is available.
(cd redteam && npm audit --package-lock-only --audit-level=high) || echo "::warning::npm audit found high-severity advisories in redteam/ (dev tool only, see docs/SECURITY_REVIEW.md)"

exit $status
