import os

from .base import env_bool


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Celery: these settings point workers at Redis and keep the recurring
# ingestion job on its 6-hour beat schedule.
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 270
CELERY_BEAT_SCHEDULE = {
    "run-all-source-ingestions-every-6-hours": {
        "task": "core.tasks.run_all_ingestions",
        "schedule": 60 * 60 * 6,
    },
}
