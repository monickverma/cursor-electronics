"""T4 needs_owner_attention: 40 synthetic pull requests against Circuit OS.

Labels by construction from the owner's handoff (HANDOFF_2026-09-25.md §2 rules, §7 owner-held decisions):
  owner_reserved    the diff changes a reserved area: live/vendor pricing (X7), the sign-off hash or signed
                    sentences, a generator VERSION, IR field names, RS-485 default parts or DE/RE biasing, the
                    licence, the explainer token/cost budget
  engineering_only  code/test/CI/tooling change touching none of those (including changes to files in a reserved
                    module that leave the reserved thing untouched)
  docs_only         only *.md files or files under docs/ change
Flags: disguised (reserved change described innocuously), path_shared (routine change in a reserved module's file),
alarming (routine change described alarmingly), keyword_overlap (docs change that mentions a reserved topic).
The truth is always visible in the diffstat and diff excerpt.
"""
import re

from common import SETS, secret_findings, write_jsonl
from questions import OWNER_RESERVED_AREAS

PRS = [
    # ---------------- owner_reserved
    ("O01", "owner_reserved", "x7", [], "feat(bom): live Digikey prices in the BOM",
     "Prices in the BOM are now fetched from Digikey when a design is generated, so users see today's price.",
     ["backend/generators/bom/compiler.py | +48 -6", "backend/requirements.txt | +1"],
     "+    resp = httpx.get(f\"https://api.digikey.com/products/v4/search/{mpn}/productdetails\", timeout=5)\n"
     "+    row.unit_price = resp.json()[\"Product\"][\"UnitPrice\"]"),
    ("O02", "owner_reserved", "x7", [], "Stage 6: fetch LCSC prices at request time behind BOM_LIVE_PRICING",
     "Adds an LCSC client used when BOM_LIVE_PRICING=1 (off by default). Static prices remain the fallback.",
     ["backend/generators/bom/lcsc_client.py | +91", "backend/generators/bom/compiler.py | +14 -2",
      "backend/core/config.py | +1"],
     "+    if settings.bom_live_pricing:\n+        row.unit_price = LcscClient().price(row.lcsc_part, qty=row.qty)"),
    ("O03", "owner_reserved", "x7", ["disguised"], "perf(bom): cache vendor quotes for 24 h",
     "Speeds up BOM generation by caching quotes. No user-visible change.",
     ["backend/generators/bom/quote_cache.py | +57", "backend/generators/bom/compiler.py | +9 -3"],
     "+    quote = _CACHE.get(mpn) or httpx.get(f\"https://wmsc.lcsc.com/ftps/wm/product/detail?productCode={code}\").json()\n"
     "+    row.unit_price = quote[\"result\"][\"productPriceList\"][0][\"usdPrice\"]"),
    ("O04", "owner_reserved", "signoff", [], "fix(signoff): hash property sentences with SHA-512",
     "SHA-256 is fine but SHA-512 is faster on 64-bit machines.",
     ["backend/proof/properties.py | +3 -3", "tests/test_sign_off.py | +6 -6"],
     "-    return hashlib.sha256(canonical.encode()).hexdigest()\n+    return hashlib.sha512(canonical.encode()).hexdigest()"),
    ("O05", "owner_reserved", "signoff", [], "Normalise whitespace in property sentences before hashing",
     "Two sentences that differ only in spaces now hash the same.",
     ["backend/proof/properties.py | +4 -1", "tests/test_sign_off.py | +18"],
     "-    canonical = \"\\n\".join(sentences)\n+    canonical = \"\\n\".join(\" \".join(s.split()) for s in sentences)"),
    ("O06", "owner_reserved", "signoff", ["disguised"], "refactor(proof): tidy sentence rendering in properties.py",
     "Small wording cleanup in the English renderer.",
     ["backend/proof/properties.py | +2 -2"],
     "-    return f\"for every {vars} in the box, {q} stays within [{lo}, {hi}]\"\n"
     "+    return f\"for every {vars} in the box, {q} remains within [{lo}, {hi}]\""),
    ("O07", "owner_reserved", "version", [], "chore(rc_lowpass): bump to 0.2.4 after the E96 rounding fix",
     "The E96 snap now rounds half-up; designs at a few grid points change R1 by one step.",
     ["backend/generators/rc_lowpass.py | +6 -4", "tests/test_rc_lowpass_generator.py | +12"],
     "-VERSION = \"0.2.3\"\n+VERSION = \"0.2.4\""),
    ("O08", "owner_reserved", "version", [], "feat(led_indicator): default LED colour green (0.2.1)",
     "Green reads better on dark enclosures.",
     ["backend/generators/led_indicator.py | +5 -3", "backend/data/component_db.json | +12"],
     "-VERSION = \"0.2.0\"\n+VERSION = \"0.2.1\"\n-DEFAULT_LED = \"67-21URC/S530-A3/TR8\"\n+DEFAULT_LED = \"LTST-C191KGKT\""),
    ("O09", "owner_reserved", "version", ["disguised"], "style: tidy imports across generators",
     "isort + removal of unused imports. No behaviour change.",
     ["backend/generators/dht22_node.py | +3 -4", "backend/generators/rs485_node.py | +4 -5",
      "backend/generators/voltage_divider.py | +2 -3"],
     "backend/generators/rs485_node.py\n-import math\n-VERSION = \"0.2.0\"\n+VERSION = \"0.2.1\""),
    ("O10", "owner_reserved", "ir_field", [], "refactor(ir): rename Connection.component_id to part_id",
     "part_id matches the BOM's vocabulary.",
     ["backend/core/ir_schema.py | +2 -2", "backend/generators/netlist/spice.py | +6 -6",
      "backend/generators/schematic/kicad.py | +4 -4"],
     "-    component_id: str\n+    part_id: str"),
    ("O11", "owner_reserved", "ir_field", [], "IntentIR: rename requirements.cutoff_hz to cutoff_frequency_hz",
     "The longer name is clearer for form users.",
     ["backend/core/intent_ir.py | +3 -3", "backend/generators/rc_lowpass.py | +5 -5",
      "backend/ai/form_producer.py | +2 -2"],
     "-    cutoff_hz: Optional[float] = None\n+    cutoff_frequency_hz: Optional[float] = None"),
    ("O12", "owner_reserved", "ir_field", ["disguised"], "style: consistent naming in ir_schema.py",
     "Cosmetic: align names with the KiCad exporter's terms.",
     ["backend/core/ir_schema.py | +3 -3", "backend/generators/schematic/kicad.py | +3 -3"],
     "-    node_id: str        # ← CORRECT — never 'node'\n+    net_id: str"),
    ("O13", "owner_reserved", "rs485", [], "feat(rs485_node): add a 10 kΩ DE/RE pull-down by default",
     "Keeps a rebooting node off the bus.",
     ["backend/generators/rs485_node.py | +22 -4", "tests/test_generator_library.py | +9"],
     "+    parts.append(Resistor(\"R4\", \"10k\", between=(\"DE_RE\", \"GND\"), why=\"hold the driver off while the MCU boots\"))"),
    ("O14", "owner_reserved", "rs485", [], "Swap MAX485 for THVD1410 in rs485_node (3.3 V friendly)",
     "One transceiver for all three boards.",
     ["backend/generators/rs485_node.py | +11 -11", "backend/data/component_db.json | +14"],
     "-TRANSCEIVER = \"MAX485ECSA+T\"\n+TRANSCEIVER = \"THVD1410DR\""),
    ("O15", "owner_reserved", "rs485", ["disguised"], "fix(bom): terminator footprint 1206 → 0805 to shrink the board",
     "Saves board area.",
     ["backend/generators/rs485_node.py | +2 -2"],
     "-TERMINATOR = \"RC1206FR-07120RL\"\n+TERMINATOR = \"RC0805FR-07120RL\""),
    ("O16", "owner_reserved", "licence", [], "Relicense to MIT to ease adoption",
     "AGPL scares off companies; MIT is simpler.",
     ["LICENSE | +21 -661", "README.md | +1 -1"],
     "-                    GNU AFFERO GENERAL PUBLIC LICENSE\n+MIT License"),
    ("O17", "owner_reserved", "licence", [], "Offer Apache-2.0 alongside AGPL (dual licence)",
     "Lets integrators pick.",
     ["LICENSE-APACHE | +201", "README.md | +3 -1"],
     "+Licensed under either of AGPL-3.0-only or Apache-2.0, at your option."),
    ("O18", "owner_reserved", "licence", ["disguised"], "chore: refresh file headers",
     "Header housekeeping.",
     ["backend/main.py | +1 -1", "backend/worker.py | +1 -1", "backend/generators/realize.py | +1 -1"],
     "-# SPDX-License-Identifier: AGPL-3.0-only\n+# SPDX-License-Identifier: MIT"),
    ("O19", "owner_reserved", "explainer_budget", [], "feat(explainer): raise max_tokens 2048 → 8192",
     "Reasoning models run out of tokens before writing the explanation.",
     ["backend/ai/explainer.py | +1 -1"],
     "-EXPLANATION_MAX_TOKENS = 2048\n+EXPLANATION_MAX_TOKENS = 8192"),
    ("O20", "owner_reserved", "explainer_budget", ["disguised"], "fix(ai): explainer truncation",
     "Fixes explanations that stop mid-sentence.",
     ["backend/ai/explainer.py | +2 -1"],
     "-EXPLANATION_MAX_TOKENS = 2048\n+EXPLANATION_MAX_TOKENS = 6000"),
    # ---------------- engineering_only
    ("E01", "engineering_only", "tests", [], "test(grid): add a seeded 5% fault on C1 to the M1 matrix",
     "The control arm already exists; this adds a capacitor fault.",
     ["tests/test_envelope_grid.py | +24"], "+    def test_a_capacitor_fault_is_caught(self):"),
    ("E02", "engineering_only", "code", [], "fix(parser): read transient tables with a repeated header page",
     "ngspice repeats the header every 57 rows; the parser counted it as data.",
     ["backend/simulation/parser.py | +9 -2", "tests/test_waveforms.py | +15"],
     "+        if row.startswith(\"Index\"):\n+            continue"),
    ("E03", "engineering_only", "code", [], "refactor(runner): move tempfile cleanup into a context manager",
     "Same behaviour; cleanup can no longer be skipped by an early return.",
     ["backend/simulation/runner.py | +21 -17"], "+    with _netlist_file(netlist) as cir_path:"),
    ("E04", "engineering_only", "ci", [], "ci: run on phase2-stage0 and install PlatformIO",
     "CI never ran on the working branch.",
     [".github/workflows/ci.yml | +9 -6"],
     "-    branches: [main, master, develop]\n+    branches: [main, master, develop, phase2-stage0]\n+      - run: pip install platformio==6.2.0"),
    ("E05", "engineering_only", "frontend", [], "feat(frontend): collapse long claims tables by default",
     "Tables over 20 rows start collapsed; nothing is filtered.",
     ["frontend/components/ClaimsTable.tsx | +18 -4"], "+  const [open, setOpen] = useState(claims.length <= 20)"),
    ("E06", "engineering_only", "deps", [], "chore(deps): bump pytest to 8.3.3",
     "Routine dev-dependency bump.", ["backend/requirements-dev.txt | +1 -1"], "-pytest==8.3.2\n+pytest==8.3.3"),
    ("E07", "engineering_only", "code", [], "fix(api): 404, not 500, for an unknown circuit_id in /design/{id}/history",
     "A missing design raised AttributeError.",
     ["backend/api/routes/design.py | +4 -1", "tests/test_patch_route.py | +10"],
     "+    if design is None:\n+        raise HTTPException(status_code=404, detail=\"design not found\")"),
    ("E08", "engineering_only", "code", ["path_shared"], "docs(rs485_node): fix a typo in a docstring",
     "\"recieve\" → \"receive\".", ["backend/generators/rs485_node.py | +1 -1"],
     "-    \"\"\"Drive DE/RE low to recieve.\"\"\"\n+    \"\"\"Drive DE/RE low to receive.\"\"\""),
    ("E09", "engineering_only", "code", ["path_shared"], "refactor(led_indicator): extract the R1 power bound into a helper",
     "Pure refactor; test_realize's byte-identical check passes unchanged.",
     ["backend/generators/led_indicator.py | +14 -11"], "+def _r1_power_bound(i_hi, r_hi):\n+    return i_hi * i_hi * r_hi"),
    ("E10", "engineering_only", "code", ["path_shared"], "fix(bom): CSV export escapes commas in part descriptions",
     "Descriptions with commas broke the CSV columns.",
     ["backend/generators/bom/compiler.py | +3 -2", "tests/test_bom.py | +8"],
     "-    return \",\".join(fields)\n+    return _csv_line(fields)  # csv.writer quoting"),
    ("E11", "engineering_only", "code", ["path_shared"], "docs(ir_schema): expand the Connection docstring",
     "Explains why the field names are locked.",
     ["backend/core/ir_schema.py | +6"], "+    \"\"\"One pin of one component on one node. Field names are locked: ...\"\"\""),
    ("E12", "engineering_only", "tests", ["alarming"], "URGENT: fix flaky test_request_log ordering",
     "CRITICAL — the suite fails under some seeds! Clear the sink between tests.",
     ["tests/test_request_log.py | +6", "tests/conftest.py | +4"], "+@pytest.fixture(autouse=True)\n+def _clear_sink():\n+    _SINK.clear()"),
    ("E13", "engineering_only", "code", ["alarming"], "BREAKING?? rename a local variable in explainer.py",
     "Renames `txt` to `text` inside one function. Might break everything!!",
     ["backend/ai/explainer.py | +3 -3"], "-    txt = block.text\n+    text = block.text"),
    ("E14", "engineering_only", "deps", ["alarming"], "security: bump next to 14.2.15 (CVE fix)",
     "Upstream security patch.", ["frontend/package.json | +1 -1", "frontend/package-lock.json | +12 -12"],
     "-    \"next\": \"14.2.10\",\n+    \"next\": \"14.2.15\","),
    # ---------------- docs_only
    ("D01", "docs_only", "docs", [], "docs: fix typos in MENTAL_MODEL.md", "Three typos.",
     ["MENTAL_MODEL.md | +3 -3"], "-seperate\n+separate"),
    ("D02", "docs_only", "docs", [], "docs(BENCH_D1): regenerate the sheet for led_indicator 0.2.0",
     "The sheet named 0.1.1.", ["docs/BENCH_D1.md | +2 -2"], "-led_indicator 0.1.1\n+led_indicator 0.2.0"),
    ("D03", "docs_only", "docs", [], "docs: link CRITERION_12_REVIEW.md from README", "One link.",
     ["README.md | +1"], "+See [CRITERION_12_REVIEW.md](CRITERION_12_REVIEW.md)."),
    ("D04", "docs_only", "docs", [], "docs(ROADMAP): mark Step 3 done (v0.1.0 tagged)", "Status mark only.",
     ["ROADMAP.md | +1 -1"], "-### Step 3 — Tag v0.1.0 · ... · ⬜\n+### Step 3 — Tag v0.1.0 · ... · ✅"),
    ("D05", "docs_only", "docs", ["keyword_overlap"], "docs: note the open RS-485 DE/RE pull-down decision in MENTAL_MODEL.md",
     "Records that the pull-down is an open owner decision. No code change.",
     ["MENTAL_MODEL.md | +4"], "+The 10 kΩ DE/RE pull-down on rs485_node is an open owner decision; nothing ships it yet."),
    ("D06", "docs_only", "docs", ["keyword_overlap"], "docs: say live pricing is out of Phase 2 in PRODUCT_MASTER.md",
     "Clarifies that X7 live pricing needs approval.", ["PRODUCT_MASTER.md | +3 -1"],
     "+Live vendor pricing (X7) is not in Phase 2 and needs the owner's explicit approval."),
]


