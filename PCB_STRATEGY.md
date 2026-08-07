# PCB & CAD Strategy

> Written 2026-08-07, after reading `backend/pcb_engine/compile_board.py`.
> A position to argue with, not a plan to execute on faith. Section 9 lists the
> ways it could be wrong.
>
> Audience sequence chosen: **hobbyist → PCB designer → HVAC/controls.**

---

## 1. What the engine does today

`place_constructive()` orders components by pad count descending, then drops each
at the grid position minimising added Manhattan bounding-box wirelength, subject
to courtyard non-overlap plus a 0.4mm gap. `AStarRouter` then routes nets on a
grid with obstacle masks and halo cells.

Stated plainly: **it optimises wirelength, and nothing else.**

The code is competent. The greedy-legal-by-construction choice in
`place_constructive` is a genuinely good call — it avoids the dense unroutable
clump that gradient descent converges to, and the docstring says so. This is not
a criticism of the engineering.

It is a criticism of the objective function.

---

## 2. Why wirelength is the wrong objective

Two problems, one strategic and one technical.

### Strategic: this race is lost before you enter it

Wirelength placement plus grid A* routing is the 1980s formulation of PCB
autolayout. Lee's algorithm is from 1961. freerouting has shipped this for two
decades. Quilter has moved a full generation past it with physics-driven
reinforcement learning and per-candidate scorecards.

If you keep pushing here, you are entering the one contest in your space where a
well-funded specialist is genuinely excellent and you have no structural
advantage. You will spend a year to arrive somewhere behind where they are now.

### Technical: even placement is often actively wrong

Good boards are lumpy on purpose. A representative sample of what real placement
is driven by:

| Constraint | Driven by | Wirelength says |
|---|---|---|
| Decoupling cap jammed against the IC power pin | loop inductance | "anywhere on that net" |
| Switching regulator hot loop kept tight | di/dt, radiated EMI | nothing |
| Crystal close and guarded | stray capacitance, jitter | "short trace, fine" |
| Connectors on board edges | mechanical, not electrical | "put it in the middle" |
| Power devices spread out | thermal | "cluster them" |
| Analog away from switching nodes | coupled noise | "closer is better" |
| TVS at the signal entry point | surge path | "anywhere on the net" |

Wirelength is a *proxy*. It correlates with a good layout in easy cases and
diverges in exactly the cases that matter. A tidy, evenly balanced board is what
you get when the optimiser does not know what the circuit means.

---

## 3. The reframe: your asset is constraints, not routing

Here is what nobody else can do.

Your `CircuitIR` already knows `SignalType.POWER`, `GROUND`, `ONE_WIRE`,
`application_class`, component types, part numbers, and — uniquely in this
market — **simulation results**. `place_constructive` receives pads and nets and
discards every bit of it.

| Competitor | Why they cannot derive layout constraints from intent |
|---|---|
| Flux.ai | No simulation. It has design context but no physics to reason from. |
| Quilter | Receives a netlist. World-class at layout, but intent never reached it. |
| Celus.io | Stops at the schematic. Component compatibility, not physics. |
| KiCad / Altium | The human supplies the constraints. That is the whole job. |

### This is not hypothetical — check the enums

`SignalType` in `ir_schema.py` already distinguishes:

```
power  ground  digital  analog  i2c_sda  i2c_scl
spi_mosi  spi_miso  spi_sck  spi_cs  uart_tx  uart_rx
rs485_a  rs485_b  pwm  one_wire
```

`ApplicationClass`: `hobby_arduino`, `iot_node`, `industrial_io`,
`hvac_control`, `modbus_rtu`.

`rs485_a` and `rs485_b` are **separate signal types**. Your IR knows, at the
node level, that two specific nets form an RS-485 differential pair — which
means it knows they need matched length, controlled spacing, 120Ω termination at
both ends and nothing between, and TVS at the entry point.

`place_constructive` sees `p.net` as an opaque string and optimises Manhattan
distance over it.

**The information is already there. The layout engine simply does not look.**
That is not a research problem. It is a wiring-up problem, and it is the
cheapest large win available to you right now.

You are the only tool positioned to say, before a netlist exists:

