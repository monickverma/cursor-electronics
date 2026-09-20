"""
Stage 1 Task 1.5 — the architecture's load-bearing invariant, asserted.

> **Gate:** No code path lets the LLM write CircuitIR — *asserted by test*.
> analytic, G1.

This has been the project's central claim since 2026-06-01 and until now it
was enforced by prose: `CLAUDE.md`'s "The One Rule", `MENTAL_MODEL.md` §3, and
a line in `decisions.md`. A rule that only exists in documentation is a rule
that holds until someone in a hurry does not read it.

The check is **static**, by AST, and deliberately not a runtime one. A runtime
test can only show that the paths it exercised did not do this; the claim is
analytic — that no such path exists — and only reading every module can
support that. `EVIDENCE_CLASSES.md` §3.1 is the test: could a measurement
falsify it? No. So it must be argued from the code, not sampled from a run.

**What counts as a violation:** a module that talks to a model *and*
constructs a `CircuitIR`. Either alone is fine and both are common —
`ai/explainer.py` calls a model and takes a `CircuitIR` as a parameter,
`generators/rc_lowpass.py` constructs one and never calls a model. It is the
conjunction that puts model output into a design.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"

#: Everything that ships or could be run against the product. `scripts/` is
#: included because "no code path" is a claim about the repository, not about
#: one directory — a dev script that fed model output into a CircuitIR would
#: falsify it just as thoroughly. `tests/` is excluded: this file deliberately
#: writes a violating module to prove the scanner catches one.
_SCANNED_ROOTS = (BACKEND, ROOT / "scripts")

#: How a module talks to a model. `make_client` is the single factory every
#: call site uses (`ai/client.py`), so naming it catches any new caller.
_MODEL_CALL_NAMES = {"make_client", "OpenAICompatClient"}

#: Constructing a design.
_DESIGN_TYPE = "CircuitIR"

#: Every way a Pydantic model gets built from data. The first version of this
#: scanner looked only for `CircuitIR(...)` and therefore passed while
#: `ai/circuit_reasoner.py` — the exact module this gate exists to remove —
#: was still present, because it used `CircuitIR.model_validate(last_raw)`.
#: An analytic claim with a hole in the check is not an analytic claim.
_CONSTRUCTORS = {
    "model_validate",
    "model_validate_json",
    "model_construct",
    "parse_obj",
    "parse_raw",
    "parse_file",
    "from_orm",
    "construct",
}


def _python_files():
    found = []
    for root in _SCANNED_ROOTS:
        if root.exists():
            found += [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]
    return sorted(found)


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _analyse(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = set()
    constructs_design = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        # A call, not a type annotation. Annotations are how a module receives
        # a design; calls are how it makes one.
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == _DESIGN_TYPE:
                constructs_design = True
            elif isinstance(func, ast.Attribute):
                # CircuitIR.model_validate(...) and friends.
                rooted_at_design = (
                    isinstance(func.value, ast.Name) and func.value.id == _DESIGN_TYPE
                )
                if rooted_at_design and func.attr in _CONSTRUCTORS:
                    constructs_design = True
                elif func.attr == _DESIGN_TYPE:
                    constructs_design = True

    return names, constructs_design


class TestNoModuleBothCallsAModelAndBuildsADesign:
    def test_the_invariant_holds_across_the_whole_backend(self):
        violations = []
        for path in _python_files():
            names, constructs_design = _analyse(path)
            talks_to_model = bool(names & _MODEL_CALL_NAMES)
            if talks_to_model and constructs_design:
                violations.append(_rel(path))

        assert not violations, (
            "these modules both talk to a model and construct a CircuitIR, "
            "which is the one thing the architecture forbids:\n  "
            + "\n  ".join(violations)
            + "\n\nThe model writes IntentIR. A deterministic generator turns "
              "that into a CircuitIR. See CLAUDE.md, 'The One Rule'."
        )

    @pytest.mark.parametrize("construction", [
        "CircuitIR(**data)",
        "CircuitIR.model_validate(data)",
        "CircuitIR.model_validate_json(raw)",
        "CircuitIR.model_construct(**data)",
        "CircuitIR.parse_obj(data)",
    ])
    def test_the_scanner_catches_every_way_of_building_one(self, construction, tmp_path):
        # A test that can only pass proves nothing. `model_validate` is in
        # this list because the first version of the scanner missed it — and
        # that is exactly the form the module this gate removed was using, so
        # the check passed while the violation sat in the tree.
        module = tmp_path / "bad.py"
        module.write_text(
            "from ai.client import make_client\n"
            "from core.ir_schema import CircuitIR\n"
            "def bad(data, raw):\n"
            "    client = make_client()\n"
            f"    return {construction}\n",
            encoding="utf-8",
        )
        names, constructs_design = _analyse(module)
        assert names & _MODEL_CALL_NAMES
        assert constructs_design, f"scanner missed {construction}"

    def test_receiving_a_design_as_a_parameter_is_not_a_violation(self, tmp_path):
        # ai/explainer.py calls a model and takes a CircuitIR. That is fine and
        # must stay fine, or the invariant becomes unusable.
        module = tmp_path / "ok.py"
        module.write_text(
            "from ai.client import make_client\n"
            "from core.ir_schema import CircuitIR\n"
            "def explain(ir: CircuitIR) -> str:\n"
            "    return str(make_client())\n",
            encoding="utf-8",
        )
        names, constructs_design = _analyse(module)
        assert names & _MODEL_CALL_NAMES
        assert not constructs_design

    def test_scanner_reads_a_meaningful_number_of_modules(self):
        # Guards the other direction: a glob that silently matched nothing
        # would make the invariant vacuously true.
        assert len(_python_files()) > 25

    def test_scanner_covers_scripts_as_well_as_backend(self):
        # "No code path" is a claim about the repository. A dev script feeding
        # model output into a CircuitIR would falsify it just as thoroughly.
        scanned = {_rel(p).split("/")[0] for p in _python_files()}
        assert {"backend", "scripts"} <= scanned


class TestTheRemovedPath:
    def test_circuit_reasoner_no_longer_exists(self):
        # It was the LLM → CircuitIR path. Leaving it importable would leave
        # the path: the gate is that no such code exists, not that nothing
        # currently calls it.
        assert not (BACKEND / "ai" / "circuit_reasoner.py").exists()

        with pytest.raises(ModuleNotFoundError):
            import ai.circuit_reasoner  # noqa: F401

    def test_nothing_references_it(self):
        offenders = [
            _rel(p)
            for p in _python_files()
            if "circuit_reasoner" in p.read_text(encoding="utf-8")
            and p.name != "openai_compat.py"  # docstring history, no import
        ]
        assert not offenders, f"still referencing the removed path: {offenders}"


class TestTheReplacementPath:
    def test_the_design_route_generates_through_the_registry(self):
        source = (BACKEND / "api" / "routes" / "design.py").read_text(encoding="utf-8")
        assert "registry.dispatch(intent)" in source
        assert "generator.generate(intent)" in source

    def test_the_producer_writes_intent_not_design(self):
        names, constructs_design = _analyse(BACKEND / "ai" / "intent_producer.py")
        assert "make_client" in names, "the producer should be the module talking to the model"
        assert not constructs_design

    def test_generators_build_designs_without_a_model(self):
        names, constructs_design = _analyse(BACKEND / "generators" / "rc_lowpass.py")
        assert constructs_design
        assert not (names & _MODEL_CALL_NAMES)
