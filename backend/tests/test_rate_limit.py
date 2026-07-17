"""请求限流测试"""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.utils.rate_limiter import RateLimitMiddleware


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    RateLimitMiddleware.reset_all_buckets()
    yield


class TestRateLimiter:

    def test_health_whitelisted(self):
        client = TestClient(app)
        for _ in range(50):
            resp = client.get("/health")
            assert resp.status_code == 200

    def test_root_whitelisted(self):
        client = TestClient(app)
        for _ in range(50):
            resp = client.get("/")
            assert resp.status_code == 200

    def test_api_rate_limited(self):
        client = TestClient(app)
        login = client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "admin123",
        })
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        statuses = []
        for _ in range(40):
            resp = client.post("/api/v1/selection/analyze", json={
                "category": "electronics", "top_n": 1,
            }, headers=headers)
            statuses.append(resp.status_code)
        assert 200 in statuses
        assert 429 in statuses

    def test_429_has_retry_after_header(self):
        client = TestClient(app)
        login = client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "admin123",
        })
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        for _ in range(35):
            resp = client.post("/api/v1/selection/analyze", json={
                "category": "electronics", "top_n": 1,
            }, headers=headers)
            if resp.status_code == 429:
                assert "retry-after" in resp.headers
                assert "retry_after_seconds" in resp.json()
                break
        else:
            pytest.fail("Expected 429 response not received")
