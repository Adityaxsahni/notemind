import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from rq import Callback, Queue

from app.ingestion.tasks import JOB_TIMEOUT_SECONDS, on_job_failure, process_document
from app.redis_client import get_redis

Enqueue = Callable[[uuid.UUID], None]


def get_enqueue() -> Enqueue:
    queue = Queue("ingestion", connection=get_redis())

    def enqueue(document_id: uuid.UUID) -> None:
        queue.enqueue(
            process_document,
            str(document_id),
            job_timeout=JOB_TIMEOUT_SECONDS,
            result_ttl=0,
            failure_ttl=24 * 3600,
            on_failure=Callback(on_job_failure),
        )

    return enqueue


EnqueueDep = Annotated[Enqueue, Depends(get_enqueue)]
