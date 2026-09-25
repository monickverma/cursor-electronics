# Jev calibration on Circuit OS's own domain

## How accurate and calibrated is Jev on Circuit OS questions, overall and by question type and category?

### Takeaway
Pending. The live run has not started. This file currently holds only the pre-registration record, which was written before any Jev call.

### Cited Findings
- **Pre-registration record (written 2026-09-24T22:56:00Z, before any Jev call in this study).** Labelled set `items.jsonl` (361 items, 739 planned requests). sha256 `69a52ee5c689d37eb65cf6f59f6063937379eb446d5c862d2efc9b7cb67a86c9`. Generator `make_items.py` sha256 `057151356f483634abd6e60a4fb3165801d6fbb7cfe9aab52b9a221d590ecad5`. `manifest.json` sha256 `f4f9989c61dd20e2b992801f610d9f4dbeb91144b126f01bd39b69fdb4e79a55`. The manifest was created at 2026-09-24T22:55:47+00:00 and holds the analysis plan and hypotheses H1–H6. Files: [items.jsonl](../../tools/jev/interrogation/calibration/items.jsonl), [make_items.py](../../tools/jev/interrogation/calibration/make_items.py), [manifest.json](../../tools/jev/interrogation/calibration/manifest.json)
- Items per category, from the manifest: a closed-form 120, b units 36, c qualitative 53, d project rules 42, e unanswerable 36, f multi-step 38, g comparison 36. Planned requests: 361 base, 282 twins (precomputed or rule-in-state), 72 repeats (20 % per category), 24 solo (q1 alone). Model pinned to `jev-1.13.0` — [manifest.json](../../tools/jev/interrogation/calibration/manifest.json)
- The hypotheses were fixed before the run:
  - H1: compute is less accurate than precomputed.
  - H2: near-threshold items are less accurate than far ones.
  - H3: when p_top ≥ 0.9, accuracy on compute items is below 0.9, while accuracy on rule-in-state items is at least 0.9.
  - H4: Nouls on unanswerable items lean "no" rather than sitting at 0.35–0.65.
  - H5: Choices abstain on at least 80 % of unanswerable items.
  - H6: polarity sums deviate more on compute items than on rule items.

  Source: [manifest.json](../../tools/jev/interrogation/calibration/manifest.json)

### Inferences
- Pending.

### Gaps
- Pending.
