from celery import Celery
from kombu import Queue

celery_app = Celery('jobflow', broker="redis://localhost:6379/0", backend="redis://localhost:6379/1")

celery_app.conf.update(
    task_default_queue = "default",
    task_queues = (
        Queue("high_priority"),
        Queue("default", ),
        Queue("low_priority")
    ),
    task_serializer = "json",
    result_serializer = "json",
    accept_content = ["json"],
    beat_schedule = {
        "cleanup-stale-jobs-every-hour":{
            "task": "tasks.cleanup_stale_jobs",
            "schedule": 60 * 60
        }
    }
)

celery_app.autodiscover_tasks(["tasks"])