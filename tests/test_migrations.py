"""
Stage 2 — idempotent startup migrations. `db/migrations.py`.

`schema.sql` only runs on an empty data directory, so a column added after a
volume exists is missing on it and every INSERT naming that column fails.
Stage 2 adds two (`circuit_designs.intent_ir`, `.annotations`), and the fix is
statements that are safe to run on every start (decisions.md, X2 + X4, item 2).

These tests pin the three properties that make running DDL at startup
acceptable: every statement is additive and idempotent, a fresh volume and a
migrated one end up with the same columns, and a failure never stops the app.
"""

import asyncio
import re
from pathlib import Path

import pytest

from db.migrations import MIGRATIONS, apply_migrations, is_safe
from db.models import CircuitDesign

SCHEMA_SQL = Path(__file__).resolve().parent.parent / "backend" / "db" / "schema.sql"


class TestEveryStatementIsSafe:
    @pytest.mark.parametrize("statement", MIGRATIONS)
    def test_additive_and_idempotent(self, statement):
        assert is_safe(statement), f"not safe to run on every start: {statement}"

    @pytest.mark.parametrize("statement", [
        "ALTER TABLE circuit_designs ADD COLUMN intent_ir JSONB",          # not idempotent
        "ALTER TABLE circuit_designs DROP COLUMN IF EXISTS intent_ir",     # destructive
        "ALTER TABLE circuit_designs RENAME COLUMN a TO b",                # a data decision
        "DELETE FROM circuit_designs",
    ])
    def test_the_safety_check_refuses_what_it_should(self, statement):
        assert not is_safe(statement)

    def test_a_unique_index_is_allowed(self):
        """The explanation ledger is unique per design version. [F-0006]"""
        assert is_safe("CREATE UNIQUE INDEX IF NOT EXISTS idx_x ON t(a, b)")


class TestFreshAndMigratedVolumesAgree:
    def _added_columns(self):
        found = []
        for statement in MIGRATIONS:
            m = re.search(r"ALTER TABLE (\w+) ADD COLUMN IF NOT EXISTS (\w+)", statement)
            if m:
                found.append(m.groups())
        return found

    def test_every_migrated_column_is_in_schema_sql(self):
        schema = SCHEMA_SQL.read_text(encoding="utf-8")
        for table, column in self._added_columns():
            block = schema.split(f"CREATE TABLE {table} (", 1)[1].split(");", 1)[0]
            assert re.search(rf"^\s*{column}\s", block, re.M), (
                f"{table}.{column} is migrated onto old volumes but missing from "
                f"schema.sql, so a fresh volume would differ"
            )

    def test_every_migrated_column_is_on_the_model(self):
        columns = set(CircuitDesign.__table__.columns.keys())
        for table, column in self._added_columns():
            if table == "circuit_designs":
                assert column in columns

    def test_the_stage_2_columns_are_migrated(self):
        assert ("circuit_designs", "intent_ir") in self._added_columns()
        assert ("circuit_designs", "annotations") in self._added_columns()


class TestTheExplanationLedgerIsShippedEverywhere:
    """[2026-10-21, F-0006] The attempt ledger is a new table. It must exist
    in all three places or the poll cannot tell a lost task from a slow one:
    the model, schema.sql (a fresh volume) and the startup migrations (an
    old volume)."""

    def test_the_model_has_the_table(self):
        from db.models import ExplanationAttempt
        columns = set(ExplanationAttempt.__table__.columns.keys())
        assert {"circuit_id", "version", "attempts", "task_id", "queued_at"} <= columns

    def test_schema_sql_has_the_table(self):
        schema = SCHEMA_SQL.read_text(encoding="utf-8")
        assert "CREATE TABLE explanation_attempts" in schema
        for column in ("attempts", "task_id", "queued_at", "version"):
            assert column in schema.split("CREATE TABLE explanation_attempts (", 1)[1].split(");", 1)[0]

    def test_the_migrations_create_the_table(self):
        statements = " ".join(MIGRATIONS)
        assert "CREATE TABLE IF NOT EXISTS explanation_attempts" in statements

    def test_the_table_is_unique_per_design_version(self):
        """Two rows for one design version would leave the poll with two
        answers and no way to say which is the truth."""
        schema = SCHEMA_SQL.read_text(encoding="utf-8")
        assert "idx_explanation_attempts_design_version" in schema
        assert "ON explanation_attempts(circuit_id, version)" in schema

    def test_the_model_and_the_schema_agree_on_the_columns(self):
        from db.models import ExplanationAttempt
        schema = SCHEMA_SQL.read_text(encoding="utf-8")
        block = schema.split("CREATE TABLE explanation_attempts (", 1)[1].split(");", 1)[0]
        for column in ExplanationAttempt.__table__.columns.keys():
            if column == "id":
                continue
            assert column in block, f"explanation_attempts.{column} is on the model but not in schema.sql"


class TestFailureNeverStopsTheApp:
    def test_an_unreachable_database_is_logged_not_raised(self, caplog):
        class _Down:
            def begin(self):
                raise ConnectionRefusedError("postgres is not up")

        assert asyncio.run(apply_migrations(_Down())) is False
        assert "schema migrations not applied" in caplog.text

    def test_all_statements_run_in_order_when_it_is_up(self):
        executed = []

        class _Conn:
            async def execute(self, clause):
                executed.append(str(clause))

        class _Begin:
            async def __aenter__(self):
                return _Conn()

            async def __aexit__(self, *exc):
                return False

        class _Up:
            def begin(self):
                return _Begin()

        assert asyncio.run(apply_migrations(_Up())) is True
        assert executed == list(MIGRATIONS)
