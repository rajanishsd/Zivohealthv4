"""Reminder service module (API, Celery worker, scheduler, dispatcher).

This module is intended to run as a separate service container. It exposes
HTTP APIs for the existing backend to create and query reminders, and uses
RabbitMQ + Celery for processing and scheduling.
"""


