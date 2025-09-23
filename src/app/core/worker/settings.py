from arq.connections import RedisSettings

from ...core.config import settings
from .functions import sample_background_task, process_document_for_rag, shutdown, startup

REDIS_QUEUE_HOST = settings.REDIS_QUEUE_HOST
REDIS_QUEUE_PORT = settings.REDIS_QUEUE_PORT


class WorkerSettings:
    functions = [sample_background_task, process_document_for_rag]
    redis_settings = RedisSettings(
        host=REDIS_QUEUE_HOST, 
        port=REDIS_QUEUE_PORT
    )
    on_startup = startup
    on_shutdown = shutdown
    handle_signals = False
    max_tries = 3  # Retry failed jobs
    job_timeout = 300  # 5 minute job timeout
    keep_result = 3600  # Keep job results for 1 hour
