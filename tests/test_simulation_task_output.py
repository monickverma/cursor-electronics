"""The simulation task hands the route the whole ngspice output, because the route grades from it."""
import asyncio

from simulation.runner import NgspiceRunner
from tasks.simulation_task import run_simulation


def test_the_task_does_not_cut_the_output_the_route_grades_from(monkeypatch):
    long_output = "v(in) 5.0\n" * 5000  # 50 kB, well past the old 4000-character cut

    async def fake_run(self, netlist):
        return {"stdout": long_output, "stderr": ""}

    monkeypatch.setattr(NgspiceRunner, "run", fake_run)
    monkeypatch.setattr(run_simulation, "update_state", lambda *a, **k: None)  # no Redis in the unit test
    out = run_simulation.apply(args=["cid", "* netlist", "job"]).get()
    assert out["status"] == "complete"
    assert out["stdout"] == long_output
