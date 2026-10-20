"""RQ worker entrypoint: `python -m app.worker`.

RQ relies on os.fork, so run this inside Docker/Linux (or WSL), not native Windows.
"""

from redis import Redis
from rq import Queue, Worker

from app.config import get_settings

QUEUES = ["ingestion"]


def main() -> None:
    connection = Redis.from_url(get_settings().redis_url)
    queues = [Queue(name, connection=connection) for name in QUEUES]
    Worker(queues, connection=connection).work()


if __name__ == "__main__":
    main()
