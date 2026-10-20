"""RQ worker entrypoint: `python -m app.worker {ingestion,indexing}`.

- ingestion: parses untrusted uploads. Each job runs in a freshly forked, memory-capped process.
- indexing: chunks and embeds extracted text. Jobs run in-process (SimpleWorker) so the
  embedding model is loaded once at startup instead of once per document.

RQ relies on os.fork and SIGALRM, so run this inside Docker/Linux (or WSL), not native Windows.
"""

import argparse
import logging

from redis import Redis
from rq import Queue, SimpleWorker, Worker

from app.config import get_settings
from app.ingestion.queue import INDEXING_QUEUE, INGESTION_QUEUE

WORKER_CLASSES: dict[str, type[Worker]] = {INGESTION_QUEUE: Worker, INDEXING_QUEUE: SimpleWorker}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("queue", choices=sorted(WORKER_CLASSES), nargs="?", default=INGESTION_QUEUE)
    queue_name = parser.parse_args().queue
    logging.basicConfig(level=logging.INFO)

    if queue_name == INDEXING_QUEUE:
        from app.embeddings import get_embedder

        get_embedder()  # fail fast if the model is missing, and keep it loaded for every job

    connection = Redis.from_url(get_settings().redis_url)
    worker_class = WORKER_CLASSES[queue_name]
    worker_class([Queue(queue_name, connection=connection)], connection=connection).work()


if __name__ == "__main__":
    main()
