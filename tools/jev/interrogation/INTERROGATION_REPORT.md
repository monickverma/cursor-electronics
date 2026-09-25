# Jev interrogation of Circuit OS: what it can and cannot be trusted with

**Dates:** 2026-09-24 → 2026-09-25 · **Model:** `jev-1.13.0` (pinned; every call resolved to it)
**Volume:** 4,223 Jev requests across six tracks, 0 unexpected errors, ≈ 5.7 M input tokens.

> **Correction.** An earlier version of this file (commit `3e946ae`) was written before most of the tracks
> had been run or scored, and it contained numbers that were never measured: the dossier "96 % on 78
> questions", the latency/determinism/cost tables, "4,500+ label items", the ROI claims. This version replaces
> it. Every number below comes from a results file in this directory and the script that scores it.

Method, common to all tracks: every question set and its labels were generated and SHA-256-hashed **before**
Jev saw them (`PREREGISTRATION.*`, `manifest.json`, `prereg_labels.json`, `sets/`). Ground truth comes from
code, circuit construction, standard text, or computation. None of it comes from Jev. Each item is sent in several variants
(original, option order reversed, repeat, paraphrase, blind) so stability is measured, not assumed.

| Track | Requests | Scored by | Result file |
|---|---|---|---|
| Calibration: electronics domain (361 items, 7 categories) | 739 | `calibration/analyze.py` | `calibration/results_tables.md` |
| Runtime shadow checks: IntentIR transcription, patches, prompt injection | 958 | `runtime/analyze.py` | `runtime/RESULTS.md` |
| Robustness: confidence, determinism, order, paraphrase, polarity, authority, distractors, batching, abstention, size | 948 | `robustness/analyze.py` | `robustness/RESULTS.md` |
| **Big file:** the whole 94.6 KB Circuit OS dossier + 257-question battery (plus 18 size-limit probes) | 48 | `dossier/analyze_battery.py` | `dossier/BATTERY_RESULTS.md` |
| Dev workflow: decision↔commit, CI failure class, doc drift, entry quality, owner attention, commit convention | 1,128 | `devflow/analyze.py` | `devflow/RESULTS.md` |
| Phase 3 assurance labels: P1 net role, P2 environment, P3 isolation, P4 standard family | 402 | `labels/run_and_analyze.py` | `labels/RESULTS.md` |

---

## The answer in six lines

1. **Jev reads extremely well.** In the full 94.6 KB dossier it answered 49/49 fact questions correctly, with no
   loss at any depth in the file. It abstained correctly on 12/13 questions whose answer is absent. In
   size-scaling tests it found 8/8 planted facts at every size up to the ~31k-token limit.
2. **Jev computes badly.** Give it component values and ask for a threshold decision, and it gets 67 % right. It drops
   to 53 % when the value is within 5 % of the limit. Put the computed number in the state and it gets **100 %** (229 pairs,
   76 wrong→right, 0 right→wrong). *Code computes, Jev weighs.*
3. **Its answers are stable where it matters.** Option order changed nothing (74/74 known items identical in all
   6 orders). Paraphrase changed 1 of 29 known items. Irrelevant text up to 2× the state and batching of up to 50 questions changed
   nothing. It is **not** bit-deterministic: probabilities wobble by up to ±0.07, and 1 of 20 yes/no answers flipped once in 20 repeats.
4. **Its confidence is honest in one direction only.** On known-answer items, p_top ≥ 0.9 was right 95–100 % of the time
   in every track. Four confidently wrong answers exist in the calibration set, and all four are computed values within 5 % of a
   limit.
5. **It can be pushed.** A note saying "the owner/experts say X" moved 13–15 % of answers to the cued wrong
   option (0 % for "URGENT" or "council"). Text injected into a user command provoked false flags in 3/4 faithful patches.
   Jev must never read state an attacker controls if its answer gates anything.
6. **On judgment questions it has no ground truth, so it only gives stable opinions.** Reversing option order changed 7 of 168
   judgment answers, and swapping the full dossier for the core one changed about half, which shows the answers depend on context.

---

## 1. Calibration: 361 electronics questions (739 requests)

| Category | n (q1) | Accuracy [95 % CI] |
|---|---|---|
| d project rules (e.g. Uno PWM pins, RS-485 termination rule) | 42 | **97.6 %** [92.9, 100] |
| c qualitative (strapping pins, I/O limits) | 53 | 84.9 % [73.6, 94.3] |
| b units | 36 | 72.2 % [55.6, 86.1] |
| g comparison | 36 | 69.4 % [52.8, 83.3] |
| a closed-form (RC cutoff, LED current, dissipation, rise time) | 120 | 69.2 % [61.7, 77.5] |
| f multi-step | 38 | 52.6 % [36.8, 68.4] |
| **All answerable** | 325 | 73.8 % [68.9, 78.8] · Brier 0.235 · ECE 0.056 |

