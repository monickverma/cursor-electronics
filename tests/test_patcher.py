"""
Patcher regression tests — the invariant and the sequential-patch criterion.

Complements `test_ai_layer.py`, which already covers PatchResult construction and
`apply_to()` field mechanics. This file covers what was missing:

- THE INVARIANT: `patch()` never returns a full IR (`.claude/rules/code-style.md`).
  Previously unguarded by any test, despite being a stated project rule.
- Criterion 7 (5 sequential patches, no corruption) as an automated regression
  test. It passed by hand on 2026-06-02 but a manual pass that cannot be re-run
  is not a criterion that stays met.
- `patch()` behaviour with a mocked client, so the patch path has deterministic
  coverage even when ANTHROPIC_API_KEY is absent — which is the default for
  local runs and for CI without secrets.

Mocking note: `CircuitPatcher.__init__` calls `make_client()`, so tests patch
`ai.patcher.make_client` rather than the SDK itself. That keeps the test bound to
this module's own seam instead of Anthropic's internals.
"""

from __future__ import annotations

import pytest

from ai.patcher import CircuitPatcher, PatchResult
from core.ir_schema import CircuitIR


# ── Mock plumbing ─────────────────────────────────────────────────────────────

class _FakeContentBlock:
    def __init__(self, payload: dict):
        self.input = payload


class _FakeResponse:
    def __init__(self, payload: dict):
        self.content = [_FakeContentBlock(payload)]


class _FakeMessages:
    def __init__(self, payload: dict, recorder: dict):
        self._payload = payload
        self._recorder = recorder

    def create(self, **kwargs):
        self._recorder.update(kwargs)
        return _FakeResponse(self._payload)


class _FakeClient:
    def __init__(self, payload: dict, recorder: dict):
        self.messages = _FakeMessages(payload, recorder)


@pytest.fixture
def patcher_factory(monkeypatch):
    """Returns (build_patcher, recorder).

    `build_patcher(payload)` yields a CircuitPatcher whose model call returns
    `payload` verbatim. `recorder` captures the kwargs passed to messages.create
    so tests can assert on how the request was shaped.
    """
    recorder: dict = {}

    def build(payload: dict) -> CircuitPatcher:
        monkeypatch.setattr(
            "ai.patcher.make_client",
            lambda: _FakeClient(payload, recorder),
        )
        return CircuitPatcher()

    return build, recorder


# ── THE INVARIANT ─────────────────────────────────────────────────────────────

class TestPatchNeverReturnsFullIR:
    """`.claude/rules/code-style.md`: the patcher's job is surgical.

    Returning a full IR overwrites user customisations and makes patch_history
    meaningless. These tests exist so that regression is caught mechanically
    rather than in review.
    """

    def test_patch_returns_patchresult_not_circuitir(self, ir_dht22, patcher_factory):
        build, _ = patcher_factory
        patcher = build({"changes": [
            {"component_id": "R1", "field": "value", "new_value": "4.7k"}
        ]})
        result = patcher.patch(ir_dht22, "Change R1 to 4.7k")

        assert isinstance(result, PatchResult)
        assert not isinstance(result, CircuitIR)

    def test_patch_result_exposes_no_ir_level_fields(self, ir_dht22, patcher_factory):
        """A PatchResult must not carry circuit-level state.

        If any of these appear, someone has widened PatchResult into an IR
        carrier and the invariant is gone.
        """
        build, _ = patcher_factory
        patcher = build({"changes": []})
        result = patcher.patch(ir_dht22, "no-op")

        for forbidden in ("circuit_id", "components", "nodes", "connections",
                          "simulation_spec", "validation_rules"):
            assert not hasattr(result, forbidden), (
                f"PatchResult exposes '{forbidden}' — the patcher is leaking full "
                f"IR state. See .claude/rules/code-style.md (Patcher Invariant)."
            )

    def test_changes_are_field_level_not_whole_components(self, ir_dht22, patcher_factory):
        """Each change addresses one field, not a replacement component object."""
        build, _ = patcher_factory
        patcher = build({"changes": [
            {"component_id": "R1", "field": "value", "new_value": "4.7k"},
            {"component_id": "U1", "field": "part_number", "new_value": "DHT11"},
        ]})
        result = patcher.patch(ir_dht22, "swap parts")

        for change in result.changes:
            assert set(change.keys()) <= {"component_id", "field", "new_value"}
            assert not isinstance(change.get("new_value"), dict), (
                "new_value is a dict — this looks like a whole component being "
                "substituted rather than a single field being patched."
            )

    def test_patch_does_not_mutate_input_ir(self, ir_dht22, patcher_factory):
        build, _ = patcher_factory
        before = ir_dht22.model_dump_json()
        patcher = build({"changes": [
            {"component_id": "R1", "field": "value", "new_value": "4.7k"}
        ]})
        patcher.patch(ir_dht22, "Change R1 to 4.7k")

        assert ir_dht22.model_dump_json() == before, (
            "patch() mutated the IR it was given. It must be read-only over its input."
        )


# ── Request shaping ───────────────────────────────────────────────────────────

