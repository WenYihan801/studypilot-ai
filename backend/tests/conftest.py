import os
import uuid

# Must be set before the app (and its cached Settings) are imported.
os.environ.update(
    {
        "APP_ENV": "test",
        "DATA_BACKEND": "memory",
        "AI_PROVIDER": "mock",
        "RETRIEVAL_MIN_SCORE": "0.05",
        "SUPABASE_URL": "https://test-project.supabase.co",
        "CORS_ORIGINS": "http://localhost:5173",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api import deps  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.core.security import CurrentUser, get_current_user  # noqa: E402
from app.main import create_app  # noqa: E402
from tests.helpers import make_docx, make_pdf  # noqa: E402

USER_A = str(uuid.UUID(int=1))
USER_B = str(uuid.UUID(int=2))


def _fake_current_user(request) -> CurrentUser:
    # Test token format: "Bearer test:<user-id>"
    from app.core.errors import UnauthorizedError

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer test:"):
        raise UnauthorizedError("Missing bearer token.")
    uid = auth.removeprefix("Bearer test:")
    return CurrentUser(id=uid, email=f"{uid[-4:]}@example.com", access_token="test")


@pytest.fixture(autouse=True)
def _reset_state():
    get_settings.cache_clear()
    deps.memory_db.reset()
    deps.memory_storage.objects.clear()
    deps._provider_cache.clear()
    limiter.reset()
    yield


@pytest.fixture
def app():
    application = create_app()
    from fastapi import Request

    def override(request: Request) -> CurrentUser:
        return _fake_current_user(request)

    application.dependency_overrides[get_current_user] = override
    return application


def _client(app, user_id: str | None) -> TestClient:
    c = TestClient(app)
    if user_id:
        c.headers["Authorization"] = f"Bearer test:{user_id}"
    return c


@pytest.fixture
def client_a(app) -> TestClient:
    return _client(app, USER_A)


@pytest.fixture
def client_b(app) -> TestClient:
    return _client(app, USER_B)


@pytest.fixture
def anon(app) -> TestClient:
    return _client(app, None)


@pytest.fixture
def workspace(client_a) -> dict:
    r = client_a.post("/api/v1/workspaces", json={"name": "Database Systems", "description": "CS2102"})
    assert r.status_code == 201, r.text
    return r.json()


DB_NOTES = """# Normalization

Database normalization is the process of organizing tables to reduce data redundancy and improve data integrity.
First normal form (1NF) requires that every column holds atomic values and there are no repeating groups.
Second normal form (2NF) requires 1NF and that every non-key attribute depends on the whole primary key.
Third normal form (3NF) removes transitive dependencies between non-key attributes.

# Transactions

A transaction is a unit of work that must satisfy the ACID properties: atomicity, consistency, isolation and durability.
Atomicity means a transaction either completes entirely or has no effect at all.
"""

NETWORK_NOTES = """# Transport Layer

TCP is a connection-oriented protocol that provides reliable, ordered delivery with retransmission and congestion control.
UDP is a connectionless protocol that sends datagrams without delivery guarantees, which makes it faster for streaming.
"""


def upload(client: TestClient, workspace_id: str, name: str, data: bytes, mime: str):
    return client.post(f"/api/v1/workspaces/{workspace_id}/documents", files={"file": (name, data, mime)})


@pytest.fixture
def ready_doc(client_a, workspace) -> dict:
    r = upload(client_a, workspace["id"], "db-notes.md", DB_NOTES.encode(), "text/markdown")
    assert r.status_code == 201, r.text
    doc = client_a.get(f"/api/v1/documents/{r.json()['id']}").json()
    assert doc["status"] == "READY", doc
    return doc


__all__ = ["make_pdf", "make_docx", "upload", "DB_NOTES", "NETWORK_NOTES", "USER_A", "USER_B"]
