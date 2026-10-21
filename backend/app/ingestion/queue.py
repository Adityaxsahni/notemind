"""Job queues. Jobs are referenced by import path so the API never imports parsers or torch."""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from redis import Redis
from rq import Callback, Queue

from app.redis_client import get_redis

Enqueue = Callable[[uuid.UUID], None]

INGESTION_QUEUE = "ingestion"  # parses untrusted files: forked, memory-capped work-horse
INDEXING_QUEUE = "indexing"  # chunks + embeds extracted text: keeps the model loaded

INGESTION_TIMEOUT_SECONDS = 900  # a 200 MB, 2000-page PDF
INDEXING_TIMEOUT_SECONDS = 1800  # embedding ~10k chunks on CPU

_ON_FAILURE = Callback("app.ingestion.tasks.on_job_failure")


def _enqueue(redis: Redis, queue: str, func: str, timeout: int, document_id: uuid.UUID) -> None:
    Queue(queue, connection=redis).enqueue(
        func,
        str(document_id),
        job_timeout=timeout,
        result_ttl=0,
        failure_ttl=24 * 3600,
        on_failure=_ON_FAILURE,
    )


def enqueue_ingestion(redis: Redis, document_id: uuid.UUID) -> None:
    _enqueue(
        redis,
        INGESTION_QUEUE,
        "app.ingestion.tasks.process_document",
        INGESTION_TIMEOUT_SECONDS,
        document_id,
    )


def enqueue_indexing(redis: Redis, document_id: uuid.UUID) -> None:
    _enqueue(
        redis,
        INDEXING_QUEUE,
        "app.ingestion.tasks.index_document_job",
        INDEXING_TIMEOUT_SECONDS,
        document_id,
    )


def get_enqueue() -> Enqueue:
    redis = get_redis()
    return lambda document_id: enqueue_ingestion(redis, document_id)


EnqueueDep = Annotated[Enqueue, Depends(get_enqueue)]
