import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Configure JWT settings before importing the FastAPI app.
os.environ["JWT_SECRET"] = "test_jwt_secret_key_min_32_charstest_jwt_secret_key_min_32_chars!!"
os.environ["JWT_ALG"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"

from app.api.deps import get_db
from app.db.base import Base
from app.main import app

engine = create_engine(
    "sqlite+pysqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def override_get_db() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_test_db() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def db_session_factory() -> sessionmaker[Session]:
    return TestingSessionLocal


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app, backend_options={"use_uvloop": True}) as test_client:
        yield test_client
