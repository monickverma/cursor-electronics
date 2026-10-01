"""
The Mouser key never reaches Sentry ([2026-10-01] #1).

Mouser takes the key in the query string, and Sentry's httpx integration
records the query on every outgoing span and breadcrumb. `main.sentry_options`
turns that integration off and scrubs every event, transaction and breadcrumb.
This runs Sentry, configured exactly as the app configures it, in a child
process with a transport that captures what would be sent — so the global
Sentry client never touches the rest of the suite.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCRIPT = textwrap.dedent('''
    import asyncio, os, sys
    os.environ.update(SENTRY_DSN="https://pub@o0.ingest.sentry.io/0", MOUSER_API_KEY="")
    sys.path.insert(0, "backend")
    from datetime import datetime, timezone
    import httpx, sentry_sdk
    from sentry_sdk.transport import Transport

    captured = []

    class Capture(Transport):
        def capture_envelope(self, envelope):
            for item in envelope.items:
                captured.append(item.payload.get_bytes().decode("utf-8", "replace"))

    import main
    from pricing import mouser

    options = main.sentry_options()
    options.update(transport=Capture, traces_sample_rate=float(sys.argv[1]))
    sentry_sdk.init(**options)
    KEY = "SECRETKEY-1234-abcd"

    def answer(request):
        sentry_sdk.add_breadcrumb(category="http", data={"url": str(request.url)})
        return httpx.Response(200, json={"Errors": [], "SearchResults": {"Parts": []}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as client:
            with sentry_sdk.start_transaction(name="GET /design/x/bom"):
                await mouser.fetch(["CL05B104KO5NNNC"], KEY, client, datetime.now(timezone.utc))
                sentry_sdk.capture_message("a later error in the same request")

    asyncio.run(run())
    sentry_sdk.flush()
    assert captured, "nothing was captured: the test would prove nothing"
    leaked = [p for p in captured if KEY in p]
    print(len(captured), len(leaked))
    sys.exit(1 if leaked else 0)
''')


def _run(rate: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, "-c", SCRIPT, rate], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=120)


def test_a_sampled_request_sends_sentry_no_key():
    out = _run("1.0")
    assert out.returncode == 0, out.stdout + out.stderr


def test_an_unsampled_request_sends_sentry_no_key():
    out = _run("0.0")
    assert out.returncode == 0, out.stdout + out.stderr