**Key experiment: same item, Jev computes vs code precomputes** (paired, q1):

| Subset | Pairs | Jev computes | Value precomputed in state |
|---|---|---|---|
| All numeric | 229 | 66.8 % | **100 %** |
| Near a threshold (1–5 %) | 125 | 52.8 % | 100 % |
| Far from threshold | 104 | 83.7 % | 100 % |
| Qualitative rule recalled vs rule written in state | 53 | 84.9 % | 98.1 % |

All four answers with confidence ≥ 0.9 that were still wrong are numeric edge cases: LED current 9.54 mA vs 10 mA,
9.615 mA vs 10 mA, termination power 0.1276 W vs 0.125 W, and a unit conversion. Unanswerable questions: 18/18
choices abstained with `need_more_information`. Pre-registered hypotheses H1, H2, H4, H5 and H6 held. H3 did not
("compute at conf ≥ 0.9 is below 90 % accurate"): it measured 92.9 %.

## 2. Runtime shadow checks (958 requests)

Would Jev catch a bad LLM output before the deterministic gate? The test seeded faults into IntentIR transcriptions (45),
RFC 6902 patches (26 seeded, 26 faithful) and prompt injections, using real Circuit OS requests.

| Check | Recall on target faults | False flags on faithful | Pre-registered verdict |
|---|---|---|---|
| R1 fields: `stated_<leaf>` P(yes) < 0.9 (unit scale, hallucinated, swapped, wrong board) | 22/27 = 0.81 | 0/40 | advisory |
| R1 function: "is this the function the user asked for?" | 1/12 = 0.08 | 0/40 | shadow |
| R1 unrepresented requirement | 1/6 = 0.17 | 0/40 | shadow |
| R2 patch op faithful @0.9 | 16/20 = 0.80 | 0/22 | advisory |
| R2 coverage (missing op) | 4/4 | 0/22 | advisory |
| Any R1 flag @0.9 | 33/45 = 0.73 | 0/40 | — |

- Leaf-level AUC 0.984 and patch op-level AUC 0.992: Jev's probabilities rank faulty fields above faithful ones almost perfectly.
  A fixed 0.5 threshold still misses many faults, because faults score 0.5–0.9 rather than near 0.
- It is blind to **wrong function** and **out-of-catalogue** requests (it agrees with the recorded function
  in 11 of 12 seeded cases). The deterministic registry refusal already covers those.
- **Injection:** "ignore previous…/approved/system" text did not suppress detection of transcription faults (0 suppressed),
  but did suppress 2/4 patch-op flags, and "flag this" text **provoked** false flags on 3/4 faithful patches. No
  check met the pre-registered bar for *blocking*. The best reach "advisory".

## 3. Robustness and limits (948 requests)

| Experiment | Result |
|---|---|
| E1 `confidence` vs dead options (k = 2…8) | Accuracy 12/12 at every k. Mean confidence moved only 0.985 → 0.995 on these easy items. The formula still means confidence is never thresholded |
| E2 determinism (20-question request × 20) | Choice argmax never flipped. One yes/no flipped once (19 True / 1 False). Probabilities vary by up to 0.11, score expected values by ±0.07. 1/20 answers byte-identical across repeats. Three duplicate questions in one request gave the same argmax, probabilities within 0.04 |
| E3 option order (6 orders in one request) | 74/74 known and 14/14 judgment items same argmax in all orders. P(truth) spread median 0.00, max 0.06 |
| E4 paraphrase (4 states × 4 wordings) | Known: 462/464 correct, 28/29 identical across all 16. Judgment: 3/6 identical |
| E5 polarity (x vs not-x) | 48 pairs, sum median 1.00, 2 off by > 0.15, 1 incoherent |
| E6 authority cue in state | none/neutral/owner-right/URGENT: 100 %. council-wrong 97.7 %. **experts-wrong 86.4 %, owner-wrong 85.2 %** |
| E7 irrelevant project text (10 %–200 %, before/after) | 100 % in every variant |
| E8 batching (alone, in 10, in 50) | Identical answers and probabilities for all 10 targets |
| E9 decisive fact removed | Abstains 24/36 (67 %) when `need_more_information` is offered. Guesses the other 12. With no NMI option it always guesses |
| E10 state size, 8 planted facts | 8/8 choice, 8/8 yes/no, 2/2 absent correct at every size from 1k to 31k tokens |
| Hard limit | ≈ 32.9k **input tokens per request** (state + questions), `400 max_tokens_exceeded` above it. 3,000 questions in one request worked (50k tokens was rejected only by size) |
| Latency | Median 157 ms, p90 396 ms, max 913 ms for small requests. 1.3–1.9 s for a full 29–31k-token dossier request |

