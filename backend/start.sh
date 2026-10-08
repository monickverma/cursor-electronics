#!/bin/sh
# One container, two processes: Railway puts a service with no web traffic to sleep
# on the free plan, so a separate Celery worker never wakes to take a queued
# simulation. Running the worker beside the API keeps it awake with the API.
celery -A worker.app worker --loglevel=info --concurrency=1 &
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