> "This is an RS-485 bus. A/B is a differential pair, 120Ω termination at both
> physical ends of the bus and nowhere else, TVS at the connector entry, minimum
> 8mm from the switching regulator, bias resistors near the master."

Not because a router inferred it from geometry — because **you knew it was
RS-485 at the intent stage.**

**So: the moat is the constraint layer. The router is a commodity you should
consume, not a product you should build.**

This also resolves your competitive position with Quilter. Stop being a weaker
version of them. Become the thing that feeds them — and feeds freerouting, and
feeds KiCad, and feeds a human. Constraints are portable. Routers are not.

---

## 4. The three audiences, and what actually differs

You chose hobbyist → designer → HVAC. Taking that seriously:

| | Hobbyist | PCB designer | HVAC / controls |
|---|---|---|---|
| Owns an EDA tool | no | yes, expert, won't switch | usually not |
| Wants layout control | none | total | some |
| Quality bar | "it works" | professional | "it passes inspection" |
| Will they use your CAD | no — wants auto | never | **yes — no alternative** |
| Pays for | convenience | validation, constraints | de-risking a product line |
| Sales cycle | instant | short | long, high value |

**The important observation:** all three want the constraint layer and the
explanation. Only the *surface* differs.

- Hobbyist: constraints applied silently, board just comes out better
- Designer: constraints exported to their tool, plus a validation report
- HVAC: constraints plus a guided editor, because they have no tool at all

**Build the constraint engine once. Put three faces on it.** That is the
architectural payoff of the sequence you picked, and it means the middle
audience is not a detour.

### Pushback on the middle step

Professional PCB designers are the hardest segment you listed. They own tools
they are expert in, hold the highest quality bar, are most sceptical of
AI-generated layout, and are least willing to pay for a new one. If "win the
designer" means "get them to lay out boards in your CAD," that step will
consume years and probably fail.

