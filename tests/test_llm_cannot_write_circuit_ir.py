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

**What counts as a violation:** a module that talks to a model *and* writes a
`CircuitIR` — constructs one, copies one with `update=`, or mutates one in
place. Either half alone is fine and both are common: `ai/explainer.py` calls
a model and reads a `CircuitIR` it is given, `generators/rc_lowpass.py`
constructs one and never calls a model. It is the conjunction that puts model
output into a design.

**"Talks to a model" is transitive — the third version of this scanner.** The
first looked only for `CircuitIR(...)` and passed while `circuit_reasoner.py`
built designs with `model_validate`. The second missed `model_copy(update=...)`
and passed while `ai/patcher.py` wrote through it. The Stage 2 verification
then showed the per-module check itself was the hole: it recognised a model
only by the client factory's name, so a module that reached a model through a
wrapper — `IntentPatcher`, `ExplanationEngine().client` — or mutated a design
in place (`ir.components[0].value = raw`) passed however it used the output.
Now:

- a top-level function, class or module-level name that references the client
  factory, a `.messages.create(...)` call, or another such name is
  **model-facing**, to a fixed point across the whole repository, with imports
  resolved to the module that defines each name;
- a module that references any model-facing name talks to a model;
- in such a module, constructions, `model_copy(update=...)`, attribute and
  item writes to design fields, mutating calls on them, and `setattr` /
  `__dict__` are all writes;
- a write that has been reviewed is listed in `_REVIEWED` with its reason,
  matched by file and exact source text, and an entry that no longer matches
  anything fails the suite.

