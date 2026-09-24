"""Celery task for running ngspice simulations in background workers."""

from __future__ import annotations

import asyncio
import time

from worker import app as celery_app


@celery_app.task(bind=True, name="tasks.simulation_task.run_simulation")
def run_simulation(self, circuit_id: str, netlist: str, job_id: str, circuit_type: str = "unknown") -> dict:
    """
    Run ngspice on the given netlist. Returns a results dict stored in Celery backend.
    Records outcome to sim_monitor.jsonl for the Phase 1 launch gate check.
    """
    from simulation.runner import NgspiceRunner
    from simulation.parser import SpiceResultParser
    from simulation.monitor import record_simulation
    from simulation.waveforms import waveforms_from

    start_ms = int(time.time() * 1000)
    self.update_state(state="STARTED")

    netlist_lines = len(netlist.splitlines())

    try:
        runner = NgspiceRunner()
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(runner.run(netlist))
        finally:
            loop.close()

        parser = SpiceResultParser()
        parsed = parser.parse(result["stdout"], result["stderr"])

        duration_ms = int(time.time() * 1000) - start_ms

        record_simulation(
            circuit_id=circuit_id,
            circuit_type=circuit_type,
            success=True,
            duration_ms=duration_ms,
            netlist_line_count=netlist_lines,
            dc_node_count=len(parsed.dc_voltages),
            ac_point_count=len(parsed.ac_points),
        )

        return {
            "status": "complete",
            "circuit_id": circuit_id,
            "job_id": job_id,
            "duration_ms": duration_ms,
            "dc_voltages": parsed.dc_voltages,
            "ac_points_count": len(parsed.ac_points),
            # Stage 3: the points themselves, downsampled, for the viewer.
            "waveforms": waveforms_from(parsed),
            "stdout": result["stdout"][:4000],
            "stderr": result["stderr"][:2000],
        }

    except Exception as exc:
        duration_ms = int(time.time() * 1000) - start_ms
        record_simulation(
            circuit_id=circuit_id,
            circuit_type=circuit_type,
            success=False,
            duration_ms=duration_ms,
            netlist_line_count=netlist_lines,
            error=str(exc),
        )
        return {
            "status": "failed",
            "circuit_id": circuit_id,
            "job_id": job_id,
            "duration_ms": duration_ms,
            "error": str(exc),
        }
