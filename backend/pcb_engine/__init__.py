"""PCB engine — netlist JSON in, routed board + SVG out.

The modules in this package (``board_ir``, ``footprints``, ``kernel``,
``router``, ``render_pretty``, ``compile_board``) import each other by bare
name — ``from board_ir import Board`` rather than ``from .board_ir import
Board``. That was deliberate when the engine ran standalone out of its own
directory, and it keeps the CLI working:

    cd backend/pcb_engine && python compile_board.py netlist_dht22.json

Rewriting those to relative imports would break that CLI, so instead this
package puts its own directory on ``sys.path`` at import time. The engine then
resolves its siblings exactly as it does when run directly, while the backend
imports it normally:

    from pcb_engine import compile_board

Only stdlib plus numpy (``router.py``) is required — no ngspice, no KiCad.
"""

import sys
from pathlib import Path

_PKG_DIR = str(Path(__file__).resolve().parent)
if _PKG_DIR not in sys.path:
    sys.path.insert(0, _PKG_DIR)

from compile_board import compile_board, from_netlist, place_constructive  # noqa: E402

__all__ = ["compile_board", "from_netlist", "place_constructive"]