**Still outside it**, stated so nobody reads more into a green run: a model
reached only through an object passed in as a parameter whose class is never
named (unless it calls `.messages.create` directly); names built at runtime
(`getattr(module, "Circuit" + "IR")`, `importlib`); and model output that goes
through storage — a database row, a file — before a separate process builds
a design from it.
"""

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

import pytest

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"

#: Everything that ships or could be run against the product. `scripts/` is
#: included because "no code path" is a claim about the repository, not about
#: one directory — a dev script that fed model output into a CircuitIR would
#: falsify it just as thoroughly. `tests/` is excluded: this file deliberately
#: writes violating modules to prove the scanner catches them.
_SCANNED_ROOTS = (BACKEND, ROOT / "scripts")

#: Where every model call starts. `make_client` is the single factory every
#: call site uses (`ai/client.py`); `OpenAICompatClient` is what it may return.
#: A `.messages.create(...)` call is a model call whatever the receiver is.
_SEEDS = frozenset({"ai.client:make_client", "ai.openai_compat:OpenAICompatClient"})
_SEED_NAMES = frozenset(q.split(":")[1] for q in _SEEDS)
_MESSAGES_CREATE = "<messages.create>"

_DESIGN_TYPE = "CircuitIR"

#: Every way a Pydantic model gets built from data. The first version of this
#: scanner looked only for `CircuitIR(...)` and therefore passed while
#: `ai/circuit_reasoner.py` — the exact module this gate exists to remove —
#: was still present, because it used `CircuitIR.model_validate(last_raw)`.
_CONSTRUCTORS = frozenset({
    "model_validate", "model_validate_json", "model_construct",
    "parse_obj", "parse_raw", "parse_file", "from_orm", "construct",
})

#: Methods that change a list, dict or model in place.
_MUTATORS = frozenset({
    "append", "extend", "insert", "pop", "remove", "clear", "update", "setdefault",
    "popitem", "sort", "reverse", "__setitem__", "__delitem__", "__setattr__", "__delattr__",
})

#: Writes into a design inside a model-facing module that a person has read and
#: judged safe. Matched by file and exact source text; the reason is required.
_REVIEWED: Dict[Tuple[str, str], str] = {
    ("backend/api/routes/patch.py", "CircuitIR.model_validate(design.ir_json)"):
        "rebuilds the stored design record read from Postgres by `_load_owned`; "
        "the patcher's output reaches a design only through registry dispatch "
        "and `realize()`",
    # `generator` is a CircuitIR field since Stage 2 and a request-log field
    # since Stage 1; these two set the log row, not a design.
    ("backend/api/routes/design.py", "ctx.generator = f'{generator.name}@{generator.version}'"):
        "sets the request-log context (RequestLogContext.generator), not a design",
    ("backend/api/routes/patch.py", "ctx.generator = tag"):
        "sets the request-log context (RequestLogContext.generator), not a design",
}


def _design_fields() -> FrozenSet[str]:
    """Every field name on CircuitIR and the models it is built from."""
    import core.ir_schema as schema
    from pydantic import BaseModel

    names: Set[str] = set()
    for obj in vars(schema).values():
        if isinstance(obj, type) and issubclass(obj, BaseModel) and obj.__module__ == schema.__name__:
            names |= set(obj.model_fields)
    return frozenset(names)


_DESIGN_FIELDS = _design_fields()


# ── Reading one module ───────────────────────────────────────────────────────

def _python_files() -> List[Path]:
    found: List[Path] = []
    for root in _SCANNED_ROOTS:
        if root.exists():
            found += [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]
    return sorted(found)


def _rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _module_name(path: Path) -> str:
    """The dotted name the module is imported by. Backend is on sys.path, so `ai.client`."""
    for root, prefix in ((BACKEND, ""), (ROOT / "scripts", "scripts.")):
        try:
            parts = list(path.relative_to(root).with_suffix("").parts)
        except ValueError:
            continue
        if parts[-1] == "__init__":
            parts.pop()
        return prefix + ".".join(parts)
    return path.stem


@dataclass
class _Site:
    line: int
    source: str
    kind: str


@dataclass
class _Facts:
    path: Path
    module: str
    #: Every Name, Attribute and import alias spelled in the module.
    names: Set[str] = field(default_factory=set)
    #: Qualified names each top-level unit references ("ai.client:make_client").
    units: Dict[str, Set[str]] = field(default_factory=dict)
    #: Qualified names referenced anywhere in the module.
    refs: Set[str] = field(default_factory=set)
    writes: List[_Site] = field(default_factory=list)


def _root_name(node: ast.AST) -> Optional[str]:
    while isinstance(node, (ast.Attribute, ast.Subscript, ast.Call)):
        node = node.func if isinstance(node, ast.Call) else node.value
    return node.id if isinstance(node, ast.Name) else None


def _touches_design_field(node: ast.AST) -> bool:
    """`ir.components[0]`, `x.value` — an attribute chain through a design field name."""
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        if isinstance(node, ast.Attribute) and node.attr in _DESIGN_FIELDS:
            return True
        node = node.value
    return False


class _Reader(ast.NodeVisitor):
    def __init__(self, facts: _Facts, tree: ast.Module) -> None:
        self.f = facts
        self.imports: Dict[str, str] = {}        # local name -> "module:name"
        self.modules: Dict[str, str] = {}        # local alias -> module
        self.local: Set[str] = set()             # top-level names defined here
        self.design_aliases: Set[str] = {_DESIGN_TYPE}
        self._current: Optional[Set[str]] = None
        self._collect_top_level(tree)

    # Imports and top-level names are resolved before anything is read, so a
    # function can reference a name imported or defined further down.
    def _collect_top_level(self, tree: ast.Module) -> None:
        package = self.f.module.split(".")[:-1] if not self.f.path.name == "__init__.py" \
            else self.f.module.split(".")
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    anchor = package[: len(package) - (node.level - 1)] if node.level > 1 else package
                    base = ".".join([*anchor, *([base] if base else [])])
                for alias in node.names:
                    local = alias.asname or alias.name
                    self.imports[local] = f"{base}:{alias.name}"
                    self.modules.setdefault(local, f"{base}.{alias.name}".strip("."))
                    if alias.name == _DESIGN_TYPE:
                        self.design_aliases.add(local)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname:
                        self.modules[alias.asname] = alias.name
                    else:
                        self.modules[alias.name.split(".")[0]] = alias.name.split(".")[0]
        for node in tree.body:
            for name in self._unit_names(node):
                self.local.add(name)

    @staticmethod
    def _unit_names(node: ast.stmt) -> List[str]:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return [node.name]
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            return [t.id for t in targets if isinstance(t, ast.Name)]
        return []

    def read(self, tree: ast.Module) -> None:
        for node in tree.body:
            names = self._unit_names(node)
            refs: Set[str] = set()
            self._current = refs
            self.visit(node)
            self._current = None
            for name in names:
                self.f.units[f"{self.f.module}:{name}"] = refs
            self.f.refs |= refs

    # ── references ──────────────────────────────────────────────────────
    def _ref(self, qualified: str) -> None:
        if self._current is not None:
            self._current.add(qualified)

    def _dotted(self, node: ast.AST) -> Optional[List[str]]:
        parts: List[str] = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if not isinstance(node, ast.Name):
            return None
        parts.append(node.id)
        return parts[::-1]

    def visit_Name(self, node: ast.Name) -> None:
        self.f.names.add(node.id)
        if node.id in self.imports:
            self._ref(self.imports[node.id])
        elif node.id in self.local:
            self._ref(f"{self.f.module}:{node.id}")
        if node.id in _SEED_NAMES:
            self._ref(next(q for q in _SEEDS if q.endswith(":" + node.id)))

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self.f.names.add(node.attr)
        dotted = self._dotted(node)
        if dotted:
            head = dotted[0]
            if head in self.modules:
                module = ".".join([self.modules[head], *dotted[1:-1]])
                self._ref(f"{module}:{dotted[-1]}")
        if node.attr in _SEED_NAMES:
            self._ref(next(q for q in _SEEDS if q.endswith(":" + node.attr)))
        if node.attr == "__dict__":
            self._write(node, "touches __dict__")
        self.generic_visit(node)

    def visit_alias(self, node: ast.alias) -> None:
        # `from core.ir_schema import CircuitIR` is a reference too, and the
        # only one in a module that never spells the type again.
        self.f.names.add(node.name.rsplit(".", 1)[-1])
        if node.asname:
            self.f.names.add(node.asname)

    # ── writes ──────────────────────────────────────────────────────────
    def _write(self, node: ast.AST, kind: str) -> None:
        self.f.writes.append(_Site(getattr(node, "lineno", 0), ast.unparse(node), kind))

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "create" and \
                isinstance(func.value, ast.Attribute) and func.value.attr == "messages":
            self._ref(_MESSAGES_CREATE)
        if isinstance(func, ast.Name):
            if func.id in self.design_aliases:
                self._write(node, "constructs")
            elif func.id in ("setattr", "delattr"):
                self._write(node, func.id)
        elif isinstance(func, ast.Attribute):
            receiver = func.value
            rooted_at_design = (
                (isinstance(receiver, ast.Name) and receiver.id in self.design_aliases)
                or (isinstance(receiver, ast.Attribute) and receiver.attr == _DESIGN_TYPE)
            )
            if func.attr == _DESIGN_TYPE or (rooted_at_design and func.attr in _CONSTRUCTORS):
                self._write(node, "constructs")
            elif func.attr == "model_copy" and any(k.arg == "update" for k in node.keywords):
                # The receiver's type is not known statically. In a module that
                # talks to a model, any copy-with-update is treated as a write.
                self._write(node, "model_copy(update=...)")
            elif func.attr in _MUTATORS and _touches_design_field(receiver) \
                    and _root_name(receiver) not in ("self", "cls"):
                self._write(node, f"mutates via .{func.attr}()")
            elif func.attr == "__setattr__" and isinstance(receiver, ast.Name) and receiver.id == "object":
                self._write(node, "object.__setattr__")
        self.generic_visit(node)

    def _check_target(self, target: ast.AST, stmt: ast.AST) -> None:
        if isinstance(target, (ast.Tuple, ast.List)):
            for t in target.elts:
                self._check_target(t, stmt)
        elif isinstance(target, ast.Starred):
            self._check_target(target.value, stmt)
        elif isinstance(target, (ast.Attribute, ast.Subscript)):
            if _root_name(target) in ("self", "cls"):
                return
            if (isinstance(target, ast.Attribute) and target.attr in _DESIGN_FIELDS) \
                    or _touches_design_field(target):
                self._write(stmt, "assigns a design field")

    def visit_Assign(self, node: ast.Assign) -> None:
        for t in node.targets:
            self._check_target(t, node)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._check_target(node.target, node)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self._check_target(node.target, node)
        self.generic_visit(node)

    def visit_Delete(self, node: ast.Delete) -> None:
        for t in node.targets:
            self._check_target(t, node)
        self.generic_visit(node)


def _analyse(path: Path) -> _Facts:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    facts = _Facts(path=path, module=_module_name(path))
    reader = _Reader(facts, tree)
    reader.read(tree)
    return facts


# ── Across the repository ────────────────────────────────────────────────────

def _model_facing(all_facts: Iterable[_Facts]) -> Set[str]:
    """Qualified names that reach a model, directly or through another such name."""
    all_facts = list(all_facts)
    facing = set(_SEEDS) | {_MESSAGES_CREATE}
    changed = True
    while changed:
        changed = False
        for facts in all_facts:
            for unit, refs in facts.units.items():
                if unit not in facing and refs & facing:
                    facing.add(unit)
                    changed = True
    return facing


def _scan(extra: Iterable[Path] = ()) -> Tuple[Dict[str, List[_Site]], Dict[str, _Facts], Set[str]]:
    """Violations by file, every module's facts, and the model-facing names."""
    all_facts = {_rel(p): _analyse(p) for p in [*_python_files(), *extra]}
    facing = _model_facing(all_facts.values())
    violations: Dict[str, List[_Site]] = {}
    for rel, facts in all_facts.items():
        if not (facts.refs & facing):
            continue
        unreviewed = [s for s in facts.writes if (rel, s.source) not in _REVIEWED]
        if unreviewed:
            violations[rel] = unreviewed
    return violations, all_facts, facing


