"""Parse ngspice -b (batch) output into structured SimulationData.

ngspice batch output format (from CLAUDE.md Rule 4):
  - DC op (.op): columnar Node/Voltage table — v(nodename)  3.30000e+00
  - AC sweep (.print ac): tabular with frequency and magnitude columns
  - NOT the v(x) = y format used by some other SPICE variants.
"""

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# Matches DC op table lines: "v(nodename)   3.30000e+00"
_DC_NODE_PATTERN = re.compile(
    r'^\s*v\(([^)]+)\)\s+([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)',
    re.IGNORECASE,
)

# Matches ngspice columnar Node/Voltage table: "  nodename   5.00000e+00"
# Node names contain word chars and underscores but NOT '#' (that's branch current)
_DC_COLUMNAR_PATTERN = re.compile(
    r'^\s+([\w][\w_]*)\s{2,}([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*$',
)

# Matches column header tokens like "v(out)", "v(vcc_5v)"
_V_COL_PATTERN = re.compile(r'^v\(([^)]+)\)$', re.IGNORECASE)


@dataclass
class SimulationData:
    dc_voltages: Dict[str, float] = field(default_factory=dict)
    ac_points: List[Tuple[float, Dict[str, float]]] = field(default_factory=list)
    raw_stdout: str = ""
    raw_stderr: str = ""


class SpiceResultParser:
    """Parses ngspice -b output. Node names are lowercased in all returned dicts."""

    def parse(self, stdout: str, stderr: str) -> SimulationData:
        data = SimulationData(raw_stdout=stdout, raw_stderr=stderr)

        # AC sweep: look for the frequency table first
        if re.search(r'\bfrequency\b', stdout, re.IGNORECASE):
            data.ac_points = self._parse_ac_table(stdout)

        # DC: scan every line for the "v(node)  value" columnar pattern
        _SKIP_WORDS = {"node", "voltage", "source", "current", "model", "device", "resistor"}
        in_node_table = False
        for line in stdout.splitlines():
            # v(nodename)  value  — from .print directive output
            m = _DC_NODE_PATTERN.match(line)
            if m:
                data.dc_voltages[m.group(1).lower()] = float(m.group(2))
                continue
            # Detect entry into Node/Voltage columnar table
            if re.search(r'\bNode\b.*\bVoltage\b', line, re.IGNORECASE):
                in_node_table = True
                continue
            if in_node_table:
                stripped = line.strip()
                if not stripped or stripped.startswith("-"):
                    continue
                # Exit table when we hit a blank section or non-data header
                if re.match(r'^[A-Za-z]', stripped) and not re.match(r'^[A-Za-z][\w_]*\s+[+-]?\d', stripped):
                    in_node_table = False
                    continue
                m2 = _DC_COLUMNAR_PATTERN.match(line)
                if m2:
                    node = m2.group(1).lower()
                    if node not in _SKIP_WORDS and "#" not in node:
                        data.dc_voltages[node] = float(m2.group(2))

        # DC fallback: tabular format from .print dc (Index v(node1) v(node2) ...)
        if not data.dc_voltages and not data.ac_points:
            data.dc_voltages = self._parse_dc_table(stdout)

        return data

    # ── DC tabular fallback ───────────────────────────────────────────────────

    def _parse_dc_table(self, stdout: str) -> Dict[str, float]:
        """Parse '.print dc' tabular output: header with v(node) columns + data row."""
        lines = stdout.splitlines()
        voltages: Dict[str, float] = {}

        for i, line in enumerate(lines):
            parts = line.split()
            cols: List[Tuple[int, str]] = []
            for j, p in enumerate(parts):
                m = _V_COL_PATTERN.match(p)
                if m:
                    cols.append((j, m.group(1).lower()))
            if not cols:
                continue
            # Parse the first non-separator data row after the header
            for data_line in lines[i + 1:]:
                data_parts = data_line.split()
                if not data_parts or data_parts[0].startswith("-"):
                    continue
                try:
                    nums = [float(x) for x in data_parts]
                except ValueError:
                    continue
                for col_idx, node in cols:
                    if col_idx < len(nums):
                        voltages[node] = nums[col_idx]
                break

        return voltages

    # ── AC sweep table ────────────────────────────────────────────────────────

    def _parse_ac_table(self, stdout: str) -> List[Tuple[float, Dict[str, float]]]:
        """Parse ngspice AC output.

        ngspice emits one table per variable even when multiple nodes appear on
        the same .print line, and paginates each table.  Strategy:
        1. Find every 'Index  frequency  v(node)' header.
        2. Parse each table section independently, collecting {freq_idx: value}.
        3. Build a shared freq_idx→frequency map from the first table.
        4. Merge all tables into List[(freq, {node: value})].
        """
        lines = stdout.splitlines()

        # Collect all table sections: (node_name, {freq_idx: value})
        node_data: Dict[str, Dict[int, float]] = {}
        freq_map: Dict[int, float] = {}  # freq_idx → frequency

        i = 0
        while i < len(lines):
            line = lines[i]
            if not re.search(r'\bfrequency\b', line, re.IGNORECASE):
                i += 1
                continue

            # Parse header: "Index  frequency  v(nodename)"
            parts = line.split()
            lower_parts = [p.lower() for p in parts]
            if "frequency" not in lower_parts:
                i += 1
                continue

            node_name: Optional[str] = None
            for token in lower_parts:
                m = _V_COL_PATTERN.match(token)
                if m:
                    node_name = m.group(1).lower()
                    break

            if node_name is None:
                i += 1
                continue

            if node_name not in node_data:
                node_data[node_name] = {}

            # Skip separator line
            i += 1
            if i < len(lines) and lines[i].startswith("---"):
                i += 1

            # Parse data rows: Index\tfrequency\treal,\timag\t
            while i < len(lines):
                row = lines[i]
                stripped = row.strip()
                if not stripped:
                    i += 1
                    break
                if stripped.startswith("-") or stripped.startswith("="):
                    i += 1
                    continue
                # Check if it's a new header (re-pagination)
                if re.search(r'\bfrequency\b', stripped, re.IGNORECASE):
                    break  # will be picked up in outer loop
                # Strip commas from complex format: "1.23e+00,"
                cleaned = stripped.replace(",", " ")
                try:
                    nums = [float(x) for x in cleaned.split()]
                except ValueError:
                    i += 1
                    continue
                if len(nums) < 3:
                    i += 1
                    continue
                idx = int(nums[0])
                freq = nums[1]
                # Complex format: real  imag — compute true magnitude
                real_part = nums[2]
                imag_part = nums[3] if len(nums) > 3 else 0.0
                value = math.sqrt(real_part ** 2 + imag_part ** 2)
                freq_map[idx] = freq
                node_data[node_name][idx] = value
                i += 1
            # continue outer loop at current i (might be new header)

        if not node_data or not freq_map:
            return []

        # Merge into sorted list of (freq, {node: value})
        result: List[Tuple[float, Dict[str, float]]] = []
        for idx in sorted(freq_map):
            freq = freq_map[idx]
            values = {node: vals[idx] for node, vals in node_data.items() if idx in vals}
            if values:
                result.append((freq, values))

        return result
