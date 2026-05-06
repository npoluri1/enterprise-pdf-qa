"""Celery application factory."""
from celery import Celery
from app.config import settings

celery_app = Celery(
    "pdf_qa",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.workers.tasks.ingest_document": {"queue": "ingestion"},
        "app.workers.tasks.batch_embed": {"queue": "ingestion"},
    },
    beat_schedule={
        "cleanup-failed-documents": {
            "task": "app.workers.tasks.cleanup_failed_documents",
            "schedule": 3600.0,  # every hour
        },
    },
)