def _talks_to_model(rel: str, all_facts: Dict[str, _Facts], facing: Set[str]) -> bool:
    return bool(all_facts[rel].refs & facing)


def _write_module(tmp_path: Path, name: str, source: str) -> Path:
    path = tmp_path / f"{name}.py"
    path.write_text(source, encoding="utf-8")
    return path


# ── The invariant ────────────────────────────────────────────────────────────

class TestNoModuleBothCallsAModelAndWritesADesign:
    def test_the_invariant_holds_across_the_whole_repository(self):
        violations, _, _ = _scan()
        assert not violations, (
            "these modules talk to a model and write a CircuitIR, which is the one "
            "thing the architecture forbids:\n  "
            + "\n  ".join(f"{rel}:{s.line}  {s.kind}: {s.source[:100]}"
                          for rel, sites in violations.items() for s in sites)
            + "\n\nThe model writes IntentIR. A deterministic generator turns that "
              "into a CircuitIR. See CLAUDE.md, 'The One Rule'. If a write here "
              "is genuinely safe, add it to _REVIEWED with the reason."
        )

    def test_every_reviewed_write_still_exists(self):
        # A stale exemption is how a scanner stops scanning: it outlives the
        # line it excused and waits for a new line with the same text.
        _, all_facts, _ = _scan()
        for (rel, source), reason in _REVIEWED.items():
            assert reason.strip(), f"{rel}: a reviewed write needs a reason"
            assert rel in all_facts, f"_REVIEWED names a file that is gone: {rel}"
            assert any(s.source == source for s in all_facts[rel].writes), \
                f"_REVIEWED entry no longer matches anything in {rel}: {source}"

    def test_the_modules_that_reach_a_model_are_the_expected_ones(self):
        # Guards the transitive closure from silently collapsing: if resolution
        # broke, the wrapper-using routes would drop out and the invariant
        # would pass vacuously over them.
        _, all_facts, facing = _scan()
        for rel in ("backend/ai/intent_producer.py", "backend/ai/intent_patcher.py",
                    "backend/ai/explainer.py", "backend/api/routes/design.py",
                    "backend/api/routes/patch.py"):
            assert _talks_to_model(rel, all_facts, facing), rel
        for rel in ("backend/generators/rc_lowpass.py", "backend/generators/realize.py",
                    "backend/core/intent_patch.py"):
            assert not _talks_to_model(rel, all_facts, facing), rel

    def test_scanner_reads_a_meaningful_number_of_modules(self):
        # A glob that silently matched nothing would make the invariant vacuous.
        assert len(_python_files()) > 25

    def test_scanner_covers_scripts_as_well_as_backend(self):
        scanned = {_rel(p).split("/")[0] for p in _python_files()}
        assert {"backend", "scripts"} <= scanned