**Make it thin deliberately.** Win designers as a *constraint and validation
provider* — a KiCad plugin, a DSN/net-class export, a rule report — not as a CAD
replacement. Their respect is the proof point that sells HVAC ("professional PCB
designers use our constraint output"), and you can earn it without building CAD.

The original bottom-up thesis was hobbyist → IoT startup → OEM. Substituting
"designer" for "IoT startup" is fine *if* the designer step is a credibility
play rather than a revenue play. If you are counting on designer seat revenue,
reconsider.

---

## 5. The CAD staircase

Four steps. You are on step one.

| Step | What it is | Who needs it | Cost |
|---|---|---|---|
| 1. **Viewer** | `render_pretty.py` → SVG. Done. | everyone | done |
| 2. **Annotated viewer** | Shows *why* each part is where it is; DRC violations inline with consequences | everyone | weeks |
| 3. **Constrained editor** | Drag parts, rules enforced live, immediate feedback on what you just broke | HVAC, some designers | months |
| 4. **General CAD** | Replace KiCad | HVAC only | years |

**Step 2 is the one to build, and it is uniquely yours.** It is your explanation
layer applied to geometry:

> "C1 sits 2.1mm from U2's VCC pin. At 8mm the supply loop inductance pushes
> ripple past the DHT22's 0.3V tolerance and readings intermittently fail CRC.
> Simulation confirms. Moving it further is the single most likely way to break
> this board."

No competitor has this. Flux shows you a board. Quilter shows you a scorecard.
Neither tells you *why*, in a sentence an HVAC engineer can act on.

**Note where CAD actually lands.** Hobbyists do not want CAD, they want
automation. Designers will not switch to your CAD. Only HVAC needs it — and HVAC
is your third audience. **Therefore full CAD is a phase-3 investment, and
building it now would be building for the audience you reach last.**

That is convenient. It means the right move today is step 2, which serves
everyone, rather than step 4, which serves nobody yet.

---

## 6. What to build, in order

### Now — semantic placement (days, not months)

Make `place_constructive` read the IR instead of just pads. A starter rule set:

1. **Decoupling caps** — nearest legal position to the power pin of the IC they
   decouple, before any wirelength consideration. Highest impact, easiest to
   detect (small cap, one pin on a POWER net, one on GROUND, same net as an IC).
2. **Connectors and terminal blocks** — board edge, not interior.
3. **Protection devices** (TVS, fuses) — between the connector and everything else.
4. **Transceivers** (MAX485, CAN) — adjacent to their connector, short stubs.
5. **Crystals/oscillators** — minimum distance to the MCU pin, keepout around.
6. **Analog vs switching separation** — minimum distance between nodes typed
   analog and any node that switches.
7. **Thermal spread** — power dissipators not clustered.

Rules 1 and 2 alone will visibly change output quality more than any routing
improvement you could ship this quarter. All the information needed is already
in the IR.

### Next — constraints as a first-class artifact

You already have `to_dsn()`. Extend to a real constraint set:

- Net classes with trace width and clearance per signal type
- Differential pairs with target impedance and length matching
- Keepouts (analog islands, antenna zones, high-voltage clearance)
- Placement groups (this cap belongs to that IC)
- **A plain-English reason attached to every constraint**

That last bullet is the product. A constraint file that explains itself is
something no EDA tool produces, and it is exportable to KiCad, freerouting,
Quilter, or a human reviewer.

### Then — the annotated viewer (step 2)

Overlay the reasons on the SVG you already render. DRC violations with
consequences, not codes. This is where the CAD ambition properly begins.

### Not yet — routing quality

Leave A* alone. It is adequate for the boards your five templates produce. When
routing quality genuinely blocks you, prefer integrating freerouting over
improving your own router, and revisit only if a specific customer need proves
otherwise.

---

## 7. Explicit non-goals

Writing these down so they stop consuming attention:

- **Beating Quilter at autorouting.** Not winnable, not necessary, not your moat.
- **General-purpose CAD before the HVAC phase.** Building for the audience you
  reach last, at the highest cost.
- **Gerber export and fab APIs right now.** Real value, but downstream of layout
  quality being trustworthy. Premature.
- **Multi-layer beyond 2–4 layers.** Your circuit classes do not need it.
- **RF, controlled impedance, high-speed digital.** Your simulator cannot
  validate above ~100MHz, so you would be generating constraints you cannot
  check. Say so out loud rather than quietly generating them.

---

## 8. How this changes the roadmap

`master_plan.md` has PCB auto-layout in Phase 3 via KiCad freerouting. Reality is
a custom A* engine shipped in Phase 1. Under this strategy:

- **Phase 1 (now):** PCB engine is experimental and labelled. Not in the v0.1.0
  gate. Semantic placement rules land here because they are cheap and visible.
- **Phase 2:** constraint layer as a first-class output. Annotated viewer.
  Designer-facing export (KiCad plugin / DSN / rule report).
- **Phase 3:** constrained editor. Industrial rule libraries — this is where
  UL 508A, 4–20mA, RS-485 bias and termination, 24VDC supply patterns pay off,
  and where CAD investment finally matches the audience.

---

## 9. How this could be wrong

Take these seriously; each would change the conclusion.

1. **If layout quality is the actual buying trigger**, constraints are a
   consolation prize and this whole document is a rationalisation for not
   competing. Test it: show two hobbyists a good board with no explanation and a
   mediocre board with a great explanation. See which one they want.

2. **If Quilter or Flux ships intent-aware constraints**, the moat closes fast.
   Flux is closest — they have design context and would only need to add physics.
   Watch for it.

3. **If HVAC customers want finished boards, not designs**, then CAD never
   matters and you should be a design service with software leverage. Worth
   asking three real HVAC controls people before committing to step 3 or 4.

4. **The constraint layer may be harder than it looks.** "Decoupling cap near
   the pin" is easy. "How near, given this supply, this load step, this
   tolerance" is a real engineering problem. If the constraints are vague, the
   explanation is vague, and the differentiator evaporates.

5. **Semantic placement rules may not generalise past your five templates.**
   They are hand-written heuristics. Beyond the templates they may be wrong more
   often than wirelength. Watch for it as breadth grows.

---

## 10. The one-line version

> **Stop trying to lay out boards better than Quilter. Start being the only tool
> that knows *why* a board should be laid out that way — and sell that to
> everyone, including Quilter's users.**

The CAD ambition is real and reachable. It arrives as step 3–4 of a staircase
whose lower steps each ship value on their own, and it arrives at the same time
as the audience that actually needs it.
