# tools/jev — Jev decision requests

Committed, re-runnable Jev (TypeSafe AI) consultations. The protocol and the reasoning behind every
request are in `reports/Jev decisions for Circuit OS Phase 3.md`.

## Run

```bash
pip install typesafe-sdk==0.7.1          # the PyPI package "typesafe-ai" is NOT the official SDK
python tools/jev/run.py tools/jev/requests/*.json --dry-run      # schema check, no network
python tools/jev/run.py tools/jev/requests/x7_live_pricing.json  # needs TYPESAFE_API_KEY
```

Each run sends the original request plus a label-reversed variant (add `--repeats N`, `--blind`, or a
`<slug>.paraphrase.json` written by a second author for more), appends raw answers to
`<slug>.results.jsonl`, and prints a band per governing question.

## Before running a request

1. Fill every `<PASTE…>`, `<VERIFY…>` and `<CONFIRM…>` slot in its `state`. The runner refuses to
   run while any remain (unless `--allow-placeholders`, which the decision entry must then disclose).
2. Write `agent_prior_agrees_with` — the label your own analysis favours — **before** the call.
   Left `null`, the band is capped at "owner".
3. A re-ask is legitimate only when the state gains a named new fact: bump `attempt_n`. Rewording
   questions until the answer changes is rephrase-shopping.

## Reading results

- Bands use top probability, margin to the runner-up and stability across variants — never
  `confidence` (it is `(k·p_top − 1)/(k − 1)` and rises when options are added).
- `owner_owned` or `door: one_way` requests always end with the owner; Jev only words the recommendation.
- Nouls are diagnostics (decisive / unsettled), never the governing answer.
- The decision entry in `brain/decisions.md` links the request and results files rather than
  restating numbers.

## Contents

| File | Decision | Owner-owned |
|---|---|---|
| `requests/rs485_de_re_pulldown.json` | 10 kΩ DE/RE pull-down on rs485_node | yes |
| `requests/x7_live_pricing.json` | Live pricing (X7) — no answer is approval | yes |
| `requests/d1_bench_timing.json` | When to run the D1 bench session | yes |
| `requests/proof_kind_label.json` | `kind` of exact proofs: analytic vs empirical | yes |
| `requests/explainer_budget.json` | Explainer cost/latency next step | yes |
| `requests/pin_support_version_policy.json` | Generator VERSION bumps (residual after byte-compare) | no (one-way) |
| `requests/stage6_finish.json` | 5% KPI disposition; Stage 6 vs Phase 3 order | no |
| `requests/accuracy_flake_policy.json` | Intermittent accuracy test | no |
| `templates/*.questions.json` | Per-item question sets (D7 figure order, Phase 3 scope and labels, runtime shadow checks, refusal backlog, CI triage) — build a state per item | — |
