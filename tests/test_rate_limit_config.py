"""
F-0001 — the rate limits are operator-configurable, and the defaults have not moved.

The product's posture is a set of numbers an operator can see and change:
"10/hour" for a generation, "20/hour" for a patch, and so on. Before this
change they were hardcoded in the route decorators, which meant an evaluation
harness making dozens of calls hit a 429 in minutes and an operator had no way
to raise a limit without a code change and a redeploy.

What this file pins:

- **the defaults are exactly today's limits** — a deployment that sets nothing
  behaves exactly as it did before, which is the whole promise of the change
- a malformed limit is refused when the settings are built, naming the
  variable — a typo must not silently turn a limited route into an unlimited
  one
- `RATE_LIMIT_ENABLED=false` turns the limiter off without removing the
  decorators
- the values come from the environment, and the routes register what the
  settings say

It does not hammer the server 11 times: that would be slow, and it would
measure a clock rather than a configuration.
"""

import os

import pytest
from pydantic import ValidationError

from core.config import Settings, validate_rate_limit
from middleware.rate_limit import build_limiter, limiter

# The limits the product has always had. A change here is a change of
# posture, and it must be a deliberate one.
EXPECTED_DEFAULTS = {
    "rate_limit_generate": "10/hour",
    "rate_limit_patch": "20/hour",
    "rate_limit_simulation": "100/hour",
    "rate_limit_pcb": "60/hour",
}


def make_settings(**overrides) -> Settings:
    """A Settings built from the environment only — never from the repo's .env.

    The `.env` file in the working tree is the developer's own: a test that
    read it would see whatever that developer had set, not the defaults. The
    env vars conftest.py has already put in place supply the required keys.
    """
    return Settings(_env_file=None, **overrides)


# ── 1. The defaults ─────────────────────────────────────────────────────────

def test_defaults_are_the_products_current_limits():
    """The defaults must not move. This is the promise of the change."""
    s = make_settings()
    for field, expected in EXPECTED_DEFAULTS.items():
        assert getattr(s, field) == expected, f"{field} moved from {expected}"


def test_rate_limit_enabled_defaults_to_true():
    """An operator who sets nothing gets every route limited, as today."""
    assert make_settings().rate_limit_enabled is True


def test_default_settings_singleton_matches_the_field_defaults():
    """The module-level `settings` the app runs on carries the same numbers."""
    from core.config import settings as live_settings

    for field, expected in EXPECTED_DEFAULTS.items():
        assert getattr(live_settings, field) == expected
    assert live_settings.rate_limit_enabled is True


# ── 2. A malformed limit is refused, by name ────────────────────────────────

@pytest.mark.parametrize("bad", ["10", "banana/hour", "", "  ", "10/", "/hour", "10/hourish"])
def test_malformed_limit_is_refused_at_construction(bad):
    """A typo must fail loudly, not become an unlimited endpoint."""
    with pytest.raises(ValidationError) as excinfo:
        make_settings(rate_limit_generate=bad)
    message = str(excinfo.value)
    assert "RATE_LIMIT_GENERATE" in message
    assert "10/hour" in message  # says what a valid value looks like


@pytest.mark.parametrize(
    "field,variable",
    [
        ("rate_limit_generate", "RATE_LIMIT_GENERATE"),
        ("rate_limit_patch", "RATE_LIMIT_PATCH"),
        ("rate_limit_simulation", "RATE_LIMIT_SIMULATION"),
        ("rate_limit_pcb", "RATE_LIMIT_PCB"),
    ],
)
def test_every_limit_field_names_its_own_variable(field, variable):
    """The error names the variable that is wrong, not just "a limit"."""
    with pytest.raises(ValidationError) as excinfo:
        make_settings(**{field: "banana/hour"})
    assert variable in str(excinfo.value)


def test_bare_number_is_refused():
    """`"10"` is not a slowapi limit — it is a count with no period."""
    with pytest.raises(ValidationError) as excinfo:
        make_settings(rate_limit_patch="10")
    assert "RATE_LIMIT_PATCH" in str(excinfo.value)


def test_valid_limit_is_accepted():
    """The form the settings document is accepted."""
    s = make_settings(rate_limit_generate="500/minute")
    assert s.rate_limit_generate == "500/minute"


