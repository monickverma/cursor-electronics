# Jev robustness, determinism, limits, latency and cost, measured live, for Circuit OS's stability-gated decision protocol

(Working draft. The pre-registration record below was written at 2026-09-24T22:57Z, before any Jev call on these item sets. Results sections are filled in after the runs.)

## Method and pre-registration

### Pre-registration record (written before any call on these sets)

All item sets are in `tools/jev/interrogation/robustness/items/`. They were built by `scripts/build_items.py` from the hand-authored banks `scripts/items_spec.py`, `scripts/items_known.py` and `scripts/items_judgment.py`. Ground truth for known-answer items comes from Circuit OS rule text in the p2 snapshot and the 2026-09-25 handoff, never from Jev. Each item carries its `derivation`. The runners refuse to send any file whose sha256 differs from `items/PREREGISTRATION.tsv` (`jevlog.verify_prereg`).

| Registered (UTC) | File | sha256 | Requests | Questions |
|---|---|---|---|---|
| 2026-09-24T22:57:04Z | E1a_conf_k.json | 84974b7cfb5d0ce2f7504a36aca76b319d42b3e90ade73a65ab3be1ab34b3fc5 | 12 | 84 |
| 2026-09-24T22:57:04Z | E1b_score_formula.json | 8375b9435a913ca8c49a8a3e65d9a7d971f7346a56725749a196b597af696e3d | 12 | 96 |
| 2026-09-24T22:57:04Z | E2_determinism.json | 82ef3883d7a6b34f5cdca779a5f6dbfb0f695c16541f9a41b77cc34508e437da | 1 (x36 scheduled) | 20 |
| 2026-09-24T22:57:04Z | E3_order.json | d93060f7aa276b6d594e52fb00570c064d93469d9b060b7a972c436b55c828f4 | 88 | 528 |
| 2026-09-24T22:57:04Z | E3b_order_separate.json | 52c7053e561abc562e8147d0b70547bb78a4b9c9c0bbb675a513ed71f34a39f0 | 36 | 36 |
| 2026-09-24T22:57:04Z | E4_paraphrase.json | a3b98213043a4e0baa2e1c7088616d90646b1b57530dd76fb0a574db9756ac75 | 140 | 560 |
| 2026-09-24T22:57:04Z | E5_polarity.json | 1e51a60df0bdf3e725f2dfdf59ad755fead192b0a614d6df46d17c5dfe60153d | 48 | 232 |
| 2026-09-24T22:57:04Z | E6_authority.json | c2b1d15287dfa973b7eee60413842d1e9738cbfc3a8e01ef43d5e754521b4e32 | 308 | 616 |
| 2026-09-24T22:57:15Z | E7_distractors.json | 250effb63ec5882c8b8ef2496c821f76f56b182cd462253eaca3f0d9efb76ac2 | 128 | 256 |
| 2026-09-24T22:57:04Z | E8_batching.json | 536742332ea729868a43b6ec0e2abcdadf4e99eaf17677249c6d957b6794d697 | 60 | 1220 |
| 2026-09-24T22:57:04Z | E9_nmi.json | f0b6d68b49b0c70f0125d017b5c1ecdbe6d143ed583a440bbc23cd6c3f2b67de | 72 | 288 |
| 2026-09-24T22:57:04Z | E10_scaling.json | f52fb827aaab3fa78c955f3f9ab3f304b087e377354d885f8a0a2dcfe75f7cc2 | 20 | 400 |

E7 was rebuilt at 22:57:15Z, before any call, only to correct its description string. It had named 3 distractor source files. The `distractor_sources` field lists the 8 that are actually used.

Source hashes at registration: `items_spec.py` 54d7b1e4…ebfc8, `items_known.py` ebfcf31f…ca27f, `items_judgment.py` f515a968…b5c1b, `build_items.py` e0256ede…3f6b.

Calls made before registration touched no labelled item set. They were: `GET /v1/models` (1), one smoke-test Noul on "The sky is blue." (1), and two calibration calls that measured characters per token on the E10 filler texts (40,000 characters of text A = 11,010 input tokens; 40,000 characters of text B = 9,794 input tokens).
