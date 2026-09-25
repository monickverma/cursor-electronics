# Dossier battery — results

The full Circuit OS dossier (`circuit_os_dossier.md`, 94,613 chars ≈ 27k tokens) or the core dossier (25,364 chars) is the state; the 257 battery questions are packed into requests up to ~31k input tokens (measured hard limit ≈ 32.9k, see results.jsonl probes). Variants: `full`, `full_rev` (option order reversed), `core`.

30 requests, 0 errors, 855,072 input tokens, median 1.9 s per request.

## A. Reading the dossier (ground truth from the text or by construction)

| Needle kind | full | full_rev | core |
|---|---|---|---|
| present answer (choice) | 49/49 = 100 % | 49/49 = 100 % | in core 9/9 = 100 %; not in core → NMI 37/40 = 92 %, still right 2 |
| absent answer → need_more_information | 12/13 = 92 % | 12/13 = 92 % | 13/13 = 100 % |
| absent answer, yes/no → 0.25–0.75 | 2/3 = 67 % | 2/3 = 67 % | 2/3 = 67 % |
| polarity yes/no | 24/24 = 100 % | 24/24 = 100 % | 19/24 = 79 % |

Wrong on the full dossier (2): `a04_flaky_assertion` truth need_more_information → cutoff_frequency (None); `a16_noul_flake_seed` truth 0.25<=p<=0.75 → 0.2 (None)

Polarity pairs (full): P(yes)+P(not) median 1.02, off by >0.15: 0/12.
Present-answer accuracy by position of the answer in the 94 KB file: 0–25 %: 15/15 = 100 %, 25–50 %: 16/16 = 100 %, 50–75 %: 6/6 = 100 %, 75–100 %: 12/12 = 100 %

## B/C. Judgment questions (no ground truth; stability and agreement)

| Category | n | same answer full/full_rev/core | full = full_rev | agrees with reference (where one exists) | agrees with agent prior | median p_top (full) | picks need_more_information (full) |
|---|---|---|---|---|---|---|---|
| owner_decision_prior_run | 20 | 15/20 = 75 % | 19/20 = 95 % | — | 5/8 = 62 % | 0.95 | 2 |
| owner_decision | 12 | 12/12 = 100 % | 12/12 = 100 % | — | 6/9 = 67 % | 0.59 | 2 |
| phase2_exit_defeater | 9 | 3/9 = 33 % | 6/9 = 67 % | 2/2 = 100 % | 6/9 = 67 % | 0.60 | 3 |
| phase2_exit_stage | 7 | 2/7 = 29 % | 7/7 = 100 % | 1/1 = 100 % | — | nan | 0 |
| door | 16 | 15/16 = 94 % | 16/16 = 100 % | 13/14 = 93 % | 13/14 = 93 % | 0.92 | 0 |
| phase3 | 12 | 9/12 = 75 % | 11/12 = 92 % | 2/2 = 100 % | 0/1 = 0 % | 0.37 | 1 |
| product_market | 12 | 7/12 = 58 % | 11/12 = 92 % | 5/5 = 100 % | 1/1 = 100 % | 0.71 | 0 |
| risk | 23 | 11/23 = 48 % | 23/23 = 100 % | — | — | nan | 0 |
| priority | 24 | 12/24 = 50 % | 24/24 = 100 % | — | — | nan | 0 |
| self_assessment | 33 | 10/33 = 30 % | 32/33 = 97 % | — | 17/33 = 52 % | nan | 0 |

Judgment questions whose answer flipped just from reversing option order (7): `prior__rs485__reboot_contention_material__not` False→True; `exit_D1` need_more_information→acceptable_open_with_trigger; `exit_D4` need_more_information→acceptable_open_with_trigger; `exit_D7` need_more_information→acceptable_open_with_trigger; `p3_fit_rs485_io_opto` 1→2; `pm_h3_impact` 3→2; `self_R10` 2→1
