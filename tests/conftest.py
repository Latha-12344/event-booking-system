"""
Pytest test fixtures.
"""
from collections.abc import Generator
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine, get_db
from app.main import app
from app.tasks.celery_app import celery_app


@pytest.fixture(scope="session", autouse=True)
def configure_celery():
    """Ensure Celery runs in eager mode during testing to prevent broker calls."""
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True


@pytest.fixture(autouse=True)
def clean_db():
    """Clean all tables before each test to guarantee test isolation."""
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE bookings, events, users RESTART IDENTITY CASCADE;"))
        conn.commit()
    yield


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Yield a database session for test verification."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
