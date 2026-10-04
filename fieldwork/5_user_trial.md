# Step 5 — Ten real users

**Goal:** measure what share of real requests the five templates handle, and turn every refusal into a backlog item.
This answers the "AI hardware compiler" generality question with a number instead of a corpus we wrote ourselves.

## Setup

- Ten people who build things with Arduinos: classmates, or the robotics or electronics club.
- Brief them in one line only: *"Describe a circuit you'd actually want built, in your own words."* Don't show them
  the template list. That would measure the list, not the demand.
- Each person makes 1–3 requests. They sit with you, or use the app themselves with an account you create.
- Credits: each generation costs about $0.05–0.15, so 30 requests is under $5. Top up OpenRouter first.

## What to log

The app already logs every request to `request_log` (outcome `completed` / `refused` / `failed`, plus
`refusal_reason`, `underdetermined`, `generator` and `latency_ms`). **It stores only a hash of the prompt, not the
text.** That's deliberate, for privacy, but it means the trial needs its own sheet. With each person's consent,
write the words down:

| # | Who (initials) | Prompt, verbatim | Outcome | Refusal reason / questions asked | Did they want this? (Y/N) |
|---|---|---|---|---|---|
| 1 | | | | | |

Afterwards, cross-check against the log:

```sql
SELECT created_at, outcome, generator, refusal_reason, underdetermined, latency_ms, error
FROM request_log
WHERE created_at >= '<trial start>' AND route LIKE '%/design/generate%'
ORDER BY created_at;
```

## What comes out

- **Acceptance rate on real demand** = completed ÷ requests. Report it as a fraction with the denominator, never as
  a percentage on its own.
- **The refusal histogram:** group the refusals by what was asked for (motor driver, I2C sensor, battery charger…).
  The top three rows are the Phase 3 backlog, ranked by people rather than by us.
- **Every `failed` row and every 500 is a bug.** File each one.
