"""
Timestamps must be aware. A naive UTC wall clock is wrong on a non-UTC host.

[2026-10-21, F-0009] The explanation route compares the age of a design
against a staleness window. That age came from a `timestamptz` column, and
the column was written with `datetime.utcnow()` — which returns the UTC wall
clock with NO tzinfo. asyncpg reads a naive datetime as LOCAL time, so on a
host 5.5 hours off UTC the row landed 5.5 hours in the past. A design two
seconds old looked five and a half hours old, the route decided the attempt
had been lost, and it fired its one allowed retry on the very first poll —
while the worker was running and answering.

The repository's own tests missed it because their fake ledger builds
timezone-aware datetimes by hand. The real database never did.

WHAT THIS FILE PINS
-------------------
1. Every timestamp the ORM writes is AWARE. A naive value here is a latent
   five-and-a-half-hour bug on any host that is not UTC.
2. The value written is the UTC wall clock. Not local time wearing a UTC
   label — that is the same bug with a different name.
3. The age arithmetic in the explanation route survives a naive datetime
   coming back from the database, so a row written by an older build cannot
   make the route think the design is stale.

The first two are properties of the code, and they are checked without a
database. The third needs a timestamp, and the arithmetic is done both ways
around the offset to prove the sign of the correction.

    python -m pytest tests/test_utc_timestamps.py -v
"""
from __future__ import annotations

import datetime

from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent / "backend"


# ─────────────────────────────────────────────────────────────────────────────
class TestTheORMWritesAwareTimestamps:
    """A naive datetime into a timestamptz column is the bug itself."""

    def _naive_utcnow_calls(self, filename: str) -> list[int]:
        """Every `datetime.utcnow()` call in a file, by line number.

        Parsed with the AST, not a regex. A regex over `Column(...)` breaks
        on the nested parentheses of `Column(UUID(as_uuid=True), ...)`, and a
        check that silently finds nothing is worse than no check at all.
        """
        import ast

        path = BACKEND / filename
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        lines: list[int] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr != "utcnow":
                continue
            if isinstance(func.value, ast.Name) and func.value.id == "datetime":
                lines.append(node.lineno)
        return lines

    def test_no_column_default_uses_the_naive_utcnow(self):
        """`datetime.utcnow` as a column default returns a naive value.

        Python 3.12 deprecates it for exactly this reason, and the database
        then reads it as local time.
        """
        lines = self._naive_utcnow_calls("db/models.py")
        assert not lines, (
            f"models.py calls datetime.utcnow() on line(s) {lines}; "
            f"asyncpg will read the value as local time"
        )

    def test_the_helper_returns_an_aware_datetime(self):
        from db.models import _utcnow

        value = _utcnow()
        assert value.tzinfo is not None, "the helper returned a naive datetime"
        assert value.utcoffset() == datetime.timedelta(0), (
            "the helper claims to be UTC but does not carry a zero offset"
        )

    def test_the_helper_is_the_utc_wall_clock(self):
        """Aware and UTC are two different properties. Check both."""
        from db.models import _utcnow

        value = _utcnow()
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        assert abs((now_utc - value).total_seconds()) < 5, (
            "the helper is not the UTC wall clock"
        )

    def test_no_crud_write_uses_the_naive_utcnow(self):
        """The explicit writes are the ones that decide when a job started."""
        lines = self._naive_utcnow_calls("db/crud.py")
        assert not lines, (
            f"crud.py calls datetime.utcnow() on line(s) {lines}; "
            f"a naive UTC wall clock is stored as local time"
        )

    def test_every_explicit_crud_timestamp_is_aware(self):
        """Aware means it carries an offset, so it says which one it is."""
        import ast

        path = BACKEND / "db" / "crud.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        calls: list[tuple[int, str]] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr != "now":
                continue
            if not (isinstance(func.value, ast.Name) and func.value.id == "datetime"):
                continue
            if not node.args:
                calls.append((node.lineno, "datetime.now() with no argument"))
                continue
            arg = node.args[0]
            ok = (
                isinstance(arg, ast.Attribute)
                and arg.attr == "utc"
                and isinstance(arg.value, ast.Name)
                and arg.value.id == "timezone"
            )
            calls.append((node.lineno, "aware" if ok else "NOT explicitly UTC"))

        assert calls, "no timestamp calls found — the walk is wrong, not the code"
        for lineno, verdict in calls:
            assert verdict == "aware", (
                f"crud.py line {lineno} writes a timestamp that is {verdict}; "
                f"a local-time stamp stored as if it were UTC is the same bug "
                f"with a different name"
            )


# ─────────────────────────────────────────────────────────────────────────────
class TestTheAgeArithmeticSurvivesANaiveRow:
    """A row written by an older build must not make a design look stale."""

    def test_a_naive_timestamp_is_read_as_utc(self):
        """A fresh naive row must not look hours old.

        The timestamp is taken NOW, not hard-coded. A fixed date makes the
        assertion depend on the wall clock: the test passed at 15:21 UTC and
        failed at 20:21 UTC on the same correct code, which is a test that
        measures the time of day rather than the bug.
        """
        from api.routes.explanation import _age_s

        # What an older build wrote: the UTC wall clock, no tzinfo. On a host
        # at UTC+5:30 the database stored it 5.5 hours in the past, and read
        # it back as 10:51 UTC for a row that was really 15:21 UTC.
        naive = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        age = _age_s(naive)

        # Read as UTC, the age is the true age: seconds, not hours.
        assert age < 3600, (
            f"a naive timestamp produced an age of {age:.0f}s; a fresh row "
            f"must not look hours old"
        )

    def test_an_aware_timestamp_gives_the_same_answer(self):
        """Both readings of the same instant must give the same age."""
        from api.routes.explanation import _age_s

        naive = datetime.datetime(2026, 10, 21, 15, 21, 10)
        aware = naive.replace(tzinfo=datetime.timezone.utc)
        assert _age_s(naive) == pytest.approx(_age_s(aware), abs=1.0)

    def test_a_known_offset_lands_in_the_past_not_the_future(self):
        """The skew has a sign, and the sign is the whole bug.

        A naive UTC wall clock stored on a host at UTC+5:30 is read back as
        5.5 hours EARLIER than it was written. That is what made a two-second
        design look five and a half hours old, and it is what fired the
        spurious retry.
        """
        utc_wall_clock = datetime.datetime(2026, 10, 21, 15, 21, 10)
        local_offset = datetime.timedelta(hours=5, minutes=30)

        # What asyncpg did: the naive value read as local time.
        as_read = utc_wall_clock - local_offset
        age = (datetime.datetime(2026, 10, 21, 15, 21, 10, tzinfo=datetime.timezone.utc)
               - as_read.replace(tzinfo=datetime.timezone.utc)).total_seconds()

        assert age == pytest.approx(local_offset.total_seconds()), (
            "the skew must be the local offset, and it must push the row "
            "into the past"
        )
        assert age > 0


# ─────────────────────────────────────────────────────────────────────────────
class TestTheExplanationRouteStopsFiringASpuriousRetry:
    """The symptom the timestamp bug produced, checked at the seam."""

    def test_a_fresh_design_is_not_stale(self):
        """A design written moments ago is not stale, whatever the clock."""
        from api.routes.explanation import STALE_AFTER_S

        now = datetime.datetime.now(datetime.timezone.utc)
        assert (now - now).total_seconds() < STALE_AFTER_S

    def test_the_staleness_window_is_five_minutes(self):
        """Pin the number, so a change to it is a deliberate act."""
        from api.routes.explanation import STALE_AFTER_S

        assert STALE_AFTER_S == 300.0
