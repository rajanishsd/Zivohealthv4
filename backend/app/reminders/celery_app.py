from celery import Celery
from kombu import Exchange, Queue
from .config import settings


broker_url = settings.CELERY_BROKER_URL or settings.RABBITMQ_URL
result_backend = settings.CELERY_RESULT_BACKEND or None

celery_app = Celery(
    "reminders",
    broker=broker_url,
    backend=result_backend,
)

exchange = Exchange(settings.RABBITMQ_EXCHANGE, type="direct", durable=True)

celery_app.conf.update(
    task_acks_late=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    worker_prefetch_multiplier=1,
    # Custom worker pool for PID tracking
    worker_pool="app.reminders.worker_pool:PidTrackingTaskPool",
    # Limit concurrency to prevent too many workers
    worker_concurrency=settings.WORKER_CONCURRENCY,
    task_default_queue=settings.RABBITMQ_INPUT_QUEUE,
    task_default_exchange=settings.RABBITMQ_EXCHANGE,
    task_default_routing_key=settings.RABBITMQ_INPUT_ROUTING_KEY,
    include=["app.reminders.tasks", "app.reminders.recurring_tasks"],
    task_queues=(
        Queue(settings.RABBITMQ_INPUT_QUEUE, exchange=exchange, routing_key=settings.RABBITMQ_INPUT_ROUTING_KEY, durable=True),
        Queue(settings.RABBITMQ_OUTPUT_QUEUE, exchange=exchange, routing_key=settings.RABBITMQ_OUTPUT_ROUTING_KEY, durable=True),
    ),
)

# Celery Beat schedule for periodic scanning
celery_app.conf.beat_schedule = {
    "scan-and-dispatch": {
        "task": "reminders.scan_and_dispatch",
        "schedule": settings.SCHEDULER_SCAN_INTERVAL_SECONDS,
    },
    "generate-recurring": {
        "task": "reminders.generate_recurring",
        "schedule": settings.SCHEDULER_SCAN_INTERVAL_SECONDS,
    },
    "cleanup-expired-recurring": {
        "task": "reminders.cleanup_expired_recurring",
        "schedule": 3600,  # Run every hour
    }
}

# Ensure tasks are registered when worker starts
try:
    from . import tasks as _tasks  # noqa: F401
    from . import recurring_tasks as _recurring_tasks  # noqa: F401
except Exception:
    pass



