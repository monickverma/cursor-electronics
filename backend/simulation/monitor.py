"""
Structured simulation failure logger.

Every simulation run is logged to a JSON Lines file (one JSON object per line).
Use aggregate() to compute per-circuit-type success rates — the gate for Phase 1
launch is ≥90% success across all 5 circuit types.

Log location: backend/simulation/sim_monitor.jsonl
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

_LOG_PATH = Path(__file__).parent / "sim_monitor.jsonl"


@dataclass
class SimRunLog:
    circuit_id: str
    circuit_type: str          # rc_filter | dht_sensor | modbus | led | voltage_divider
    success: bool
    duration_ms: int
    netlist_line_count: int
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    error: Optional[str] = None
    dc_node_count: int = 0
    ac_point_count: int = 0


@dataclass
class CircuitTypeStats:
    circuit_type: str
    total_runs: int
    successes: int
    failures: int
    success_rate: float
    avg_duration_ms: float
    last_error: Optional[str]


class SimulationMonitor:
    def __init__(self, log_path: Path = _LOG_PATH):
        self._log_path = log_path

    def record(
        self,
        circuit_id: str,
        circuit_type: str,
        success: bool,
        duration_ms: int,
        netlist_line_count: int = 0,
        error: Optional[str] = None,
        dc_node_count: int = 0,
        ac_point_count: int = 0,
    ) -> None:
        entry = SimRunLog(
            circuit_id=circuit_id,
            circuit_type=circuit_type,
            success=success,
            duration_ms=duration_ms,
            netlist_line_count=netlist_line_count,
            error=error,
            dc_node_count=dc_node_count,
            ac_point_count=ac_point_count,
        )
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry)) + "\n")

    def aggregate(self, last_n: Optional[int] = None) -> List[CircuitTypeStats]:
        """Return per-circuit-type success rates from the log file."""
        if not self._log_path.exists():
            return []

        entries: List[dict] = []
        with open(self._log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        if last_n:
            entries = entries[-last_n:]

        by_type: Dict[str, List[dict]] = defaultdict(list)
        for e in entries:
            by_type[e.get("circuit_type", "unknown")].append(e)

        stats = []
        for ctype, runs in by_type.items():
            total = len(runs)
            successes = sum(1 for r in runs if r.get("success"))
            failures = total - successes
            durations = [r.get("duration_ms", 0) for r in runs]
            avg_dur = sum(durations) / len(durations) if durations else 0
            last_err = next(
                (r.get("error") for r in reversed(runs) if not r.get("success") and r.get("error")),
                None,
            )
            stats.append(CircuitTypeStats(
                circuit_type=ctype,
                total_runs=total,
                successes=successes,
                failures=failures,
                success_rate=round(successes / total, 4) if total else 0.0,
                avg_duration_ms=round(avg_dur, 1),
                last_error=last_err,
            ))

        return sorted(stats, key=lambda s: s.circuit_type)

    def check_launch_gate(self, min_rate: float = 0.90, min_runs: int = 5) -> dict:
        """
        Phase 1 launch gate: every circuit type must have ≥90% success rate
        over at least 5 runs. Returns a dict with passed: bool and details.
        """
        stats = self.aggregate()
        failures = []
        for s in stats:
            if s.total_runs < min_runs:
                failures.append(f"{s.circuit_type}: only {s.total_runs} runs (need {min_runs})")
            elif s.success_rate < min_rate:
                failures.append(
                    f"{s.circuit_type}: {s.success_rate:.0%} success rate "
                    f"({s.successes}/{s.total_runs}) — below {min_rate:.0%} gate"
                )
        return {
            "passed": len(failures) == 0,
            "failures": failures,
            "stats": [asdict(s) for s in stats],
        }


_monitor = SimulationMonitor()


def record_simulation(
    circuit_id: str,
    circuit_type: str,
    success: bool,
    duration_ms: int,
    netlist_line_count: int = 0,
    error: Optional[str] = None,
    dc_node_count: int = 0,
    ac_point_count: int = 0,
) -> None:
    """Module-level convenience wrapper."""
    _monitor.record(
        circuit_id=circuit_id,
        circuit_type=circuit_type,
        success=success,
        duration_ms=duration_ms,
        netlist_line_count=netlist_line_count,
        error=error,
        dc_node_count=dc_node_count,
        ac_point_count=ac_point_count,
    )
