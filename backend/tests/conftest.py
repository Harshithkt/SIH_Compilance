"""Test database isolation and authentication helpers.

Without the dependency override below, `TestClient(app)` resolves `get_db` to the real
engine and the suite reads and writes `backend/labellens.db` — the demo database. That
both pollutes the data an officer is demonstrating with and makes the tests inherit
whatever schema that file happens to carry, so a stale column definition fails the
suite rather than the code. Each run instead gets its own in-memory database built from
the current models (StaticPool keeps every connection pointed at the same one).

Take the `client` fixture rather than importing the client from this module: an
explicit `from tests.conftest import ...` loads this file a second time, under a
different module identity from the one pytest itself loaded, and the two copies then
hold two different in-memory databases — tables get created on one while requests run
against the other.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import bootstrap_users
from app.config import settings
from app.database import Base, get_db
from app.main import app

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _get_test_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _get_test_db
_client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.create_all(bind=engine)
    with TestSession() as db:
        bootstrap_users(db)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return _client


@pytest.fixture
def db_session():
    """The same database the API is using, for arranging state that no endpoint
    deliberately exposes — a lapsed response window, say."""
    with TestSession() as session:
        yield session


@pytest.fixture
def auth_headers():
    """Bearer headers for one of the bootstrap accounts, default the officer."""

    def _headers(username: str = "officer") -> dict[str, str]:
        response = _client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": settings.bootstrap_password},
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _headers
