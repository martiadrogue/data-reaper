"""The Celery app: broker, the import queue, and the Beat schedule."""

from celery import Celery
from celery.schedules import crontab
from celery.signals import beat_init, worker_process_init, worker_process_shutdown
from celery.signals import setup_logging as celery_setup_logging
from kombu import Exchange, Queue

from data_reaper.core.config import get_settings
from data_reaper.core.logging import setup_logging
from data_reaper.core.telemetry import setup_telemetry, shutdown_telemetry
from data_reaper.domain.model.constants import IMPORT_QUEUE

app = Celery(
    "data_reaper",
    broker=get_settings().broker_url,
    include=["data_reaper.presentation.worker.tasks"],
)

app.conf.update(
    timezone="UTC",
    task_track_started=True,
    # An import is acknowledged only once it finishes, so a worker crash
    # hands it to another worker; `process_import` skips one that
    # already started, and `retry` resumes it.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Task events feed `celery-exporter`'s Prometheus metrics
    # (docs/ARCHITECTURE.md#observability).
    worker_send_task_events=True,
    task_send_sent_event=True,
    task_queues=(
        Queue(IMPORT_QUEUE, Exchange(IMPORT_QUEUE), routing_key=IMPORT_QUEUE),
    ),
    task_default_queue=IMPORT_QUEUE,
    beat_schedule={
        "discover-dataset-files": {
            "task": "data_reaper.tasks.discover_dataset_files",
            "schedule": crontab(minute="*"),
        },
    },
)


@celery_setup_logging.connect
def configure_logging(**_: object) -> None:
    """Log as the API does: JSON lines on stdout.

    A receiver on this signal stops Celery from configuring logging
    itself, so the worker's and Beat's `--loglevel` are ignored.
    """
    setup_logging()


@worker_process_init.connect
def start_worker_telemetry(**_: object) -> None:
    """Set up telemetry in each worker process, after the fork.

    The exporters' background threads don't survive a fork, so the
    parent process never sets them up.
    """
    setup_telemetry("data-reaper-worker")


@worker_process_shutdown.connect
def stop_worker_telemetry(**_: object) -> None:
    """Flush the worker process's last spans and metrics."""
    shutdown_telemetry()


@beat_init.connect
def start_beat_telemetry(**_: object) -> None:
    """Set up telemetry in Celery Beat, which sends scheduled tasks."""
    setup_telemetry("data-reaper-beat")