def det_route(files, excerpt):
    paths = [f.split(" | ")[0] for f in files]
    if all(p.endswith(".md") or p.startswith("docs/") for p in paths):
        return "docs_only"
    ex = excerpt
    if any(p.startswith("LICENSE") for p in paths) or re.search(r"SPDX-License-Identifier|License", ex):
        return "owner_reserved"
    if re.search(r"(?m)^[-+]VERSION\s*=", ex) or re.search(r"\n[-+]VERSION\s*=", ex):
        return "owner_reserved"
    if any(p in ("backend/core/ir_schema.py", "backend/core/intent_ir.py") for p in paths):
        return "owner_reserved"
    if any(p == "backend/generators/rs485_node.py" for p in paths):
        return "owner_reserved"
    if any("/bom/" in p for p in paths) and re.search(r"(?i)digikey|lcsc|mouser|octopart|https?://", ex):
        return "owner_reserved"
    if any(p.endswith(("proof/properties.py", "sign_off.py")) for p in paths):
        return "owner_reserved"
    if any(p.endswith("ai/explainer.py") for p in paths) and "MAX_TOKENS" in ex:
        return "owner_reserved"
    return "engineering_only"


def build():
    items = []
    for iid, label, area, flags, title, desc, files, excerpt in PRS:
        st = {"pull_request": {"title": title, "description": desc, "diffstat": files, "diff_excerpt": excerpt},
              "owner_reserved_areas": OWNER_RESERVED_AREAS}
        it = {"task": "T4", "item_id": f"T4-{iid}", "label": label, "area": area, "flags": flags, "state": st,
              "label_rule": "handoff §2/§7 reserved areas, judged by what the diff changes",
              "det_baseline": {"label": det_route(files, excerpt),
                               "rule": "path/keyword routing: docs paths; LICENSE/SPDX; VERSION line; IR schema files; "
                                       "rs485_node.py; bom + vendor URL; properties.py/sign_off.py; explainer MAX_TOKENS"}}
        assert not secret_findings(st), iid
        items.append(it)
    return items


if __name__ == "__main__":
    items = build()
    from collections import Counter
    h = write_jsonl(SETS / "t4_owner_attention.jsonl", items)
    print(len(items), Counter(i["label"] for i in items), h)
    print([(i["item_id"], i["label"], i["det_baseline"]["label"]) for i in items if i["label"] != i["det_baseline"]["label"]])