class TestTheScannerCatchesEveryForm:
    """Negative controls. A check that can only pass proves nothing."""

    DIRECT = "from ai.client import make_client\nfrom core.ir_schema import CircuitIR\n"

    @pytest.mark.parametrize("write", [
        "CircuitIR(**data)",
        "CircuitIR.model_validate(data)",
        "CircuitIR.model_validate_json(raw)",
        "CircuitIR.model_construct(**data)",
        "CircuitIR.parse_obj(data)",
        # The form the Phase 1 patcher used, missed until Stage 2.
        "data.model_copy(update={'components': raw})",
    ])
    def test_every_way_of_building_one(self, write, tmp_path):
        path = _write_module(tmp_path, "bad", self.DIRECT + (
            "def bad(data, raw):\n"
            "    client = make_client()\n"
            f"    return {write}\n"))
        violations, _, _ = _scan([path])
        assert _rel(path) in violations, f"scanner missed {write}"

    @pytest.mark.parametrize("body", [
        "ir.components[0].value = raw['value']",
        "ir.components.append(raw)",
        "ir.constraints['cutoff_hz'] = raw",
        "ir.version += 1",
        "setattr(ir, 'version', raw)",
        "object.__setattr__(ir, 'version', raw)",
        "ir.__dict__.update(raw)",
        "del ir.components[0]",
    ])
    def test_writing_into_a_design_it_was_given(self, body, tmp_path):
        # Found by the Stage 2 verification: receiving a design and changing it
        # in place wrote model output into it without constructing anything.
        path = _write_module(tmp_path, "mutates", self.DIRECT + (
            "def bad(ir: CircuitIR):\n"
            "    raw = make_client().messages.create()\n"
            f"    {body}\n"
            "    return ir\n"))
        violations, _, _ = _scan([path])
        assert _rel(path) in violations, f"scanner missed {body}"

    def test_a_model_reached_through_a_wrapper_class(self, tmp_path):
        # Found by the Stage 2 verification: this module never names the
        # client factory, so the per-module scanner passed it.
        path = _write_module(tmp_path, "via_wrapper", (
            "from ai.intent_patcher import IntentPatcher\n"
            "from core.ir_schema import CircuitIR\n"
            "def bad(content):\n"
            "    raw = IntentPatcher()._call(content)\n"
            "    return CircuitIR.model_validate(raw)\n"))
        violations, _, _ = _scan([path])
        assert _rel(path) in violations

    def test_a_model_reached_through_an_ai_modules_client(self, tmp_path):
        path = _write_module(tmp_path, "via_client", (
            "from ai.explainer import ExplanationEngine\n"
            "from core.ir_schema import CircuitIR\n"
            "def bad(p):\n"
            "    r = ExplanationEngine().client.messages.create(**p)\n"
            "    return CircuitIR(**r.content[0].input)\n"))
        violations, _, _ = _scan([path])
        assert _rel(path) in violations

    def test_a_wrapper_two_modules_away(self, tmp_path):
        # The closure is computed to a fixed point, not one hop.
        helper = _write_module(tmp_path, "helper_a", (
            "from ai.client import make_client\n"
            "class Helper:\n"
            "    def ask(self):\n"
            "        return make_client().messages.create()\n"))
        middle = _write_module(tmp_path, "helper_b", (
            "from helper_a import Helper\n"
            "def fetch():\n"
            "    return Helper().ask()\n"))
        bad = _write_module(tmp_path, "helper_c", (
            "from helper_b import fetch\n"
            "from core.ir_schema import CircuitIR as Design\n"
            "def bad():\n"
            "    return Design(**fetch())\n"))
        violations, _, _ = _scan([helper, middle, bad])
        assert _rel(bad) in violations

    def test_a_duck_typed_client(self, tmp_path):
        path = _write_module(tmp_path, "duck", (
            "from core.ir_schema import CircuitIR\n"
            "def bad(any_client):\n"
            "    r = any_client.messages.create(model='m')\n"
            "    return CircuitIR(**r.content[0].input)\n"))
        violations, _, _ = _scan([path])
        assert _rel(path) in violations

    def test_a_review_covers_only_the_exact_write_it_names(self, tmp_path, monkeypatch):
        # The patch route's reviewed writes must not excuse a new one added
        # beside them. The copy is scanned *as* the real file, replacing it, so
        # every reviewed entry applies and only the new write may surface.
        real = "backend/api/routes/patch.py"
        source = (ROOT / real).read_text(encoding="utf-8")
        source += "\n\ndef smuggled(raw):\n    return CircuitIR(**raw)\n"
        path = _write_module(tmp_path, "patch_copy", source)
        original_rel = _rel
        monkeypatch.setattr(
            sys.modules[__name__], "_rel",
            lambda p: real if p == path else original_rel(p),
        )
        violations, _, _ = _scan([path])
        assert [s.source for s in violations.get(real, [])] == ["CircuitIR(**raw)"]


