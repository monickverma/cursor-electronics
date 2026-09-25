"""
Live distributor pricing — Mouser, optional. `brain/decisions.md` [2026-09-25].

Only `GET /design/{id}/bom` reads it. Nothing under `validation/`, `proof/` or
the generators imports this package: a price never gates a claim.
"""
