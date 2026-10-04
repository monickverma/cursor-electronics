import sys
from pathlib import Path

# Celery puts the working directory on sys.path only while it loads the app
# (`-A worker.app`); a task that imports `generators` when it *runs* then fails
# with ModuleNotFoundError — which is every firmware build ([2026-10-04], found
# on the first real worker run of the compile gate). The worker's own folder
# stays on the path for as long as the worker lives.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from celery import Celery  # noqa: E402

from core.config import settings  # noqa: E402

app = Celery(
    "circuit_os",
    broker=settings.broker_url,
    backend=settings.redis_url,
    include=[
        "tasks.simulation_task",
        "tasks.firmware_task",   # Stage 5: the compile gate
        "tasks.explain_task",    # [2026-10-05]: the explanation, off the request
    ],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    result_expires=3600,  # results expire after 1 hour
    worker_prefetch_multiplier=1,  # simulation is CPU-heavy — one task at a time per worker
)

if __name__ == "__main__":
    app.start()
