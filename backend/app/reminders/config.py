from pydantic_settings import BaseSettings
from typing import Optional


class ReminderSettings(BaseSettings):
    # Service configuration
    SERVICE_HOST: str
    SERVICE_PORT: int

    # RabbitMQ configuration
    RABBITMQ_URL: str
    RABBITMQ_EXCHANGE: str
    RABBITMQ_INPUT_QUEUE: str
    RABBITMQ_OUTPUT_QUEUE: str
    RABBITMQ_INPUT_ROUTING_KEY: str
    RABBITMQ_OUTPUT_ROUTING_KEY: str

    # Celery configuration
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    WORKER_CONCURRENCY: int = 4

    # Scheduling
    SCHEDULER_SCAN_INTERVAL_SECONDS: int
    SCHEDULER_BATCH_SIZE: int

    # FCM
    FCM_PROJECT_ID: Optional[str] = None
    FCM_CREDENTIALS_JSON: Optional[str] = None  # path or inline JSON via env

    # Metrics
    METRICS_ENABLED: bool

    class Config:
        env_prefix = "REMINDER_"


settings = ReminderSettings()


