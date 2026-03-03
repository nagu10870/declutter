"""
Celery Task Queue — Month 4

Replaces FastAPI BackgroundTasks for long-running jobs that need:
  - Retry on failure
  - Progress tracking via Redis
  - Scheduled/periodic execution
  - Proper error handling and alerting

Tasks defined here:
  - classify_user_files     → Heuristic + optional GPT-4o classification
  - generate_clip_embeddings → CLIP semantic embedding generation
  - generate_suggestions_task → Run rules engine after classification
  - send_scan_complete_email → Email digest after scan completes
  - weekly_scan_job          → Scheduled: re-index all connections
  - monthly_report_email     → Scheduled: monthly storage report

Usage from FastAPI:
    from app.services.workers.celery_app import classify_user_files
    classify_user_files.delay(user_id, limit=500)
"""

import os
from celery import Celery
from celery.schedules import crontab

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "declutter",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.services.workers.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # One task at a time (prevents RAM overuse)
    result_expires=3600,           # Keep task results for 1 hour

    # Retry policy
    task_autoretry_for=(Exception,),
    task_max_retries=3,
    task_retry_backoff=True,
    task_retry_backoff_max=300,

    # Rate limits
    task_default_rate_limit="100/m",

    # Beat scheduler (periodic tasks)
    beat_schedule={
        "weekly-scan-all-users": {
            "task": "app.services.workers.tasks.weekly_scan_all",
            "schedule": crontab(hour=2, minute=0, day_of_week=1),  # Monday 2am UTC
        },
        "monthly-report-emails": {
            "task": "app.services.workers.tasks.send_monthly_reports",
            "schedule": crontab(hour=9, minute=0, day_of_month=1),  # 1st of month, 9am
        },
        "cleanup-expired-data": {
            "task": "app.services.workers.tasks.cleanup_expired_data",
            "schedule": crontab(hour=3, minute=0),  # Daily at 3am
        },
    },
)
