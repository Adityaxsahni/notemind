import os

os.environ["ENVIRONMENT"] = "test"  # must be set before app settings are first loaded

import fakeredis  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app import models  # noqa: E402, F401
from app.config import get_settings  # noqa: E402
from app.db import Base, get_session  # noqa: E402
from app.ingestion.queue import get_enqueue  # noqa: E402
from app.ingestion.tasks import index_document, ingest_document  # noqa: E402
from app.main import app  # noqa: E402
from app.redis_client import get_redis  # noqa: E402
from app.storage import LocalStorage, get_storage  # noqa: E402
from tests.fakes import FakeEmbedder  # noqa: E402

GOOD_PASSWORD = "correct-horse-battery-42"  # pragma: allowlist secret


def _test_database_url():
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return make_url(explicit)
    # Never run tests against the dev database: same server, separate database.
    return make_url(get_settings().database_url).set(database="notemind_test")


@pytest.fixture(scope="session")
def engine():
    url = _test_database_url()
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
        )
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()

    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine):
    """Session factory for tests that need to inspect or tweak rows directly."""
    yield sessionmaker(bind=engine, expire_on_commit=False)
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} CASCADE"))


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path / "uploads")


@pytest.fixture
def embedder():
    return FakeEmbedder()


@pytest.fixture
def make_client(db, storage, embedder):
    """Returns a factory: each call is a separate browser with its own cookie jar."""
    redis = fakeredis.FakeRedis()

    def _session():
        session = db()
        try:
            yield session
        finally:
            session.close()

    def _index_inline(document_id):
        with db() as session:
            index_document(session, embedder, document_id)

    def _enqueue_inline(document_id):
        # Run ingestion + indexing synchronously so tests see the final document state.
        with db() as session:
            ingest_document(session, storage, document_id, index=_index_inline)

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_redis] = lambda: redis
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_enqueue] = lambda: _enqueue_inline
    clients = []

    def _make():
        # https base URL: auth cookies are Secure and would not be sent over http.
        client = TestClient(app, base_url="https://testserver")
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.close()
    app.dependency_overrides.clear()


@pytest.fixture
def client(make_client):
    return make_client()


def signup(client, email, password=GOOD_PASSWORD):
    response = client.post("/auth/signup", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    return response.json()
