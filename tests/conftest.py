"""Pytest configuration, fixtures and test client setup."""

import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import close_db_connection, init_db


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Configure an isolated temporary SQLite database for testing."""
    temp_dir = tempfile.mkdtemp()
    test_db = os.path.join(temp_dir, "test_payments.db")
    settings.DB_PATH = test_db
    settings.APP_ENV = "test"
    settings.DEBUG = True

    init_db()

    yield

    close_db_connection()
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except OSError:
            pass


@pytest.fixture
def client():
    """Provide a test client instance with the FastAPI application."""
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
