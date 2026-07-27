# tests/conftest.py
"""
Shared test fixtures.

Each test gets a FRESH in-memory SQLite database via a get_db dependency
override, so tests never touch the real rasa_gate.db and are order-independent.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.session import Base, get_db
from app.main import app


@pytest.fixture(autouse=True)
def _no_rasa_startup_wait(monkeypatch):
    """
    The app's lifespan waits for Rasa to be reachable on startup. Tests
    don't run a real Rasa server, so disable that wait everywhere — without
    this, every test that spins up TestClient(app) would hang for up to
    RASA_STARTUP_MAX_RETRIES * RASA_STARTUP_RETRY_DELAY seconds.
    """
    monkeypatch.setattr(settings, "rasa_startup_wait", False)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # single shared in-memory DB per test
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
