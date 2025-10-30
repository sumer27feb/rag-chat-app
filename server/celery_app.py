from celery import Celery
from config import settings
import platform

# Always use a single instance
broker_url = settings.REDIS_URL or "redis://localhost:6379/0"

celery = Celery(
    "rag_app",
    broker=broker_url,
    backend=broker_url,
    include=["tasks.chat_tasks"]
)

# Windows compatibility (solo pool, no multiprocessing)
if platform.system() == "Windows":
    celery.conf.worker_pool = "solo"

# Common config
celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)
