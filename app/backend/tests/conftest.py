"""Shared test fixtures for the merged backend."""

from collections.abc import Iterator
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.backend.api.deps import (
    get_ai_provider,
    get_ai_repository,
    get_session_repository,
)
from app.backend.core.database import Base, ensure_runtime_schema, get_db
from app.backend.integrations.ai_provider import StubAIProviderClient
from app.backend.main import create_app


def create_test_client() -> TestClient:
    get_ai_repository.cache_clear()
    get_ai_provider.cache_clear()
    get_session_repository.cache_clear()

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
    )
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema(engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_ai_provider] = lambda: StubAIProviderClient()
    client = TestClient(app)
    client.session_factory = testing_session_local
    return client


@pytest.fixture
def client() -> Iterator[TestClient]:
    with create_test_client() as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client) -> dict[str, str]:
    client.post(
        "/v1/auth/register",
        json={
            "email": "fixture@example.com",
            "display_name": "Fixture User",
            "password": "strong-password",
        },
    )
    login_response = client.post(
        "/v1/auth/login",
        json={
            "email": "fixture@example.com",
            "password": "strong-password",
        },
    )
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}