class TestWhatIsNotAViolation:
    """Guards the rule from over-reach, or it becomes unusable and gets exempted."""

    def test_receiving_and_reading_a_design(self, tmp_path):
        # ai/explainer.py calls a model and takes a CircuitIR. That is fine.
        path = _write_module(tmp_path, "reads", (
            "from ai.client import make_client\n"
            "from core.ir_schema import CircuitIR\n"
            "def explain(ir: CircuitIR) -> str:\n"
            "    parts = [c.value for c in ir.components]\n"
            "    return str(make_client()) + ','.join(parts)\n"))
        violations, _, _ = _scan([path])
        assert _rel(path) not in violations

    def test_copying_a_design_without_update(self, tmp_path):
        path = _write_module(tmp_path, "copies", (
            "from ai.client import make_client\n"
            "from core.ir_schema import CircuitIR\n"
            "def f(ir: CircuitIR):\n"
            "    make_client()\n"
            "    return ir.model_copy()\n"))
        violations, _, _ = _scan([path])
        assert _rel(path) not in violations

    def test_an_object_setting_its_own_attributes(self, tmp_path):
        # `self.client = make_client()` in every AI module's __init__.
        path = _write_module(tmp_path, "own_attrs", (
            "from ai.client import make_client\n"
            "class Engine:\n"
            "    def __init__(self):\n"
            "        self.client = make_client()\n"
            "        self.version = 1\n"))
        violations, _, _ = _scan([path])
        assert _rel(path) not in violations

    def test_building_a_design_without_a_model(self, tmp_path):
        path = _write_module(tmp_path, "generator", (
            "from core.ir_schema import CircuitIR\n"
            "def generate(data):\n"
            "    return CircuitIR(**data)\n"))
        violations, _, _ = _scan([path])
        assert _rel(path) not in violations


