"""
Idempotent schema migrations, applied at startup.

`db/schema.sql` is mounted into Postgres' `docker-entrypoint-initdb.d`, which
runs only against an **empty** data directory. So every column added after a
volume was created is missing on that volume, and an INSERT naming it fails —
the constraint that kept the X5 evidence out of a proper column
(`brain/decisions.md` [2026-09-21], the X5 defects entry). Stage 2 needs two
new columns, and every later stage will need more, so the repo gets the
smallest thing that removes the problem: statements that are safe to run on
every start, whatever state the volume is in.

Rules for adding one:
- It must be idempotent (`IF NOT EXISTS`), because it runs on every start.
- It must be additive. A rename or a drop is a data decision and does not
  belong in a list that runs unattended.
- The same column goes into `schema.sql`, so a fresh volume and a migrated one
  end up identical.

A migration that fails is logged and the app starts anyway, which is what
happens today when Postgres is unreachable at boot; requests that need the
database then fail as they would have.
"""

from __future__ import annotations

import logging
from typing import Sequence

logger = logging.getLogger(__name__)

#: In application order. Append only.
MIGRATIONS: Sequence[str] = (
    # Stage 2 — X2: the IntentIR and annotations live on the design record.
    "ALTER TABLE circuit_designs ADD COLUMN IF NOT EXISTS intent_ir JSONB",
    "ALTER TABLE circuit_designs ADD COLUMN IF NOT EXISTS annotations JSONB",
    # Stage 5 — the compile gate's cache: one row per firmware project hash.
    "CREATE TABLE IF NOT EXISTS firmware_builds ("
    " build_hash VARCHAR(64) PRIMARY KEY, target VARCHAR(50) NOT NULL,"
    " status VARCHAR(20) NOT NULL, log TEXT, seconds DOUBLE PRECISION,"
    " created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), finished_at TIMESTAMPTZ)",
    # [2026-09-25] — live distributor quotes, one row per source and part number.
    "CREATE TABLE IF NOT EXISTS price_quotes ("
    " source VARCHAR(20) NOT NULL, part_number VARCHAR(100) NOT NULL,"
    " found BOOLEAN NOT NULL, fetched_at TIMESTAMPTZ NOT NULL, quote JSONB NOT NULL,"
    " PRIMARY KEY (source, part_number))",
    # [2026-10-21, F-0006] — the explanation's attempt ledger: what was queued
    # for a design version, and when. Caps the attempts and carries the task id
    # of the newest one, so a retry never replaces the attempt in flight.
    "CREATE TABLE IF NOT EXISTS explanation_attempts ("
    " id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
    " circuit_id VARCHAR(36) NOT NULL REFERENCES circuit_designs(circuit_id) ON DELETE CASCADE,"
    " version INTEGER NOT NULL DEFAULT 1,"
    " attempts INTEGER NOT NULL DEFAULT 0,"
    " task_id VARCHAR(255),"
    " queued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),"
    " updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_explanation_attempts_design_version"
    " ON explanation_attempts(circuit_id, version)",
)


def is_safe(statement: str) -> bool:
    """Additive and idempotent — the two properties a startup migration needs."""
    s = " ".join(statement.upper().split())
    # CREATE [UNIQUE] INDEX is additive: it constrains nothing that exists and
    # it names rows it is meant to make unique. The uniqueness is the point of
    # the index — a plain CREATE INDEX would not stop a second row for the same
    # design version, and the ledger would then hold two attempts for one
    # design with no way to say which is the truth.
    additive = ((s.startswith("ALTER TABLE") and " ADD COLUMN " in s)
                or s.startswith("CREATE INDEX")
                or s.startswith("CREATE UNIQUE INDEX")
                or s.startswith("CREATE TABLE IF NOT EXISTS"))
    return additive and "IF NOT EXISTS" in s and " DROP " not in s and " RENAME " not in s


async def apply_migrations(engine) -> bool:
    """Run every migration. True if all applied; never raises."""
    from sqlalchemy import text

    try:
        async with engine.begin() as conn:
            for statement in MIGRATIONS:
                await conn.execute(text(statement))
        return True
    except Exception as exc:  # noqa: BLE001 — startup must not die on this
        logger.error("schema migrations not applied: %s", exc)
        return False
