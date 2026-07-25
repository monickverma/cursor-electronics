"""ngspice subprocess runner — always async via run_in_executor, never inline."""

import asyncio
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple

# Prefer system ngspice; fall back to MSYS2 install on Windows
def _find_ngspice() -> str:
    if shutil.which("ngspice"):
        return "ngspice"
    candidates = [
        r"C:\msys64\ucrt64\bin\ngspice_con.exe",
        r"C:\msys64\ucrt64\bin\ngspice.exe",
        r"C:\msys64\mingw64\bin\ngspice.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "ngspice"  # will fail with FileNotFoundError — clear error


_NGSPICE_CMD = _find_ngspice()


class NgspiceRunner:
    """Runs ngspice in batch mode (-b) and returns (stdout, stderr).

    Must be used via `await runner.run(netlist)` — never call _run_sync directly
    from an HTTP handler, because ngspice takes 2–30 seconds per simulation.
    """

    _TIMEOUT_SECONDS = 30

    async def run(self, netlist: str) -> dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._run_sync, netlist)

    def _run_sync(self, netlist: str) -> dict:
        # ngspice_con on Windows writes to the console handle, not stdout pipe.
        # Use -o <outfile> to capture all output to a file instead.
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".cir", delete=False, encoding="utf-8"
        ) as f:
            f.write(netlist)
            tmp_path = Path(f.name)
        out_path = tmp_path.with_suffix(".out")
        try:
            subprocess.run(
                [_NGSPICE_CMD, "-b", "-o", str(out_path), str(tmp_path)],
                capture_output=True,  # suppress any direct console writes
                timeout=self._TIMEOUT_SECONDS,
            )
            stdout = out_path.read_text(encoding="utf-8", errors="replace") if out_path.exists() else ""
            return {"stdout": stdout, "stderr": ""}
        finally:
            tmp_path.unlink(missing_ok=True)
            out_path.unlink(missing_ok=True)
