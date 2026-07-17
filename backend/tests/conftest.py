"""pytest global config - register agents, provide test fixtures"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    init_db()
    yield


@pytest.fixture
def client():
    return TestClient(app)
