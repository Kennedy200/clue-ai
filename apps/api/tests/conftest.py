import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="clue-test-")
os.environ["STORAGE_PATH"] = _tmp
os.environ["APP_MODE"] = "saas"
os.environ["OPENROUTER_API_KEY"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from clue.core import ratelimit  # noqa: E402
from clue.core.db import Base, SessionLocal, engine  # noqa: E402
from clue.main import app  # noqa: E402
from clue.seed import ensure_reference_data  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        ensure_reference_data(db)
    ratelimit.reset()
    yield


@pytest.fixture
def db():
    with SessionLocal() as s:
        yield s


@pytest.fixture
def client():
    return TestClient(app)


def signup(client, email="a@example.com", pw="password123", **extra):
    r = client.post("/api/auth/signup", json={"email": email, "password": pw, **extra})
    assert r.status_code == 200, r.text
    return r.json()