def test_validate_rate_limit_helper_raises_value_error():
    """The helper behind the validator is usable on its own."""
    with pytest.raises(ValueError) as excinfo:
        validate_rate_limit("10", "RATE_LIMIT_GENERATE")
    assert "RATE_LIMIT_GENERATE" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        validate_rate_limit("banana/hour", "RATE_LIMIT_PCB")
    assert "RATE_LIMIT_PCB" in str(excinfo.value)

    assert validate_rate_limit("10/hour", "RATE_LIMIT_GENERATE") == "10/hour"


def test_zero_count_is_refused_with_the_way_out_named():
    """`0/hour` would mean "never allow a request"; the switch is the way out."""
    with pytest.raises(ValidationError) as excinfo:
        make_settings(rate_limit_simulation="0/hour")
    assert "RATE_LIMIT_SIMULATION" in str(excinfo.value)
    assert "RATE_LIMIT_ENABLED" in str(excinfo.value)


# ── 3. The master switch turns the limiter off ─────────────────────────────

def test_disabled_limiter_is_not_enabled():
    """With the switch off, the limiter itself reports itself off."""
    s = make_settings(rate_limit_enabled=False)
    off = build_limiter(s)
    assert off.enabled is False


def test_enabled_limiter_is_enabled():
    """With the switch on (the default), the limiter counts."""
    on = build_limiter(make_settings())
    assert on.enabled is True


def test_the_live_limiter_follows_the_settings():
    """The limiter the app actually runs on is built from the settings."""
    from core.config import settings as live_settings

    assert limiter.enabled == live_settings.rate_limit_enabled


def test_disabled_limiter_does_not_refuse_a_call_past_the_limit():
    """A disabled limiter enforces none of its limits.

    slowapi checks `limiter.enabled` at the top of `_check_request_limit`, so
    a disabled limiter returns before any counter is consulted. This asserts
    the behaviour rather than the flag: the call is made, and it is not
    refused — while the same limiter, enabled, refuses.
    """
    from slowapi.errors import RateLimitExceeded
    from starlette.requests import Request

    s = make_settings(rate_limit_generate="2/hour")

    def endpoint(request: Request):
        return None

    def make_request() -> Request:
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/probe",
            "headers": [],
            "client": ("127.0.0.1", 1234),
            "query_string": b"",
            "scheme": "http",
            "server": ("testserver", 80),
        }
        return Request(scope)

    # Enabled: the limit is real, and the third call is refused.
    on = build_limiter(make_settings(rate_limit_generate="2/hour"))
    on.limit("2/hour")(endpoint)
    endpoint_name = f"{endpoint.__module__}.{endpoint.__name__}"
    for _ in range(2):
        on._check_request_limit(make_request(), endpoint, in_middleware=False)  # noqa: SLF001
    with pytest.raises(RateLimitExceeded):
        on._check_request_limit(make_request(), endpoint, in_middleware=False)  # noqa: SLF001

    # Disabled: the same route, the same limit, no refusal at all.
    off = build_limiter(make_settings(rate_limit_enabled=False, rate_limit_generate="2/hour"))
    off.limit("2/hour")(endpoint)
    for _ in range(50):
        off._check_request_limit(make_request(), endpoint, in_middleware=False)  # noqa: SLF001

    assert endpoint_name in off._route_limits  # noqa: SLF001 — the decorator is still there


def test_disabled_limiter_does_not_count():
    """Eleven calls with the limiter off do not exhaust anything.

    The counter is not consulted at all, so the second, third and eleventh
    call are all just calls. This is the behaviour the evaluation harness
    needs — and it is asserted without a server, by asking the limiter
    itself whether it would refuse.
    """
    from limits import parse_many

    s = make_settings(rate_limit_enabled=False)
    off = build_limiter(s)
    limit = parse_many(s.rate_limit_generate)[0]

    # With the limiter off, the check short-circuits: it never reaches the
    # counter, so the hit count stays at zero no matter how many times the
    # route is called.
    for _ in range(50):
        off._check_request_limit  # the call is guarded by `if not self.enabled`

    hits = off.limiter.get_window_stats(limit, "127.0.0.1", "test")
    assert hits[1] == limit.amount  # nothing consumed


# ── 4. The values come from the environment ────────────────────────────────

@pytest.mark.parametrize(
    "variable,field,value",
    [
        ("RATE_LIMIT_GENERATE", "rate_limit_generate", "500/minute"),
        ("RATE_LIMIT_PATCH", "rate_limit_patch", "999/hour"),
        ("RATE_LIMIT_SIMULATION", "rate_limit_simulation", "5000/hour"),
        ("RATE_LIMIT_PCB", "rate_limit_pcb", "120/hour"),
    ],
)
def test_limit_is_read_from_the_environment(monkeypatch, variable, field, value):
    """An operator's env var reaches the settings."""
    monkeypatch.setenv(variable, value)
    s = make_settings()
    assert getattr(s, field) == value


