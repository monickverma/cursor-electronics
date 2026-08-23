"""ngspice subprocess runner — always async via run_in_executor, never inline."""

import asyncio
import os
import shutil
import subprocess
import tempfile
import time
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

    # The process exiting does not mean its output file is readable yet. On
    # Windows an on-access AV scan can hold a freshly written file open for a
    # few tens of milliseconds, so a read immediately after `subprocess.run`
    # returns can see the file missing, empty, or half-written. That surfaces as
    # a simulation that produced no data, with nothing to say why.
    _READ_ATTEMPTS = 6
    _READ_DELAY_S = 0.05

    def _read_settled(self, path: Path) -> str:
        """Read `path` once its size has stopped changing.

        Returns "" only if the file genuinely never appeared — not because we
        looked too early.
        """
        last_size = -1
        for _ in range(self._READ_ATTEMPTS):
            if path.exists():
                size = path.stat().st_size
                if size > 0 and size == last_size:
                    try:
                        return path.read_text(encoding="utf-8", errors="replace")
                    except PermissionError:
                        pass          # still locked; fall through and retry
                last_size = size
            time.sleep(self._READ_DELAY_S)
        if path.exists():
            try:
                return path.read_text(encoding="utf-8", errors="replace")
            except PermissionError:
                return ""
        return ""

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
            try:
                proc = subprocess.run(
                    [_NGSPICE_CMD, "-b", "-o", str(out_path), str(tmp_path)],
                    capture_output=True,  # suppress any direct console writes
                    timeout=self._TIMEOUT_SECONDS,
                )
                rc = proc.returncode
                # ngspice's own console output was being captured and discarded,
                # so a failed run produced an empty result and no explanation.
                err = (proc.stderr or b"").decode("utf-8", "replace")
            except subprocess.TimeoutExpired:
                rc, err = -1, (
                    f"ngspice exceeded {self._TIMEOUT_SECONDS}s and was killed"
                )
            stdout = self._read_settled(out_path)
            return {"stdout": stdout, "stderr": err, "returncode": rc}
        finally:
            # Cleanup must never fail a simulation that already succeeded — on
            # Windows an unlink can raise PermissionError on a file still held
            # by a scanner.
            for pth in (tmp_path, out_path):
                try:
                    pth.unlink(missing_ok=True)
                except OSError:
                    pass