class TestTheRemovedPath:
    def test_circuit_reasoner_no_longer_exists(self):
        # It was the LLM → CircuitIR path. Leaving it importable would leave
        # the path: the gate is that no such code exists, not that nothing
        # currently calls it.
        assert not (BACKEND / "ai" / "circuit_reasoner.py").exists()

        with pytest.raises(ModuleNotFoundError):
            import ai.circuit_reasoner  # noqa: F401

    def test_nothing_references_it(self):
        # No carve-out. An exemption kept for convenience is how a scanner
        # stops scanning.
        offenders = [
            _rel(p)
            for p in _python_files()
            if "circuit_reasoner" in p.read_text(encoding="utf-8")
        ]
        assert not offenders, f"still referencing the removed path: {offenders}"


class TestTheRemovedPatchPath:
    def test_circuit_patcher_no_longer_exists(self):
        # Stage 2, X4. It wrote model output into CircuitIR component fields.
        assert not (BACKEND / "ai" / "patcher.py").exists()
        with pytest.raises(ModuleNotFoundError):
            import ai.patcher  # noqa: F401

    def test_the_intent_patcher_never_names_the_design_type(self):
        # It is told part ids as plain data. Not importing CircuitIR at all is
        # stronger than not writing one, and it is cheap to keep true.
        facts = _analyse(BACKEND / "ai" / "intent_patcher.py")
        assert "make_client" in facts.names
        assert _DESIGN_TYPE not in facts.names
        assert not facts.writes


class TestTheReplacementPath:
    def test_the_design_route_generates_through_the_registry(self):
        source = (BACKEND / "api" / "routes" / "design.py").read_text(encoding="utf-8")
        assert "registry.dispatch(intent)" in source
        assert "realize(generator, intent)" in source

    def test_the_patch_route_regenerates_through_the_registry(self):
        # X4: an edit goes through the same gate as a fresh request.
        source = (BACKEND / "api" / "routes" / "patch.py").read_text(encoding="utf-8")
        assert "registry.dispatch(new_intent)" in source
        assert "realize(generator, new_intent)" in source

    def test_the_producer_writes_intent_not_design(self):
        facts = _analyse(BACKEND / "ai" / "intent_producer.py")
        assert "make_client" in facts.names, "the producer should be the module talking to the model"
        assert not facts.writes

    def test_generators_build_designs_without_a_model(self):
        _, all_facts, facing = _scan()
        rel = "backend/generators/rc_lowpass.py"
        assert any(s.kind == "constructs" for s in all_facts[rel].writes)
        assert not _talks_to_model(rel, all_facts, facing)
