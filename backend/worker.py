from celery import Celery

from core.config import settings

app = Celery(
    "circuit_os",
    broker=settings.broker_url,
    backend=settings.redis_url,
    include=[
        "tasks.simulation_task",
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
