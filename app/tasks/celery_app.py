"""
Celery configuration.
"""
from celery import Celery

from app.config import settings

# Construct result backend URL by altering database index if possible
backend_url = settings.REDIS_URL
if "/0" in backend_url:
    backend_url = backend_url.replace("/0", "/1")

celery_app = Celery(
    "event_booking",
    broker=settings.REDIS_URL,
    backend=backend_url,
    include=["app.tasks.email_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,          # task ACKed only after successful execution
    worker_prefetch_multiplier=1, # prevent worker from hoarding tasks
)
