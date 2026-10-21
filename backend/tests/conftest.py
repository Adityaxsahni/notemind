import os

os.environ["ENVIRONMENT"] = "test"  # must be set before app settings are first loaded
os.environ["BOT_MIN_FILL_SECONDS"] = "0"  # bot-check tests set their own delay

import fakeredis  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app import (
    models,  # noqa: E402, F401
    rls,  # noqa: E402
)
from app.config import get_settings  # noqa: E402
from app.db import Base, get_session, use_app_role  # noqa: E402
from app.embeddings import get_embedder  # noqa: E402
from app.ingestion.ocr import make_transcriber  # noqa: E402
from app.ingestion.queue import get_enqueue  # noqa: E402
from app.ingestion.tasks import index_document, ingest_document  # noqa: E402
from app.llm.providers import get_llm_provider  # noqa: E402
from app.main import app  # noqa: E402
from app.rag.reranker import get_reranker  # noqa: E402
from app.redis_client import get_redis  # noqa: E402
from app.storage import LocalStorage, get_storage  # noqa: E402
from tests.fakes import FakeEmbedder, FakeLLM, FakeReranker, FakeVisionLLM  # noqa: E402

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
    with engine.begin() as conn:
        rls.apply(lambda sql: conn.execute(text(sql)))
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def app_engine(engine):
    """Connections as the restricted role the real app uses, so every API test also runs
    under row-level security. The plain `engine` (table owner) is for inspecting rows."""
    app_engine = use_app_role(create_engine(engine.url))
    yield app_engine
    app_engine.dispose()


@pytest.fixture
def app_db(app_engine, db):
    return sessionmaker(bind=app_engine, expire_on_commit=False)


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
def reranker():
    return FakeReranker()


@pytest.fixture
def llm():
    return FakeLLM()


@pytest.fixture
def vision_llm():
    return FakeVisionLLM()


@pytest.fixture
def redis():
    return fakeredis.FakeRedis()


@pytest.fixture
def make_client(app_db, storage, embedder, reranker, llm, vision_llm, redis):
    """Returns a factory: each call is a separate browser with its own cookie jar."""

    def _session():
        session = app_db()
        try:
            yield session
        finally:
            session.close()

    def _index_inline(document_id):
        with app_db() as session:
            index_document(session, embedder, document_id)

    def _enqueue_inline(document_id):
        # Run ingestion + indexing synchronously so tests see the final document state.
        with app_db() as session:
            ingest_document(
                session,
                storage,
                document_id,
                index=_index_inline,
                transcriber_for=lambda user_id: make_transcriber(
                    redis, user_id, vision_llm if vision_llm.configured else None
                ),
            )

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_redis] = lambda: redis
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_enqueue] = lambda: _enqueue_inline
    app.dependency_overrides[get_embedder] = lambda: embedder
    app.dependency_overrides[get_reranker] = lambda: reranker
    app.dependency_overrides[get_llm_provider] = lambda: llm
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


def human(client) -> dict:
    """The bot-check fields our own sign-up and log-in forms send."""
    return {"form_token": client.get("/auth/form-token").json()["token"], "website": ""}


def signup(client, email, password=GOOD_PASSWORD):
    response = client.post(
        "/auth/signup", json={**human(client), "email": email, "password": password}
    )
    assert response.status_code == 201, response.text
    return response.json()
