# Criterion 12 — External Engineer Review

> The last open Phase 1 criterion. Open since 2026-06-02.
>
> **What is being tested is the explainer, not the reviewer.** Every rule below
> exists to stop you from accidentally supplying the understanding you are trying
> to measure.

---

## 0. The one rule

**Say nothing.** No framing, no context, no "does this make sense?", no
apologising for length, no "it's a first draft". The moment you explain anything,
the test is void — you cannot tell afterwards whether they understood the
document or understood you.

Paste the text. Ask the questions in §3. Stay quiet.

---

## 1. Produce the artefact

```
"Arduino reads DHT22 and alerts above 30°C"
```

Run it through the live pipeline and copy the explanation **verbatim**. Do not
tidy it, reorder it, or fix a typo.

**Record which model produced it.** `AI_MODEL` in `.env` is currently
`anthropic/claude-opus-5`; `config.py` defaults to `claude-sonnet-4-6`. These
differ, so "the explainer passed review" is meaningless without naming the model
that wrote the words the reviewer read. Put the model ID and the date at the top
of your notes file — not in the document you hand them.

Save the exact text you sent. If the reviewer fails you need to know precisely
what they were looking at.

---

## 2. Recruiting

You need someone who can read a schematic and has **not seen this project**.
That is the whole specification. It does not need to be a stranger, a
professional, or someone senior.

At KIIT, in rough order of speed:

1. **A final-year EE student.** Fastest path. Ten minutes over coffee.
2. **A faculty member** in electronics or instrumentation. Slower to schedule,
   more authoritative if you ever cite the result.
3. **The electronics/robotics club.** Several candidates in one room.
4. **Asynchronous fallback** — r/AskElectronics or the EEVblog forum. Post the
   explanation and the questions, nothing else. Slower and noisier, but it works
   when local options stall, and it is genuinely blind.

**Get three, not one.** The criterion says one. One tells you almost nothing —
a single confused reader might be a bad explanation or a distracted afternoon.
Three costs thirty minutes total and turns a coin flip into a signal.

---

## 3. The protocol

1. Send the explanation with **no preamble**.
2. "Take ten minutes with this, then I have two questions."
3. After ten minutes, ask exactly these, in this order:
   - **"Why was each component chosen?"**
   - **"What would break if one of them were changed?"**
4. Do not prompt, hint, correct, or fill silences. If they ask you a question,
   say "I'd rather not say until you've answered — it'll skew the result."
5. Write down what they say **before** you react to it.

**On disclosure:** don't volunteer that the text is AI-generated beforehand —
that buys you either hostility or charity, and both are noise. Tell them
immediately afterwards, before you discuss anything. Blind review is normal;
concealing it after the fact is not.

---

## 4. Scoring

PASS requires them to get **both** questions right **unaided**. For this circuit,
they should independently arrive at roughly:

| # | They should say something like | Tests |
|---|---|---|
| 1 | The pull-up holds DATA high between transmissions | purpose, not just identity |
| 2 | Without it the open-drain output never reaches logic HIGH, so the MCU reads timeouts | consequence of omission |
| 3 | Too low a value exceeds the sensor's sink current limit | consequence of wrong value |
| 4 | Why DHT22 rather than an alternative, in terms of *this* prompt | selection reasoning |
| 5 | What the 30°C threshold does in firmware and where it lives | spec → implementation |

**Rows 2 and 3 are the criterion.** Rows 1, 4 and 5 can be recovered by a good
engineer from the schematic alone — they do not prove the *explanation* worked.
Only the consequence rows distinguish a consequential explanation from a
descriptive one, and that distinction is the product.

Mark each row: **stated unaided** / **stated after re-reading** / **not stated**.

PASS = rows 2 and 3 stated unaided, by at least two of three reviewers.

---

## 5. If it fails

A fail is information, not a setback — and it is cheap here rather than expensive
in front of a customer.

- **Record the exact sentence** the reviewer stumbled on. That sentence is the bug.
- The fix is in `backend/ai/explainer.py`'s system prompt: every sentence must
  answer *"what breaks if this is wrong?"*. Descriptive sentences are the defect.
- `tests/test_explainer.py` asserts on causal markers ("if you", "exceeds",
  "would fail"). Those catch a prompt *regression*, not a quality regression —
  which is exactly why this criterion needs a human and cannot be automated away.
- Re-run with fresh reviewers. Someone who has already read a version is burned
  for this test permanently.

---

## 6. Recording the result

On PASS, criterion 12 closes and the path to `v0.1.0` is:

1. Log the result in `.claude/shared-memory/brain/decisions.md` — date, reviewer
   role (not name), model ID, which rows were unaided.
2. `PHASE1_COMPLETE.md` with evidence per criterion, keeping criterion 11 marked
   **`met_by_substitute`**, its limitation stated in full, and the PCB engine
   scope decision recorded.
3. `python .claude/shared-memory/tools/regen_state.py`
4. `git tag v0.1.0 && git push --tags`

Criterion 12 is not auto-checkable and never will be — it stays `⏳` in
`regen_state.py` and gets closed by hand in `PHASE1_COMPLETE.md`. That is
correct, not a gap.