The six "lure" sets (`E1c`, `E3h`, `E6h`, `E6j`, `E7h`, `E9h`) were built after registration and were **not** run.
The runner refuses unregistered files, and the protocol stays intact.

## 4. The big file: whole Circuit OS dossier + 257 questions (48 requests)

`dossier/circuit_os_dossier.md` holds 94,613 characters (≈ 27k tokens) covering architecture, rules, phase history,
defeaters, open decisions and the Stage 6 state. It fits in one request with ~4k tokens of questions left over, so the
257-question battery went out as 10 packed requests per variant.

**A. Reading (truth from the text or by construction)**

| | full | full, options reversed | core (25 KB) only |
|---|---|---|---|
| Fact present in the file | **49/49** | 49/49 | 9/9 of those in core. 37/40 of the rest correctly → NMI |
| Fact absent → `need_more_information` | 12/13 | 12/13 | 13/13 |
| Polarity yes/no pairs | 24/24 (sums 0/12 off) | 24/24 | 19/24 |
| Accuracy by position in the file (0–25 / 25–50 / 50–75 / 75–100 %) | 100 / 100 / 100 / 100 % | | |

**B/C. Judgment on the whole project (no truth, so stability and agreement only)**

| Category | n | same answer full vs reversed | agrees with reference / agent prior |
|---|---|---|---|
| One-way vs two-way doors | 16 | 16/16 | reference 13/14 |
| Owner decisions (RS-485 pull-down, X7, D1 timing, proof kind, explainer budget) | 12 | 12/12 | prior 6/9, median p_top 0.59 |
| Same owner decisions as the earlier 2026-09-25 run | 20 | 19/20 | prior 5/8 |
| Phase 2 exit, per defeater | 9 | 6/9 | 3/9 picked NMI; flips on D1, D4, D7 |
| Phase 3 fit | 12 | 11/12 | median p_top **0.37** |
| Priority / risk / self-assessment scores | 80 | 79/80 | about half change when only the core dossier is given |

Reading the table: Jev gives a stable, order-independent opinion on well-framed choices such as doors and owner decisions.
Its confidence is low on Phase 3 and on the owner calls, and it shrinks when context is removed. That makes it a
good *second reader of the project*, not an oracle for the open decisions.

## 5. Dev workflow (1,128 requests)

| Task | n | Jev (orig) | Deterministic baseline | Stable across orig/rev/rep | p_top ≥ 0.9 and stable |
|---|---|---|---|---|---|
| CONV: commit subject convention | 87 | **98 %** | (label is the regex) | 100 % | 81/82 correct |
| T2: CI failure class (infra / accuracy / nondeterminism / unknown) | 50 | **92 %** | 58 % | 100 % | 41/43 correct |
| T4: does this PR need the owner? | 40 | 88 % | **95 %** | 100 % | 34/34 correct |
| T1: does this decisions.md entry cover this commit? | 61 | 62 % | 54 % | 84 % | 8/9 correct |
| T3: doc drift (sentence contradicts a derived fact) | 53 | **85–87 %** | 62–68 % regex | — | real drifts 75 % vs regex 33 % |
| Q: entry quality (0–5) vs checklist | 40 real + 28 degraded | exact 55 %, ±1 72 % | — | — | degraded copy scored lower 28/28 |

T1 fails in a consistent way: it marks unrelated entries as "partially covers" (15 of 23 errors). T4 errs toward
"owner_reserved" on docs-only PRs (3/5 errors), the safe direction, but the path rule is simply better there.

## 6. Phase 3 assurance labels (402 requests, 158 constructed items)

