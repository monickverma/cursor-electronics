# Jev (TypeSafe AI) as a decision instrument: API, reading its outputs, request design, audit of Circuit OS's Jev decisions, and a better protocol

Method note (read first). As of 2026-09-25. **No live Jev calls were possible.** api.typesafe.ai, typesafe.ai and docs.typesafe.ai are blocked by the egress proxy, so no output below comes from a new call. Several third-party blogs were blocked too (primeline.cc, anth.us, alexmolas.com, flaviocopes.com). Sources, from most to least reliable:
(a) **First-party SDK source**: `typesafe-sdk` 0.7.1 wheel downloaded from PyPI and read locally at `scratchpad/sdk/typesafe_sdk/…`. Paths below are relative to `/tmp/claude-0/-home-user-cursor-electronics/d7f1ec44-0d48-5872-8bcf-575641baec98/scratchpad/sdk/`.
(b) **Repo snapshot** `scratchpad/p2` (origin/phase2-stage0 @ e803a99), cited as file:line.
(c) **Independent GitHub studies**, read through a fetched README or catalog page.
(d) **Search-result summaries**, marked *(search summary only)*.
The prior note `research_notes/JEV decision use in Circuit OS/jev_typesafe_ai.md` was the starting point. Its SDK facts were re-verified against the 0.7.1 wheel.

---

## 1. API surface: what the SDK says Jev takes and returns

### Takeaway
Jev has one decision endpoint (`POST /v1/systemone`). A request is one `state` (text, a JSON object or an array) plus a non-empty map of named questions. Each question is a **Noul** (yes/no probability), a **Choice** (one label from a fixed set, each label optionally with a description) or a **Score** (an ordered rubric, levels starting at 0). All questions in a request are answered against the same state. The request has no temperature, seed, n-samples, top-k or explanation field. The output is numbers only: no rationale is returned.