class TestPatchRequestShape:
    def test_uses_forced_tool_choice(self, ir_dht22, patcher_factory):
        """tool_use is forced — never free text. See code-style.md."""
        build, recorder = patcher_factory
        build({"changes": []}).patch(ir_dht22, "anything")

        assert recorder["tool_choice"] == {"type": "tool", "name": "apply_circuit_patch"}
        assert recorder["tools"][0]["name"] == "apply_circuit_patch"

    def test_existing_ir_is_sent_as_context(self, ir_dht22, patcher_factory):
        """Editing is stateful: the model must see the current design.

        Without this, the edit prompt degenerates into a generation prompt and
        the model regenerates rather than patches.
        """
        build, recorder = patcher_factory
        build({"changes": []}).patch(ir_dht22, "Change R1 to 4.7k")

        content = recorder["messages"][0]["content"]
        assert "CURRENT DESIGN" in content
        assert "CHANGE REQUEST" in content
        for comp in ir_dht22.components:
            assert comp.id in content, f"Component {comp.id} missing from patch context"

    def test_summarize_lists_every_component(self, ir_modbus):
        summary = CircuitPatcher._summarize(ir_modbus)
        for comp in ir_modbus.components:
            assert comp.id in summary
            assert comp.part_number in summary


# ── Criterion 7: five sequential patches, no corruption ───────────────────────

class TestSequentialPatches:
    """Automates Phase 1 criterion 7.

    Verified manually on 2026-06-02 (v1→v6) but never as a test, so it could
    not be re-run. Now it can.
    """

    PATCH_SEQUENCE = [
        {"component_id": "R1", "field": "value", "new_value": "4.7k"},
        {"component_id": "R1", "field": "justification",
         "new_value": "Lower pull-up value chosen to improve rise time on the DATA line."},
        {"component_id": "R1", "field": "package", "new_value": "0603"},
        {"component_id": "R1", "field": "manufacturer", "new_value": "Yageo"},
        {"component_id": "R1", "field": "confidence", "new_value": 0.95},
    ]

    def test_five_sequential_patches_keep_ir_valid(self, ir_dht22):
        ir = ir_dht22
        for i, change in enumerate(self.PATCH_SEQUENCE, start=1):
            ir = PatchResult({"changes": [change]}).apply_to(ir)
            CircuitIR.model_validate(ir.model_dump())
            assert ir.version == ir_dht22.version + i

    def test_five_sequential_patches_preserve_component_count(self, ir_dht22):
        ir = ir_dht22
        for change in self.PATCH_SEQUENCE:
            ir = PatchResult({"changes": [change]}).apply_to(ir)

        assert len(ir.components) == len(ir_dht22.components)
        assert {c.id for c in ir.components} == {c.id for c in ir_dht22.components}

    def test_later_patches_do_not_erase_earlier_ones(self, ir_dht22):
        """The regression this whole class exists to catch.

        If the patcher ever regenerates instead of patching, edits 1–4 vanish
        when edit 5 lands and only the last change survives.
        """
        ir = ir_dht22
        for change in self.PATCH_SEQUENCE:
            ir = PatchResult({"changes": [change]}).apply_to(ir)

        r1 = next(c for c in ir.components if c.id == "R1")
        assert r1.value == "4.7k"
        assert "rise time" in r1.justification
        assert r1.package == "0603"
        assert r1.manufacturer == "Yageo"
        assert r1.confidence == pytest.approx(0.95)

    def test_untouched_components_are_byte_identical(self, ir_dht22):
        untouched_before = {
            c.id: c.model_dump_json()
            for c in ir_dht22.components if c.id != "R1"
        }

        ir = ir_dht22
        for change in self.PATCH_SEQUENCE:
            ir = PatchResult({"changes": [change]}).apply_to(ir)

        for comp in ir.components:
            if comp.id in untouched_before:
                assert comp.model_dump_json() == untouched_before[comp.id], (
                    f"Component {comp.id} changed during a patch that never "
                    f"referenced it."
                )

    def test_nodes_and_connections_survive_patching(self, ir_dht22):
        ir = ir_dht22
        for change in self.PATCH_SEQUENCE:
            ir = PatchResult({"changes": [change]}).apply_to(ir)

        assert [n.id for n in ir.nodes] == [n.id for n in ir_dht22.nodes]
        assert len(ir.connections) == len(ir_dht22.connections)

    def test_connection_refs_still_resolve_after_patching(self, ir_dht22):
        """No dangling references — the corruption mode that matters."""
        ir = ir_dht22
        for change in self.PATCH_SEQUENCE:
            ir = PatchResult({"changes": [change]}).apply_to(ir)

        component_ids = {c.id for c in ir.components}
        node_ids = {n.id for n in ir.nodes}
        for conn in ir.connections:
            assert conn.component_id in component_ids
            assert conn.node_id in node_ids


# ── Malformed patch handling ──────────────────────────────────────────────────

class TestMalformedPatches:
    def test_unknown_component_id_is_skipped_not_applied(self, ir_dht22):
        before = ir_dht22.model_dump_json()
        patched = PatchResult({"changes": [
            {"component_id": "GHOST_99", "field": "value", "new_value": "1k"}
        ]}).apply_to(ir_dht22)

        assert ir_dht22.model_dump_json() == before
        assert [c.model_dump() for c in patched.components] == \
               [c.model_dump() for c in ir_dht22.components]

    def test_empty_field_name_is_skipped(self, ir_dht22):
        patched = PatchResult({"changes": [
            {"component_id": "R1", "field": "", "new_value": "x"}
        ]}).apply_to(ir_dht22)
        CircuitIR.model_validate(patched.model_dump())

    def test_missing_keys_do_not_raise(self, ir_dht22):
        patched = PatchResult({"changes": [{}]}).apply_to(ir_dht22)
        assert patched.version == ir_dht22.version + 1

    def test_empty_patch_still_increments_version(self, ir_dht22):
        """An empty patch is a real event and belongs in patch_history."""
        patched = PatchResult({"changes": []}).apply_to(ir_dht22)
        assert patched.version == ir_dht22.version + 1

    @pytest.mark.parametrize("bad_payload", [{}, {"changes": None}])
    def test_degenerate_payloads_do_not_crash_construction(self, bad_payload):
        result = PatchResult(bad_payload)
        assert result.changes in ([], None)
