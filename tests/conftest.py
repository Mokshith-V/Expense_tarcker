"""Shared test setup.

Tests run against a throwaway in-memory SQLite database, so MySQL
doesn't need to be running and your real data is never touched.
"""
import os

# Must be set BEFORE the app is imported, because app/config.py reads them on import.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

# StaticPool: every session shares ONE connection, so they all see the same in-memory database.
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session():
    """Fresh, empty tables for every single test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    """A TestClient whose routes use the test database instead of MySQL."""
    def override_get_db():
        yield db_session

    # One override covers every router, because they all use the same get_db.
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def make_user(client):
    """Register a user through the real API, log in, and return auth headers."""
    def _make(username: str, password: str = "password123") -> dict:
        response = client.post("/auth/register", json={
            "username": username,
            "email": f"{username}@example.com",
            "password": password,
        })
        assert response.status_code == 201, response.text
        response = client.post("/auth/token", data={"username": username, "password": password})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    return _make


@pytest.fixture
def auth_headers(make_user):
    return make_user("mokshith")


@pytest.fixture
def other_headers(make_user):
    return make_user("ravi")


@pytest.fixture
def category_ids(client, auth_headers):
    """{"Food": 1, "Transport": 2, ...} for the main test user."""
    response = client.get("/categories", headers=auth_headers)
    return {c["name"]: c["id"] for c in response.json()}


@pytest.fixture
def add_expense(client, auth_headers):
    """Create an expense for the main user; any field can be overridden."""
    def _add(headers: dict | None = None, **fields) -> dict:
        body = {
            "amount": "100.00",
            "description": "Test expense",
            "spent_on": "2026-10-10",
            "payment_method": "upi",
        }
        body.update(fields)
        response = client.post("/expenses", json=body, headers=headers or auth_headers)
        assert response.status_code == 201, response.text
        return response.json()
    return _add
