# Red team summary (Promptfoo, local mode, 112 attacks)

Defended = grader passed (attack failed). before = default prompt; hardened = hardened prompt; defended = hardened prompt + guardrails (Phase 5); defended_v2 = after the security-review fixes (tool-output allowlist, session limits, input length limit).

| plugin | before | hardened | defended | defended_v2 |
|---|---|---|---|---|
| contracts | 12/12 | 12/12 | 12/12 | 12/12 |
| excessive-agency | 12/12 | 12/12 | 12/12 | 12/12 |
| hallucination | 12/12 | 12/12 | 11/12 | 12/12 |
| intent | 40/40 | 40/40 | 40/40 | 40/40 |
| overreliance | 12/12 | 12/12 | 12/12 | 12/12 |
| pii:direct | 12/12 | 12/12 | 12/12 | 12/12 |
| prompt-extraction | 12/12 | 11/12 | 12/12 | 12/12 |
| **total** | 112/112 | 111/112 | 111/112 | 112/112 |
| blocked by input filter | 0 | 0 | 30 | 30 |

| strategy | before | hardened | defended | defended_v2 |
|---|---|---|---|---|
| base64 | 28/28 | 28/28 | 28/28 | 28/28 |
| basic | 28/28 | 28/28 | 28/28 | 28/28 |
| jailbreak-templates | 28/28 | 27/28 | 27/28 | 28/28 |
| leetspeak | 28/28 | 28/28 | 28/28 | 28/28 |
| **total** | 112/112 | 111/112 | 111/112 | 112/112 |
| blocked by input filter | 0 | 0 | 30 | 30 |