### Cited Findings
- Endpoints: `SYSTEM_ONE_PATH = "/v1/systemone"`, `MODELS_PATH = "/v1/models"`. Default base URL `https://api.typesafe.ai`. Default model `"jev-latest"`. Default timeout 10 s. Env vars `TYPESAFE_API_KEY`, `TYPESAFE_BASE_URL`, `TYPESAFE_DEFAULT_MODEL`, `TYPESAFE_LOG_LEVEL` — `typesafe_sdk/_core/constants.py`, `typesafe_sdk/constants.py:9-22` — [PyPI typesafe-sdk 0.7.1](https://pypi.org/project/typesafe-sdk/)
- Request schema: `state` ("The content all questions in this request refer to"), `model` ("Name or alias … Available names are returned by GET /v1/models"), `questions` (min_length=1; "each with a name you choose") — `typesafe_sdk/_schemas/models.py:196-215` — [PyPI](https://pypi.org/project/typesafe-sdk/)
- **Noul question**: `instructions` ("The yes/no question or statement to evaluate") plus optional `criteria: {true, false}` ("What counts as a yes answer" / "…a no answer"). **NoulAnswer.noul**: "Probability of a yes answer or a true statement, from 0 to 1 … values near 0.5 indicate uncertainty." A Noul has **no confidence field** — `models.py:74-104`
- **Choice question**: `instructions` ("What the model should decide when choosing an option") and `criteria`: "Choice names and descriptions of when each applies. A choice without a description is interpreted by its name alone." **ChoiceAnswer**: `choice` (the highest-probability label), `confidence` ("from 0 to 1 … use lower values to flag uncertain selections for review"), `probabilities` per label, which "sum to approximately 1" — `models.py:10-50`
- **Score question**: `criteria` is an "Ordered [list of] descriptions of the score levels. Each description's position determines its score, starting at zero" (min_length=1). **ScoreAnswer**: `score` = "the probability-weighted average of the rubric levels. May fall between integer levels", plus `confidence`, `legend` and per-level `probabilities` (integer keys in the SDK wrapper) — `models.py:106-148`; `_core/response_types.py:44-58`
- Descriptions can be text, a JSON object or an array, for Noul outcomes, Choice labels and Score levels — `_core/question_types.py:15-62`
- Response: `model` ("Name of the model that answered the questions. **May differ from the alias supplied in the request**"), `answers` keyed by question name, `usage` {input_tokens, output_tokens; "Output tokens are currently free of charge"} — `models.py:150-160, 218-235`
- Client call: `system_one(state, questions, *, model=None, retry=None, timeout=None, extra_headers=None, extra_body=None, response_model=None)`. Sync `TypeSafeClient` and async `AsyncTypeSafeClient` exist. `response_model` lets the caller parse into its own type — `_core/client/sync/client.py:102-151`; `_core/client/aio/client.py`
- Retries: by default the SDK retries up to 2 times after the first attempt on HTTP 408, 429 and 5xx, and on connection and timeout errors, honouring `Retry-After`. The response header `x-typesafe-request-id` is exposed — `_core/retry.py:52-74`; `_core/constants.py`
- PyPI lists versions 0.5.7, 0.6.0, 0.7.0 and 0.7.1 (`pip index versions typesafe-sdk`, run 2026-09-25). The METADATA says "Development Status :: 5 - Production/Stable" — `typesafe_sdk-0.7.1.dist-info/METADATA:3,11`
- Model naming: the project recorded `jev-1.13.0` (`p2/.claude/shared-memory/brain/decisions.md:1434`). One independent study reports every response identified as "jev-1.13.0" on 16–17 Sept 2026 — [RINNECODER/jev-behavior-study](https://github.com/RINNECODER/jev-behavior-study). Another reports `typesafe/jev-1.13-20260917` on 20 Sept 2026 — [priorbench/jev](https://github.com/priorbench/jev). The model list example shows only `jev-latest` with release_date 2026-09-15 — `models.py:61-68`
- Limits: up to 255 options per Choice. Above that, TypeSafe suggests a two-stage approach (score candidates, then choose) *(search summary only)* — [docs.typesafe.ai/primitives/choice](https://docs.typesafe.ai/primitives/choice) (blocked; seen via search). The community `jev` package states 255 options per choice and 256 levels per score — [PyPI jev](https://pypi.org/project/jev/). About 32k tokens per state+question branch and 65k per request *(third-party summary, from prior notes)* — [MindStudio](https://www.mindstudio.ai/blog/jev-system-one-model-launch)
- Batching: several questions in one request cost 34.7% less and returned 49.4% faster than separate requests. The distribution shift from batching was mean JS distance 0.0058, against 0.0035 between identical separate requests — [xxlya/evaljev](https://github.com/xxlya/evaljev). Bundling questions moved confidence by 0.008 — [jujumilk3/jev-calibration-audit](https://github.com/jujumilk3/jev-calibration-audit)

### Inferences
- **Model identity drifts.** An alias can resolve to a different model than the one requested, and the dated build string changes (`jev-1.13.0` vs `jev-1.13-20260917`). A decision record must store the returned `model` string and the `x-typesafe-request-id`, not the requested alias.
- There is no sampling control. Stability can only be measured by repeating calls or perturbing inputs (section 4).
- Jev returns no rationale. Every "why" in a decision entry is the agent's own reasoning, not Jev's.

### Gaps
- The SDK does not compute confidence; it arrives from the server. Its formula is not in the SDK source (see section 2).
- Official rate limits and the full model list could not be read (docs blocked).

---

## 2. How to read the outputs: probabilities, confidence, calibration

### Takeaway
**Choice confidence is a deterministic transform of the top probability and the number of options *k***: c = (p_max − 1/k)/(1 − 1/k) = (k·p_max − 1)/(k − 1). It is not a separate uncertainty signal. The same p_max gives a *higher* confidence when options are added, even options that get 0.00. Circuit OS's own recorded numbers match this formula **only if each of its two Choices had four options, but the log lists three**. That strongly suggests an unlisted fourth, near-zero option inflated both recorded confidences. Raw probabilities are not reliably calibrated outside Jev's home domain (routing and classification). On reasoning and quantitative tasks they can be confidently wrong. Thresholds should use top-p, the margin to the runner-up, and agreement across perturbed calls, not `confidence`.

### Cited Findings
- Formula: "Choice confidence is (N·p_max − 1)/(N − 1), not separate signal" (pre-registered test) — [primeline.cc](https://primeline.cc/blog/typesafe-jev-pre-registered-test), via the catalog at [awesome-jev-robustness](https://github.com/Yifan-Lan/awesome-jev-robustness) (primeline itself blocked). Also: "c = (p_max − 1/k)/(1 − 1/k) … a normalized margin over a uniform prior", and confidence "is not portable across different option counts". At k=2, c<0.55 ⇔ p_max<0.775. At k=10, c<0.55 ⇔ p_max<0.595. "Adding a single option … moves every threshold keyed on confidence, with no model or code change" — [xxlya/evaljev](https://github.com/xxlya/evaljev)
- Vendor framing: confidence is "computed from the shape of probabilities: concentrated on one option means high, spread out means low" *(search summary only)* — [flaviocopes deep dive](https://flaviocopes.com/jev/); [docs Choice page](https://docs.typesafe.ai/primitives/choice)
- **Local check against the project's numbers** (computed here, `python3`). `rc_option` had p = {0.87, 0.13, 0.00} and recorded confidence 0.83. `led_option` had p = {0.58, 0.36, 0.06} and recorded confidence 0.44 (`decisions.md:1447-1450`). With k=3 the formula gives 0.805 and 0.37, outside rounding error (±0.008) of the recorded values. With **k=4** it gives **0.827 and 0.44**, matching both. The prior audit's claim ("confidence = top probability rescaled by option count, so dead options inflate it") is therefore consistent with the formula and with the project's data. It points to a fourth option per Choice that the decision table omits.
- Score confidence: no independent formula found — [xxlya/evaljev](https://github.com/xxlya/evaljev) ("does not provide a separate formula … for Score")
- **Calibration is domain-dependent.** On support routing ECE was 0.075 (jev-1.13.0, 123,805 requests, pre-registered). On random 3-SAT the model said "satisfiable" for nearly every formula: probabilities varied by 0.026 while ground truth varied by 1.000. It gave P(satisfiable)=0.38 for `x AND NOT x`. Confidence AUROC was 0.878 overall but 0.699 within a single condition — [willkelly/jev-evaluation](https://github.com/willkelly/jev-evaluation)
- Overconfidence: Noul stated 79.0% vs 72.3% actual. Choice stated 91.4% vs 76.1% actual. The 50–95% confidence band was only 50–57% correct. Isotonic regression brings ECE from 0.117 to 0.008 — [AnthusAI/Jev-Calibration](https://github.com/AnthusAI/Jev-Calibration); [anth.us](https://anth.us/blog/can-you-trust-jev-confidence) (via catalog)
- "Accuracy above threshold is flat from 0.50 to 0.95, then jumps to 100% at 0.99 … Gate at 0.99 or not at all" (jev-1.13-20260917, 5,721 calls, pre-registered) — [priorbench/jev](https://github.com/priorbench/jev)
- A fair die: Choice put 82.9% on its pick at 19.0% accuracy, while independent Nouls stayed near 1/6 per face — [KantaHayashiAI/jev-does-not-play-dice](https://github.com/KantaHayashiAI/jev-does-not-play-dice); Choice bias grows with option count — [TakumiNoguchi2004/jev-noul-vs-choice](https://github.com/TakumiNoguchi2004/jev-noul-vs-choice) (via catalog)
- Noul vs two-option Choice on the same judgment: mean absolute gap 0.125, over 0.2 on one item in six. P(x)+P(not x) averages 1.02 but ranges 0.71–1.42 — [jujumilk3/jev-calibration-audit](https://github.com/jujumilk3/jev-calibration-audit)
- Other results point the other way. "High-confidence answers correct 492 of 493 times" on static logic, but 13.2% on sequential state mutation and 33.3% on exact counting — [etsabary/jev-deterministic-benchmark](https://github.com/etsabary/jev-deterministic-benchmark) (via catalog). "Overconfident in low bands but calibrated above 0.9" — [dopeCape/typesafe-ai-test](https://github.com/dopeCape/typesafe-ai-test) (via catalog)
- The vendor's example thresholds are 0.5 as a review floor and 0.9 before a destructive action, "as examples, not defaults". Boundaries should depend on what a wrong answer costs *(search summary only)* — [sidbharath guide](https://sidbharath.com/blog/the-complete-guide-to-jev/); [eesel review](https://www.eesel.ai/blog/typesafe-jev-review). This is the source of Circuit OS's ">0.9 act, 0.5–0.9 care, <0.5 person" rule (`decisions.md:1436-1437`).

### Inferences
- **Do not threshold on `confidence`.** It is p_max rescaled by k, so a threshold on it silently changes whenever an option is added or removed. Use p_max, the margin p1−p2, and stability across calls, and always record k.
- The 0.5–0.9 "act with care" band is the least trustworthy region in several independent studies (flat accuracy, 50–57% correct). Treat it as weak evidence that can only *break a tie* in the agent's own analysis, never as a reason to act on its own.
- Circuit OS's questions are engineering trade-offs that carry numbers (mA, mW, Ω, percentages). Maths, counting and multi-step reasoning are Jev's documented failure zone, where its calibration collapses. The numbers must be computed by tools and given to Jev as facts. Jev should only weigh already-computed consequences.
- A Noul and a Choice asking the same thing can disagree by about 0.1–0.2. Circuit OS's LED answers show exactly this (section 3).

### Gaps
- No calibration data exists for Jev on *engineering design trade-off* questions, and no labelled set from Circuit OS exists. The probabilities are uncalibrated for this use.
- Not verified from a primary TypeSafe page: primeline and the docs were blocked. The formula rests on two independent derivations plus this note's arithmetic check.

---

## 3. Audit of Circuit OS's Jev-settled decisions (snapshot p2 @ e803a99)

### Takeaway
The snapshot records **four** Jev consultations. Only **one** (2026-09-23, RC swamping + LED bound) is logged with questions and probabilities, and even that one cannot be reproduced: the request script lives in a session scratchpad and a Choice option appears to be missing from the table. Both chosen actions **were implemented**, and the tests pin them. The RC call (top-p 0.87, "act with care") was acted on with care, i.e. independent checks. The LED call (confidence 0.44) was **decided by the agent**, not a person. At the time this broke the protocol as written in that same entry ("<0.5 a person should decide"). The agent softened it by choosing the reversible status quo and saying the user may overrule. The protocol text in the handoff later added "or take the most reversible option and say so", which retroactively covers it. The two 2026-09-21 "TypeSafe passes" and the D1/D2/D7 uses named in the handoff have no recorded questions or numbers in the snapshot, so they cannot be audited.

### Cited Findings (repo)
- **Grep result.** Jev/TypeSafe appears only at `brain/decisions.md:769, 1038, 1431-1475`; `plan/current_phase.md:348, 658`; `backend/generators/rc_lowpass.py:59`; `tests/test_rc_lowpass_generator.py:477`. No `typesafe` import or dependency exists anywhere in the snapshot, so Jev is used only by the agent, as a development-time adviser.
- **[2026-09-21] X2 + X4** (`decisions.md:760-775`): "The five-advisor council review of X2/X4 and two TypeSafe (Jev) passes found the direction right and the amendments under-specified." No state, questions, probabilities, model string or script is recorded. `current_phase.md:348` says "fifteen gaps the council and TypeSafe reviews found". **Unauditable.** This is also a questionable use: "find gaps in a spec" is a generative task, and Jev can only answer fixed Noul/Choice/Score questions, so the gaps must have come from the agent's own questions or the council. The log does not say which.
- **[2026-09-21] X6 + X8** (`decisions.md:1033-1039`): "after the council verdict on X6/X8 and the TypeSafe pass that flagged X8 as due earlier than Stage 3". No numbers are recorded. **Unauditable.** The action (X8 in Stage 3) was taken.
- **[2026-09-23] RC source swamping + LED bound** (`decisions.md:1431-1475`):
  - Setup: "put to TypeSafe (Jev, `jev-1.13.0`) with the whole scenario as state, on the user's instruction ('give it the whole scenario and then make the decision')". The state was about 10.6k characters, containing history, measured facts and "every option with its benefits and costs side by side". Script `typesafe_rc_led.py` is in the "session scratchpad", not the repo. The questions were "two Choices and three Nouls" (`:1433-1444`).
  - Raw answers (`:1446-1452`): `rc_option` swamp 0.87 / refuse 0.13 / compensate 0.00, conf 0.83. `led_option` conservative_now_exact_later 0.58 / exact_now 0.36 / keep_conservative 0.06, conf 0.44. Nouls: `rc_refusal_blocks_common_requests` 0.62, `led_loss_is_material` 0.26, `led_grade_upgrade_worth_doing_now` 0.47.
  - Protocol stated in the entry: ">0.9 act, 0.5–0.9 act with care, <0.5 a person should decide" (`:1436-1437`).
  - RC action: "implemented, rc_lowpass 0.2.3", with the agent's own checks: "designs that pass today do not change (0 of 36 checked)" (`:1454-1466`). **Verified in code:** `backend/generators/rc_lowpass.py:51-59` (docstring), `:101` `VERSION = "0.2.3"`, swamp logic `:207-243`. Tests: `tests/test_rc_lowpass_generator.py:466-470` (`dependency_closure("constraints.source_impedance_ohm") == {R1, C1}`), `:477`.
  - LED action: "Confidence 0.44 is below TypeSafe's own threshold for acting, so the agent decided, taking the reversible option … **The user may overrule**" (`:1467-1475`). Scheduled as Task 4.5 (`current_phase.md:658-672`). **Then implemented the next day**: `decisions.md:1645-1660` ("Scheduled at [2026-09-23]; done before Stage 5 lands"), led_indicator 0.1.2, `r1_power_max_w` at `backend/generators/led_indicator.py:187`, `series_power` `unless` guard at `backend/proof/prover.py:86,110-122`. The code is now `VERSION = "0.2.0"` (`led_indicator.py:108`) after Stage 5.
- **D1/D2/D7 via Jev** (handoff §3): "TypeSafe (Jev) … has been used to settle judgement calls (RC source swamping, D1/D2/D7)". The snapshot's `decisions.md` ends at line 1728 ([2026-09-24] Task 4.5 amended). The D2 commit 94b61c1 and the "D1 evidence records decided 2026-09-24" are not in the snapshot. **Not auditable here.**

### Protocol-compliance table (the one auditable consultation)

| Question | Recorded | Recomputed signals | Band (stated protocol) | What the agent did | Assessment |
|---|---|---|---|---|---|
| rc_option | top 0.87, conf 0.83 | margin 0.74. k=3 → conf 0.805; k=4 → 0.827 (matches) | 0.5–0.9 act with care (top-p and conf agree) | Acted after independent checks (0/36 designs change, tests, closure widened) | **Compliant.** The care was real and checkable. |
| led_option | top 0.58, conf 0.44 | margin 0.22. k=3 → 0.37; k=4 → 0.44 (matches) | By conf: <0.5 → person. By top-p: 0.5–0.9 care. | Agent decided itself, chose the status quo, flagged "user may overrule" | **Deviation from the text as written** ("a person should decide"). Mitigated by reversibility and disclosure. The later protocol wording legitimises it. The chosen label "conservative_now_exact_later" was then carried out in full (exact done 24 Sep). |
| rc_refusal_blocks_common_requests | 0.62 | — | care | Background only | Weak evidence. Not used as a gate. OK. |
| led_loss_is_material | 0.26 | P(no)=0.74 | care (for "no") | Read as "do not matter to users" | Treated 0.74 as settled, though it sits in the unreliable band. The agent also had the numbers (16.3–16.5 mA, 62.0 mW), which is better evidence than the Noul. |
| led_grade_upgrade_worth_doing_now | 0.47 | — | <0.5 / coin flip | Read correctly as a coin flip | OK |

Internal inconsistency in the LED answers: the Choice gives P(exact_now) = 0.36, but the Noul "worth doing now" gives 0.47, a gap of 0.11. That fits the documented Noul-vs-Choice gap of about 0.125 ([jujumilk3](https://github.com/jujumilk3/jev-calibration-audit)). Neither number should be read to two decimals.

### Inferences
- **Reproducibility is the biggest failure, not the thresholds.** None of the four consultations can be re-run from the repo. There is no committed script, state text, raw JSON, returned `model` or request id. Under the project's own trust order (tests > source > … > brain/*.md > prose), Jev's contribution is recorded only as prose.
- **The missing fourth option matters.** If each Choice had a fourth, near-zero option (for example "ask the user" or "none"), confidence was inflated: LED 0.37 → 0.44, RC 0.805 → 0.83. It did not change a band here. But LED at k=3 would sit even further below 0.5, and a future dead option could push a borderline answer across 0.9.
- **Framing risk.** One agent wrote the state ("every option with its benefits and costs side by side"), asked the questions, and then acted. The RC state reportedly already said compensation "changes every design" and depends on an unverified value. Jev's 0.00 for "compensate" may just echo that framing. No order swap, paraphrase or neutral-author check was run.
- **Competence mismatch.** Both questions involve quantitative engineering (tolerance bands, mW margins). Jev's calibration is weakest on maths and multi-step reasoning ([willkelly](https://github.com/willkelly/jev-evaluation); [etsabary](https://github.com/etsabary/jev-deterministic-benchmark)). The decisions held up because the agent computed the physics itself and used Jev only to weigh values such as reversibility, user impact and effort. That is the right split, and it should be written down as a rule.
- Outcome check: both acted-on choices were built, tested and kept. Neither has been reversed in the snapshot. That supports the decisions, not Jev's calibration: one outcome per question is no calibration evidence.

### Gaps
- `typesafe_rc_led.py` and the raw responses are not in the repo, so the fourth option, exact wording, label order and descriptions cannot be checked.
- D1/D2/D7 consultations and the two 2026-09-21 passes have no recorded data in the snapshot.

---

## 4. Request design: how to write the state and questions

### Takeaway
The wording of the criteria is the single largest lever on Jev's accuracy. Give every option a one-line description of when it applies. Always include an explicit abstain or insufficient-information option. Ask one decision per question and split compound ones into separate Nouls. Put the computed facts in the state, not reasoning Jev must do. Counterbalance: repeat the call with label order reversed and a paraphrased state, and act only when the argmax holds. Keep the state short and put the key facts early, because long, diluted context degrades lookup.

### Cited Findings
- Rewriting the criteria moved paired accuracy from 70% to 96% and from 83% to 100%, the "largest lever found" — [RastislavDujava/jev-classification-prompting](https://github.com/RastislavDujava/jev-classification-prompting). Accuracy went from 83% to 100% "once criteria spelled out [the] boundary", and "criteria matter more than question" — [SYED-M-HUSSAIN/jev-experimental](https://github.com/SYED-M-HUSSAIN/jev-experimental). Wording of criteria alone flipped behaviour across a whole population — [tfolkman/jev-village](https://github.com/tfolkman/jev-village) (all via [catalog](https://github.com/Yifan-Lan/awesome-jev-robustness))
- A router whose options had names but no descriptions sent all 40 hard tasks to the cheap model at median confidence 0.96. One-line option descriptions fixed 37 of 40 *(search summary only)* — [awesome-jev-robustness](https://github.com/Yifan-Lan/awesome-jev-robustness) / search
- **Abstain option:** removing it took accuracy on unanswerable items from 0.950 to 0.000, with confidence staying at 0.79 and ECE going from 0.023 to 0.793 — [jujumilk3](https://github.com/jujumilk3/jev-calibration-audit). "0 of 30 out-of-scope messages were flagged — at 0.99 confidence" without an explicit none option — [priorbench/jev](https://github.com/priorbench/jev). Mean abstention F1 was 0.855 when abstention is offered — [sshariqali/jev-abstentionbench](https://github.com/sshariqali/jev-abstentionbench) (via catalog)
- **Option order: evidence conflicts.** On arithmetic, accuracy was 88.0% with the correct option first and 57.4% with it last (jev-1.13.0) — [RINNECODER/jev-behavior-study](https://github.com/RINNECODER/jev-behavior-study). In contrast, "Reversing two options moved probability by 0.005 and flipped 0 of 400 argmaxes" on classification — [jujumilk3](https://github.com/jujumilk3/jev-calibration-audit). Adding an unrelated candidate shifted log-odds between untouched options by 0.31–0.50 — [123Satyajeet123/jev-wide](https://github.com/123Satyajeet123/jev-wide) (via catalog)
- Wording: changing "5-minute walk" to "5-minute drive" flipped 0/20 correct to 20/20 correct. Long context: accuracy fell from 6/6 to 1/6 when target facts sat mid-document at scale — [RINNECODER](https://github.com/RINNECODER/jev-behavior-study). Paraphrase moves answers as much as negation — [jujumilk3](https://github.com/jujumilk3/jev-calibration-audit)
- Repeat stability: 15 distinct responses in 50 identical requests — [jujumilk3](https://github.com/jujumilk3/jev-calibration-audit). Probabilities 0.03–0.04 apart across five identical calls — [copyleftdev/jev-labs](https://github.com/copyleftdev/jev-labs). Repeats shifted probability by up to 0.13 — [vianaR25/jev-vs-ml](https://github.com/vianaR25/jev-vs-ml). But "Jev repeats every verdict" (argmax) — [orq-ai/jev-judge](https://github.com/orq-ai/jev-judge) (all via catalog)
- Injection and authority: crude injections succeeded on 1/200, but authority-based attacks on 147/200 — [willkelly](https://github.com/willkelly/jev-evaluation). Accuracy fell from 96.5% to 26.5% under a one-line injected instruction — [zkousama/jagged](https://github.com/zkousama/jagged) (via catalog). **Relevance:** a state that says "the user said X" or "the council concluded Y" is an authority cue that can steer the answer.
- A state-blind control (options with no context) scored 0.38–0.46 against about 0.15 chance, so option wording alone carries a lot of signal — [jujumilk3](https://github.com/jujumilk3/jev-calibration-audit)
- Known weaknesses: over-literal instructions, no reliable counting, weak maths and date comparison, multi-layer indirect reasoning, context rot, text-only input *(search summary only)* — [awesome-jev-robustness](https://github.com/Yifan-Lan/awesome-jev-robustness); [MindStudio](https://www.mindstudio.ai/blog/jev-system-one-model-launch)
- Language: Russian 77.3% vs English 88.3% — [AHTOOOXA/jev-cyrillic-audit](https://github.com/AHTOOOXA/jev-cyrillic-audit) (via catalog). Not relevant here, since Circuit OS is English.

### Inferences (concrete rules for Circuit OS requests)
1. **State = facts, not advocacy.** Use structured JSON: `decision`, `context`, `constraints` (invariants that cannot be broken, e.g. "an accepted design never carries a failing claim"), `measured_facts` (tool-computed numbers with units and source file:line), `options[]` (each with the same fields: what changes, what is reversible, blast radius, cost), `unknowns`. Give every option the same length and form. Drop adjectives ("clean", "risky"), "the user wants…", and council verdicts, because these are authority cues.
2. **Descriptions on every label and on both Noul outcomes.** State the boundary ("choose X when …; not when …").
3. **Always add `insufficient_information`** (or `needs_owner_judgement`) as a described option, and **record k**. Do not add dead options for any other reason.
4. **One decision per Choice.** Split compound questions ("keep now and do exact later?") into sequential Nouls: "Is the current behaviour acceptable to ship now?" and "Is the upgrade worth doing before Stage N?"
5. **Ask both polarities** for key Nouls (x and not-x). If P(x)+P(¬x) is not within 1±0.15, treat the answer as unstable.
6. **Counterbalance with at least 3 variants:** original, labels reversed, state paraphrased by a different author or agent. Optionally add a state-blind control (options only) to see how much is just option wording. Batching variants in one request is cheap and shifts answers little (JS 0.006).
7. **Keep the state under about 3k tokens with the decisive facts first.** The 10.6k-character RC/LED state (about 2.6k tokens) was fine.
8. **Never ask Jev to compute.** mA, mW, tolerance and "does X break Y" are for predict(), z3 or ngspice. Jev weighs consequences that are already computed.

### Gaps
- No study tests Jev on multi-option *engineering-policy* decisions like Circuit OS's, so the order and paraphrase sensitivity for this task type is unknown and should be measured when calls are possible.

---

## 5. Independent evidence on accuracy and calibration: summary and caveats

### Takeaway
Jev performs well on narrow classification and routing and resists crude injection, and its argmax is repeatable. Its probabilities are often overconfident in the middle band, collapse on reasoning tasks, and depend on option count and format. Almost all evidence comes from one-person GitHub studies in the two weeks after launch, some of them pre-registered. It is useful but thin, and some of it conflicts.

### Cited Findings
- Vendor claims of 193.6× faster and 444.6× cheaper came from its own evals. Independent checks found about 4–7× faster and 31–65× cheaper *(search summary only, prior note)* — [DEV Community](https://dev.to/arifulislamat/typesafes-jev-model-is-it-really-193x-faster-and-444x-cheaper-56oa)
- "Level with mid-price LLMs, behind the frontier" after eight days of independent tests *(search result title only)* — [DEV Community gde](https://dev.to/gde/jev-after-eight-days-of-independent-tests-level-with-mid-price-llms-behind-the-frontier-1kln)
- Most independent tests "were run in the two weeks after Jev's release … usually by one person with a small budget" *(search summary only)* — [awesome-jev-robustness](https://github.com/Yifan-Lan/awesome-jev-robustness)
- The most injection-resistant of four classifiers tested (flipped on 0.09% of 1,056 attacks) — [cwhy/decision-injection-bench](https://github.com/cwhy/decision-injection-bench) (via catalog); contrast with authority attacks at 147/200 — [willkelly](https://github.com/willkelly/jev-evaluation)
- A few hundred labelled examples are enough to fit Platt or isotonic recalibration *(search summary only)* — [KDnuggets](https://www.kdnuggets.com/what-everyone-is-getting-wrong-about-typesafe-ais-jev); isotonic regression removed 96% of error — [Adilmp/does-jev-confidence-mean-anything](https://github.com/Adilmp/does-jev-confidence-mean-anything) (via catalog)
- An argument that Jev "can't be calibrated" in general, so its outputs should be treated as scores *(search result title/summary only; page blocked)* — [alexmolas.com](https://www.alexmolas.com/2026/09/23/jev-cant-be-calibrated.html)

### Inferences
- For Circuit OS's rare, one-off design-policy decisions, recalibration is impossible because there are no labels. Read Jev as an **ordinal, stability-tested second opinion**, not as a probability of being right.

### Gaps
- There is no independent evaluation on electronics or engineering-design content.

---

## 6. Improved, repeatable decision protocol (proposal for `.claude/shared-memory`)

### Takeaway
Keep the three-band spirit, but (a) decide first whether Jev is allowed to weigh in at all, (b) base the bands on top-p, margin and cross-variant stability instead of `confidence`, (c) make every consultation a committed, re-runnable artifact, and (d) make "agent decides under uncertainty" an explicit, logged fallback that is allowed only for reversible options.

### Inferences (the protocol, derived from sections 1–5)

**Step 0: Is this a Jev question?**
- *Never Jev:* anything that computes physics, a number, or pass/fail (predict/z3/ngspice/tests own it). Anything that would override the One Rule, tool_use or IR rules, or a gate. Items the owner has reserved (handoff §7: RS-485 DE/RE pull-down, live pricing X7, bench/D1 and D7 timing, `kind` on proofs, explainer max_tokens). **Jev may raise scrutiny, never lower it.**
- *Jev-eligible:* choosing among already-analysed options on values such as reversibility, user impact, scheduling and effort, where the facts are computed and supplied.
- Classify the decision as a **one-way door** (irreversible: changes stored or signed data, hashes, public API or a generator's accepted set) or a **two-way door**.

**Step 1: Build the request (a committed file, not a scratchpad).**
- `tools/jev/<date>_<slug>.py` plus `<slug>.state.json`, following the section 4 rules: factual state, described labels, an `insufficient_information` option, one decision per Choice, both-polarity Nouls, no authority cues.
- Pin the model string. Record the SDK version.

**Step 2: Run the variants.** At least 3: original, reversed labels, paraphrased state (written by a second agent or from a neutral template). If budget allows, add 2 identical repeats and 1 state-blind control. Store raw JSON, returned `model`, `x-typesafe-request-id`, `usage` and the date in `tools/jev/<slug>.results.json`.

**Step 3: Compute signals (do not use `confidence`).** For each Choice: `k`, the p_top range across variants, `margin` = p1−p2 (minimum across variants), and `argmax_stable` (same label in every variant). Also P(insufficient_information), the Noul polarity sum, and Noul-vs-Choice coherence.

**Step 4: Bands.**

| Band | Condition (all must hold) | Action |
|---|---|---|
| **Act** | argmax stable; min p_top ≥ 0.90; min margin ≥ 0.60; P(insufficient) < 0.05; coherent Nouls; agent's independent analysis agrees | Act. Log it. For a one-way door, still tell the owner. |
| **Act with care** | argmax stable; min p_top ≥ 0.60; min margin ≥ 0.25; agent's independent analysis agrees | Act only on a **two-way door**, with named checks (tests, 0-of-N regression scan, negative control) listed before code, and a review trigger. For a one-way door, go to the owner. |
| **Owner decides** | anything else: argmax flips, margin < 0.25, P(insufficient) is the top or ≥ 0.2, incoherent, or Jev disagrees with the agent's analysis | Present options to the owner. If the owner is unavailable and the work cannot wait: take **the most reversible option** (usually the status quo), log it as `agent_decided_under_uncertainty`, add "owner may overrule" plus a dated trigger to revisit, and never take a one-way door. |

(These thresholds are set conservatively because independent studies find the 0.5–0.95 band unreliable ([priorbench](https://github.com/priorbench/jev); [AnthusAI](https://github.com/AnthusAI/Jev-Calibration)). They are a proposal, not calibrated values.)

**Step 5: Decision entry fields** (appended before code, per the project rule): question file path, model string and request ids, a k/p_top/margin/stability table, the band, the action, who decided (Jev-supported / agent-under-uncertainty / owner), the reversibility class, and the review trigger. Put a Jev citation in code comments only when the decision entry has these fields.

**Step 6: Retrospective.** Tag each Jev-settled decision with a later outcome (kept / reversed / defect found). After about 30 decisions, check whether the Act band held. This is the only calibration Circuit OS can get.

**Applied retroactively (from the 2026-09-23 numbers alone, one variant only):**
- RC: margin 0.74, p_top 0.87, one variant only, so **Act with care** on a two-way door (generator version bump; old designs unchanged). The outcome matches what was done.
- LED: margin 0.22, so **Owner decides**. The fallback (reversible status quo, flagged) is what the agent did. Under the new protocol it would be labelled `agent_decided_under_uncertainty`, not "decided with TypeSafe".

### Gaps
- The thresholds cannot be validated without live calls and outcome data.
- Whether the owner wants Jev consultations committed to the repo (key handling: the key is a Windows user env var per handoff §3) is the owner's decision.