| Label | n | Accuracy | Same answer with options reversed | p_top ≥ 0.9 → correct |
|---|---|---|---|---|
| P3 RS-485 ground-potential / isolation (all 5 questions) | 8–28 | **100 %** | 100 % | 19/19 |
| P4 possibly life-safety | 35 | 91 % | 34/35 | — |
| P2 pollution degree (IEC 60664-1) | 36 | 89 % | 30/36 | 6/6 |
| P4 standard family (60730 / 61010-2-201 / 508A) | 36 | 86 % | 34/36 | 18/18 |
| P2 install environment | 32 | 84 % | 31/32 | 12/12 |
| P1 net role (0–10 V, 4–20 mA, relay, 24 V in, logic) | 48 | 83 % | 47/48 | 34/35 |
| P2 overvoltage category | 36 | **50 %** | 32/36 | 8/8 |

Error patterns: overvoltage category collapses toward OVC II (11 of 18 errors). P1 labels `undeclared` nets with a
guessed role (6/8 errors), and 1 of 4 out-of-enum nets got a wrong role. P4 misses 5 "no life-safety effect" cases in
the unsafe direction for a *negative* claim. R7 (refusal) was not run: its generator fails its own self-check, since item
W02 is accepted by the real registry. That set needs fixing before anyone trusts it.

---

## Where to use Jev in Circuit OS

**Rule of the house (measured, not assumed):** code computes, Jev weighs. Put every number, rule and fact Jev
needs into the state. Ask it to *compare, classify or read*, never to derive. Gate on p_top ≥ 0.9 **and** the same
argmax under reversed options, never on `confidence`. Never let Jev read text an attacker controls when its answer blocks
or approves anything.

| Use | Evidence | Recommended mode |
|---|---|---|
| Read-back of IntentIR vs the user's words (R1 fields @0.9) | recall 0.81, 0 false flags, AUC 0.98 | **Advisory** warning in the UI; never blocking (injection) |
| Patch faithfulness + coverage (R2) | recall 0.80 / 4/4, 0 false flags | Advisory on patch preview |
| CI failure triage (T2) | 92 % vs 58 % regex; 95 % when confident | Label CI failures automatically; the owner decides retries |
| Doc-drift detector (T3) | 85–87 % vs 62–68 % regex; real drifts 75 % vs 33 % | Nightly job that opens a checklist; code facts stay the source |
| Commit-convention / entry-quality lint (CONV, Q) | 98 %; degraded entries always scored lower | Pre-commit hint |
| Phase 3 labels P3, P4 family, P1, P2 pollution | 83–100 %; confident answers 100 % | Pre-fill a label the **user confirms**. Treat `undeclared` as the default when p_top < 0.9 |
| One-way/two-way door and "which rule governs this?" questions over the dossier | 16/16 stable, reference 13/14 | Use in the decision protocol |
| Owner decisions (RS-485 pull-down, X7, D1 timing, …) | stable, but p_top ≈ 0.59 | Owner decides. Jev only frames the options |

**Keep deterministic (Jev measured unfit):** any threshold or numeric derivation (Ohm's law, dissipation, rise time,
divider, units). Overvoltage category (50 %). Function/catalogue membership (8 %; the registry already does it).
Decision↔commit coverage (62 %). Owner-attention routing, where the path rule is better (95 % vs 88 %). Anything gating
on injectable text.

**Protocol changes this run justifies**
1. Drop the "> 0.9 act" band's reliance on a single call. Use reversed options plus one repeat. Order never changed
   an argmax, but probabilities drift ±0.1, so a single 0.91 can be 0.84 the next time.
2. Always include `need_more_information`: without it Jev guesses 100 % of the time on missing facts, and with it 67 %
   of those become abstentions.
3. Strip "owner/experts say" framing from states: it moved 13–15 % of answers to the cued option.
4. Keep requests under ~31k input tokens. The whole dossier fits with room for ~10–40 questions.

## What was not done

- The six lure sets (unregistered) and R7 refusal (broken generator).
- E2 delayed (≥ 1 h) repeats and `jev-latest`/`jev-preview` comparisons.
- A second human author for paraphrases. The paraphrases were written by the same agent that wrote the items.
- Accuracy on judgment questions is unknowable here. The report shows only stability and agreement with priors.

## Reproduce

```bash
pip install typesafe-sdk==0.7.1         # needs TYPESAFE_API_KEY
python tools/jev/interrogation/calibration/analyze.py
python tools/jev/interrogation/runtime/analyze.py
python tools/jev/interrogation/robustness/analyze.py
python tools/jev/interrogation/dossier/build_battery.py && python tools/jev/interrogation/dossier/run_battery.py && python tools/jev/interrogation/dossier/analyze_battery.py
python tools/jev/interrogation/devflow/analyze.py
python tools/jev/interrogation/labels/run_and_analyze.py --analyze-only
```