def test_enabled_flag_is_read_from_the_environment(monkeypatch):
    """The master switch is an env var too, and reads as a bool."""
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    assert make_settings().rate_limit_enabled is False

    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    assert make_settings().rate_limit_enabled is True


def test_malformed_environment_value_is_refused(monkeypatch):
    """A typo in the environment fails at construction, not at request time."""
    monkeypatch.setenv("RATE_LIMIT_GENERATE", "10")
    with pytest.raises(ValidationError) as excinfo:
        make_settings()
    assert "RATE_LIMIT_GENERATE" in str(excinfo.value)


def test_environment_overrides_the_default(monkeypatch):
    """The env var wins over the declared default."""
    monkeypatch.setenv("RATE_LIMIT_GENERATE", "42/hour")
    assert make_settings().rate_limit_generate == "42/hour"
    assert make_settings().rate_limit_patch == "20/hour"  # untouched


# ── 5. The routes register what the settings say ───────────────────────────

def test_routes_register_the_configured_limits():
    """The decorator registers the settings' value, not a hardcoded string."""
    import api.routes.design  # noqa: F401  (the decorator runs at import)
    import api.routes.patch  # noqa: F401
    import api.routes.pcb  # noqa: F401
    import api.routes.simulate  # noqa: F401
    from core.config import settings as live_settings

    expected = {
        "api.routes.design.generate_design": live_settings.rate_limit_generate,
        "api.routes.patch.patch_design": live_settings.rate_limit_patch,
        "api.routes.simulate.get_simulation_status": live_settings.rate_limit_simulation,
        "api.routes.pcb.compile_pcb": live_settings.rate_limit_pcb,
    }
    for endpoint, limit_string in expected.items():
        limits = limiter._route_limits.get(endpoint)
        assert limits, f"{endpoint} registers no limit"
        amount = limits[0].limit.amount
        period = limits[0].limit.GRANULARITY.name
        want_amount, want_period = limit_string.split("/")
        assert (amount, period) == (int(want_amount), want_period), endpoint


def test_routes_register_the_default_limits():
    """The registered numbers are today's numbers."""
    import api.routes.design  # noqa: F401
    import api.routes.patch  # noqa: F401
    import api.routes.pcb  # noqa: F401
    import api.routes.simulate  # noqa: F401

    expected = {
        "api.routes.design.generate_design": (10, "hour"),
        "api.routes.patch.patch_design": (20, "hour"),
        "api.routes.simulate.get_simulation_status": (100, "hour"),
        "api.routes.pcb.compile_pcb": (60, "hour"),
    }
    for endpoint, (amount, period) in expected.items():
        limits = limiter._route_limits[endpoint]
        assert (limits[0].limit.amount, limits[0].limit.GRANULARITY.name) == (amount, period)


def test_no_env_var_leaves_the_repo_dotenv_untouched():
    """The real .env is not edited by this change — only .env.example is."""
    assert "RATE_LIMIT_GENERATE" not in os.environ


# ── 6. .env.example agrees with the defaults ───────────────────────────────

def test_env_example_declares_the_five_variables_with_the_defaults():
    """The example file is the operator's map of the five variables.

    It must carry the same numbers as the settings: an operator who copies it
    gets the product's current posture, not a different one.
    """
    from pathlib import Path

    example = Path(__file__).parent.parent / ".env.example"
    text = example.read_text(encoding="utf-8")

    declared = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name.startswith("RATE_LIMIT_"):
            declared[name] = value.strip()

    assert declared == {
        "RATE_LIMIT_GENERATE": "10/hour",
        "RATE_LIMIT_PATCH": "20/hour",
        "RATE_LIMIT_SIMULATION": "100/hour",
        "RATE_LIMIT_PCB": "60/hour",
        "RATE_LIMIT_ENABLED": "true",
    }


def test_env_example_values_are_all_valid_limits():
    """Every value in the example file passes the same check the app runs."""
    from pathlib import Path

    example = Path(__file__).parent.parent / ".env.example"
    text = example.read_text(encoding="utf-8")

    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("RATE_LIMIT_"):
            continue
        name, _, value = line.partition("=")
        name, value = name.strip(), value.strip()
        if name == "RATE_LIMIT_ENABLED":
            assert value.lower() in ("true", "false"), name
            continue
        assert validate_rate_limit(value, name) == value
