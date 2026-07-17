
"""数据传递集成测试"""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.selection import SelectionInput
from app.schemas.competitor import CompetitorInput
from app.schemas.inventory import InventoryInput
from app.agents.agent_02_product_selection.product_selection import analyze_products
from app.agents.agent_04_competitor_analysis.competitor_analysis import analyze_competitor
from app.agents.agent_08_inventory_advice.inventory_advice import analyze_inventory


class TestA2Downstream:

    def test_selection_produces_downstream(self):
        a2 = analyze_products(SelectionInput(category="electronics", top_n=3))
        downstream = a2.for_downstream or {}
        assert "recommended_products" in downstream
        assert len(downstream["recommended_products"]) > 0


class TestA4Downstream:

    def test_competitor_produces_avg_price(self):
        a4 = analyze_competitor(CompetitorInput(
            target_product_id=1, category="electronics",
            target_product={"title": "Test", "price": 99.0, "rating_rate": 4.0, "rating_count": 100},
        ))
        downstream = a4.for_downstream or {}
        assert "competitor_avg_price" in downstream


class TestA8Standalone:

    def test_inventory_basic(self):
        result = analyze_inventory(InventoryInput(
            product_id=5,
            product={"title": "ST", "current_stock": 30, "avg_daily_sales": 10},
            trend_info={"demand_trend": "平稳"},
        ))
        assert result.advice in ("补货", "维持", "清仓")
        assert result.stockout_days >= 0


class TestSelectionAPI:

    def test_api_returns_ranking(self):
        client = TestClient(app)
        login = client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "admin123",
        })
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.post("/api/v1/selection/analyze", json={
            "category": "electronics", "top_n": 3,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "ranking" in data or "total_products" in data
