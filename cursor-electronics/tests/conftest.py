"""
Pytest fixtures. All 5 example IRs available in every test module.
"""

import os
import sys
from pathlib import Path

# Set dummy env vars BEFORE any backend imports so pydantic-settings doesn't
# fail at import time.  Real values override these in CI via environment.
# Empty string for the API key → API_KEY_PRESENT=False → live tests skipped.
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")

# Ensure backend is importable when running tests from repo root
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import pytest

from core.ir_examples import IR_001, IR_002, IR_003, IR_004, IR_005, ALL_EXAMPLES
from core.ir_schema import CircuitIR


@pytest.fixture
def ir_dht22():
    """Arduino Uno + DHT22 temperature/humidity sensor."""
    return IR_001


@pytest.fixture
def ir_led():
    """Arduino Uno + LED with current limiting resistor."""
    return IR_002


@pytest.fixture
def ir_rc_filter():
    """RC low-pass filter, 1kHz cutoff."""
    return IR_003


@pytest.fixture
def ir_voltage_divider():
    """Voltage divider 12V → 5V."""
    return IR_004


@pytest.fixture
def ir_modbus():
    """Arduino Uno + MAX485 RS-485 Modbus RTU master."""
    return IR_005


@pytest.fixture(params=["ir_001", "ir_002", "ir_003", "ir_004", "ir_005"])
def all_example_irs(request):
    """Parameterized fixture — runs test once per example IR."""
    return {
        "ir_001": IR_001,
        "ir_002": IR_002,
        "ir_003": IR_003,
        "ir_004": IR_004,
        "ir_005": IR_005,
    }[request.param]
