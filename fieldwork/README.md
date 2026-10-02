# Field kit — the work only a person can do

Written 2026-10-02 after the end-of-Phase-2 review. Its conclusion was that the repo has a great deal of machinery
for stating doubts and almost no evidence from the physical world or from outside readers. Each sheet here turns
one doubt into something you can do in an afternoon. The agent prepared everything it could; the measuring,
reading, signing and recruiting are yours.

| Step | Sheet | When | Needs | Closes |
|---|---|---|---|---|
| 1 | [Bench afternoon](1_bench.md) | week 1 | Uno, multimeter, parts | D1 on 4 designs; the LED V_F assumption; first firmware on a real board |
| 2 | [D7 spot-check](2_d7_spotcheck.md) | week 1 | the PDFs, about 2 h | whether the bulk confirmation of 126 figures means anything |
| 3 | [Sign the 12 proofs](3_sign_proofs.md) | week 2 | about 1 h of reading | library floor G2 → G1 |
| 4 | [Outside reader](4_outside_reader.md) | weeks 2–3 | OpenRouter credits, 1–3 readers | criterion 12 / D3 |
| 5 | [Ten users](5_user_trial.md) | weeks 3–4 | credits, 10 people | real acceptance rate and refusal backlog |
| 6 | [What this is](6_what_this_is.md) | after 5 | the numbers from 1–5 | thesis or paper vs startup |

`firmware/` is generated output: `python scripts/bench_firmware.py fieldwork/firmware`. It's gitignored, so
regenerate it rather than editing it.

## Found while preparing this (not fixed)

- `CRITERION_12_REVIEW.md` §1's prompt is now refused as underdetermined. Fixed in that file to a fully specified
  prompt.
- OpenRouter credits are exhausted, so live generation returns 503 until they're topped up.
- One `/design/generate` request returned a bare **HTTP 500** during that outage instead of a 503.
- The DHT22 firmware's error message hard-codes "10k pull-up" (`sensor_read.ino.j2:39`), although the pull-up is
  sized per cable. On a long cable the message names the wrong part.
