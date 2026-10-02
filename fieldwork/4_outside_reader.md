# Step 4 — One outside reader, three explanations (criterion 12 / D3)

The protocol is [`CRITERION_12_REVIEW.md`](../CRITERION_12_REVIEW.md): say nothing, ask the two questions, and write
down the answers before you react. This sheet only adds what changed.

## Capture the three texts (blocked on 2026-10-02)

I tried to capture these from the running backend and couldn't:

- The guide's own prompt, *"Arduino reads DHT22 and alerts above 30°C"*, is now **refused as underdetermined**
  (cable length and supply not given). That is correct behaviour, but it means the guide's §1 is out of date.
- After that, every request failed with **OpenRouter 402 `in_flight_budget_exhausted`**: the account is out of
  credits. Top it up first.
- One of those requests came back as a bare **HTTP 500** rather than the 503 the others got. An unhandled
  error on `/design/generate` is a launch-checklist failure in its own right ("zero HTTP 500s"), so look at the
  backend log for it.

Once there are credits, with the backend up:

```bash
python scripts/capture_explanation.py --prompt "Arduino Uno reads a DHT22 over a 2 m cable on a 5 V supply and alerts above 30°C"
```

```bash
python scripts/capture_explanation.py --prompt "Arduino Uno drives an indicator LED at 10 mA from a 5 V supply"
```

```bash
python scripts/capture_explanation.py --prompt "RC low-pass filter with a 1 kHz cutoff on a 5 V supply"
```

Each one writes `captures/<slug>__<model>__<timestamp>.json`. Hand over the explanation text **verbatim**, and
keep the model ID and date in your notes, not in the text you give the reader.

## Who

A final-year EE student or a faculty member who hasn't seen the project. Get three readers if you can; one reader
is a coin flip.

## Record

| Reader | Design | "Why each component?" (their words) | "What breaks if one changes?" (their words) | Understood without help? |
|---|---|---|---|---|
| | DHT22 | | | |
| | LED | | | |
| | RC filter | | | |

Tell them it was AI-generated **afterwards**, before you discuss anything.
