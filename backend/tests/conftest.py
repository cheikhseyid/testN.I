import os

import pytest
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/eau")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    # Context manager runs the lifespan, i.e. create_all at startup.
    with TestClient(app) as c:
        yield c
