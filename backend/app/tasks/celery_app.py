from celery import Celery
from celery.schedules import crontab
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "monad_mate",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.tasks.escrow_tasks",
        "app.tasks.match_tasks",
        "app.tasks.reputation_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    "auto-slash-expired-escrows": {
        "task": "app.tasks.escrow_tasks.auto_slash_expired_escrows",
        "schedule": crontab(minute=0),  # every hour
    },
    "expire-stale-matches": {
        "task": "app.tasks.match_tasks.expire_stale_matches",
        "schedule": crontab(minute=0),  # every hour
    },
    "apply-reputation-decay": {
        "task": "app.tasks.reputation_tasks.apply_reputation_decay",
        "schedule": crontab(hour=2, minute=0),  # daily at 02:00 UTC
    },
}
