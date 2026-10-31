# Red team summary (Promptfoo, local mode, 112 attacks)

Defended = grader passed (attack failed). before = default prompt; hardened = hardened prompt; defended = hardened prompt + guardrails.

| plugin | before | hardened | defended |
|---|---|---|---|
| contracts | 12/12 | 12/12 | 12/12 |
| excessive-agency | 12/12 | 12/12 | 12/12 |
| hallucination | 12/12 | 12/12 | 11/12 |
| intent | 40/40 | 40/40 | 40/40 |
| overreliance | 12/12 | 12/12 | 12/12 |
| pii:direct | 12/12 | 12/12 | 12/12 |
| prompt-extraction | 12/12 | 11/12 | 12/12 |
| **total** | 112/112 | 111/112 | 111/112 |
| blocked by input filter | 0 | 0 | 30 |

| strategy | before | hardened | defended |
|---|---|---|---|
| base64 | 28/28 | 28/28 | 28/28 |
| basic | 28/28 | 28/28 | 28/28 |
| jailbreak-templates | 28/28 | 27/28 | 27/28 |
| leetspeak | 28/28 | 28/28 | 28/28 |
| **total** | 112/112 | 111/112 | 111/112 |
| blocked by input filter | 0 | 0 | 30 |
