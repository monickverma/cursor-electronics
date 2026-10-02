# Step 6 — Then decide what this is

This is a draft to argue with. It isn't a decision: the decision is yours, after steps 1–5.

## The bet: a research contribution

**Working title.** *Assurance by elimination for LLM-generated hardware.*

**The claim.** An LLM can sit at the front of a hardware design flow without being trusted. It writes only a
requirement, and everything downstream is deterministic. Every claim about the result names what it assumes and
what could defeat it.

### Contributions (each one is already in the repo)

1. **The One Rule as architecture.** The LLM writes IntentIR and never the circuit. A scanner test enforces this.
   Retries may add to a request but never rewrite it (X5).
2. **Refusal by name.** A request outside a generator's envelope is refused with a reason rather than approximated.
3. **Claims with explicit defeaters.** Each claim has a register of D1–D9 doubts and is graded by its weakest
   claim, never an average. Unchecked is never shown as passed.
4. **Proofs from the netlist.** Properties are compiled from the SPICE text into exact nodal analysis, then proved
   with z3 over tolerance boxes, with sound rational enclosures. The English is generated from the formula, so the
   sentence a person signs is the theorem.
5. **An honest ledger of what isn't retired.** D1, D7 and the V_F assumption are stated as open, not hidden.

### The evidence each step supplies

| Step | Evidence for the paper |
|---|---|
| 1 Bench | Model against measurement on four designs: the first external validation |
| 2 D7 spot-check | The measured error rate of agent-extracted datasheet figures; publishable either way |
| 3 Signing | Whether a person can actually read and endorse generated proof statements |
| 4 Outside reader | Whether the explanations communicate (D3), from a blind read |
| 5 Users | The envelope's coverage of real demand, and the refusal distribution |

### Threats to validity, to state up front

- The scope is five templates on three boards: depth, not breadth.
- The tests were largely written by the same agent that wrote the code (mitigated by CI and independent review,
  which found 25 defects the suite missed).
- The datasheet figures were extracted by an LLM (step 2 measures this).
- The developer and the evaluator are the same person (steps 4 and 5 bring in outsiders).

### Where it could go

A final-year thesis first. Then a workshop paper (formal methods in EDA, or LLMs for hardware) once steps 1–5 give
it numbers.

## What stops until then

- Bulk confirmations of anything.
- New machinery: defeaters, Jev decisions, the PCB engine, Phase 3 planning.
- Treating the test count as progress.
