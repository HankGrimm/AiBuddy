import os
# Override DATABASE_URL before any app module is imported so that database.py
# does not attempt to connect to Postgres during test collection.
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Patch the module-level engine in database.py with an in-memory SQLite engine.
from app.core import database as _db_module

_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
# Replace the module-level objects before anything uses them.
_db_module.engine = _test_engine
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)
_db_module.SessionLocal = TestingSessionLocal

from app.core.database import Base, get_db
from app.main import app


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=_test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
