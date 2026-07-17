"""Basic endpoint tests"""
import pytest
from app.utils.auth import create_access_token, verify_token


class TestBasicEndpoints:
    """Root and health endpoints"""

    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


class TestAuth:
    """Authentication module tests"""

    def test_login_success(self, client):
        resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    def test_verify_token(self, client):
        login_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
        token = login_resp.json()["access_token"]
        resp = client.get("/api/v1/auth/verify", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["username"] == "admin"

    def test_no_token_rejected(self, client):
        resp = client.post("/api/v1/selection/analyze", json={"category": "electronics", "top_n": 3})
        assert resp.status_code == 401

    def test_jwt_util(self):
        token = create_access_token("testuser")
        payload = verify_token(token)
        assert payload["sub"] == "testuser"
