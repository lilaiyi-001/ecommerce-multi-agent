from __future__ import annotations
from unittest.mock import patch
"""Agent纯计算逻辑单元测试"""

import pytest
from app.agents.agent_02_product_selection.product_selection import (
    calculate_explosive_index, compute_price_distribution, _normalize,
)
from app.agents.agent_03_trend_forecast.trend_forecast import (
    _linear_regression_forecast, _moving_average_forecast,
    _exponential_smoothing_forecast, _detect_trend, _select_algorithm,
)
from app.agents.agent_08_inventory_advice.inventory_advice import analyze_inventory
from app.schemas.inventory import InventoryInput

class TestMinMaxNormalize:
    def test_normal_range(self):
        result = _normalize([10, 20, 30, 40, 50])
        assert result[10] == 0.0
        assert result[50] == 1.0
    def test_all_same(self):
        result = _normalize([5, 5, 5])
        assert all(v == 0.5 for v in result.values())
    def test_single_value(self):
        result = _normalize([7])
        assert result[7] == 0.5

class TestExplosiveIndex:
    def test_ranking_order(self):
        products = [
            {"product_id": 1, "title": "A", "price": 100, "rating_rate": 4.5,
             "rating_count": 500, "avg_daily_sales": 100},
            {"product_id": 2, "title": "B", "price": 50, "rating_rate": 2.0,
             "rating_count": 10, "avg_daily_sales": 5},
            {"product_id": 3, "title": "C", "price": 80, "rating_rate": 4.0,
             "rating_count": 200, "avg_daily_sales": 50},
        ]
        scored = calculate_explosive_index(products)
        scored.sort(key=lambda p: p["explosive_index"], reverse=True)
        assert scored[0]["product_id"] == 1
        assert scored[-1]["product_id"] == 2

class TestPriceDistribution:
    def test_bands(self):
        products = [{"product_id": i, "price": p} for i, p in enumerate(
            [10, 20, 30, 40, 50, 60, 70, 80, 90, 100], 1)]
        dist = compute_price_distribution(products)
        assert dist["min"] == 10
        assert dist["max"] == 100
        assert len(dist["bands"]) == 4

class TestLinearRegression:
    def test_positive_trend(self):
        forecast = _linear_regression_forecast(list(range(1, 11)), 3, 10)
        assert len(forecast) == 3
        assert forecast[0] > 10

class TestMovingAverage:
    def test_constant_output(self):
        forecast = _moving_average_forecast([5, 6, 5, 6, 5, 6], 4)
        assert len(forecast) == 4

class TestExponentialSmoothing:
    def test_produces_values(self):
        forecast = _exponential_smoothing_forecast(list(range(10)), 5)
        assert len(forecast) == 5

class TestDetectTrend:
    def test_rising(self):
        direction, _ = _detect_trend(list(range(1, 31)))
        assert direction == "上升"
    def test_falling(self):
        direction, _ = _detect_trend(list(range(30, 0, -1)))
        assert direction == "下降"

class TestAlgorithmSelection:
    def test_enough_data(self):
        algo = _select_algorithm(list(range(30)))
        assert algo.selected_method != "fallback_category_avg"

class TestInventoryAdvice:
    def test_low_stock_reorder(self):
        result = analyze_inventory(InventoryInput(
            product_id=1,
            product={"title": "T", "current_stock": 10, "avg_daily_sales": 5},
            trend_info={"demand_trend": "平稳"},
        ))
        assert result.advice == "补货"
    def test_healthy_maintain(self):
        result = analyze_inventory(InventoryInput(
            product_id=2,
            product={"title": "T2", "current_stock": 300, "avg_daily_sales": 5},
            trend_info={"demand_trend": "平稳"},
        ))
        assert result.advice == "维持"
    def test_overstock_clearance(self):
        result = analyze_inventory(InventoryInput(
            product_id=3,
            product={"title": "T3", "current_stock": 2000, "avg_daily_sales": 5},
            trend_info={"demand_trend": "平稳"},
        ))
        assert result.advice == "清仓"
    def test_no_data_graceful(self):
        result = analyze_inventory(InventoryInput(
            product_id=4, product={"title": "Ghost"}, trend_info={},
        ))
        assert result.urgency == "低"

# ---- 2.2 选品交叉数据注入 ----

class TestSelectionWithCrossData:
    """验证选品 Agent 正确使用三表交叉数据"""
    def test_ranking_includes_cross_fields(self):
        """ProductRank 应填充 price_vs_market / stock_health / margin_pct"""
        from app.agents.agent_02_product_selection.product_selection import analyze_products
        from app.schemas.selection import SelectionInput
        products = [
            {"product_id": 1, "title": "耳机", "category": "数码", "price": 89.0,
             "rating_rate": 4.5, "rating_count": 520, "avg_daily_sales": 35.0},
            {"product_id": 2, "title": "充电宝", "category": "数码", "price": 69.0,
             "rating_rate": 4.0, "rating_count": 180, "avg_daily_sales": 25.0},
        ]
        cross_views = [
            {"product_id": 1, "derived": {"price_vs_market": -10.0, "stock_health": "充足", "margin_pct": 38.2}},
            {"product_id": 2, "derived": {"price_vs_market": 10.0, "stock_health": "预警", "margin_pct": 20.0}},
        ]
        with patch("app.agents.agent_02_product_selection.product_selection.get_feishu_products", return_value=products):
            with patch("app.agents.agent_02_product_selection.product_selection.get_demo_products", return_value=[]):
                with patch("app.services.cross_table.get_all_cross_views", return_value=cross_views):
                    result = analyze_products(SelectionInput(category="数码", top_n=2))
        assert len(result.ranking) == 2
        r1 = result.ranking[0]
        r2 = result.ranking[1]
        assert r1.price_vs_market == -10.0
        assert r1.stock_health == "充足"
        assert r1.margin_pct == 38.2
        assert r2.price_vs_market == 10.0
        assert r2.stock_health == "预警"
        # cross_summary 应包含交叉数据信息
        assert "交叉对比" in result.cross_summary

    def test_cross_data_failure_does_not_break(self):
        """交叉数据加载失败时，选品分析照常工作（降级）"""
        from app.agents.agent_02_product_selection.product_selection import analyze_products
        from app.schemas.selection import SelectionInput
        products = [
            {"product_id": 1, "title": "耳机", "category": "数码", "price": 89.0,
             "rating_rate": 4.5, "rating_count": 520, "avg_daily_sales": 35.0},
        ]
        with patch("app.agents.agent_02_product_selection.product_selection.get_feishu_products", return_value=products):
            with patch("app.services.cross_table.get_all_cross_views", side_effect=RuntimeError("cross down")):
                result = analyze_products(SelectionInput(category="数码", top_n=1))
        assert len(result.ranking) == 1
        assert result.ranking[0].stock_health == "未知"
        assert result.ranking[0].price_vs_market is None
        assert result.cross_summary == ""

    def test_downstream_includes_cross_data(self):
        """for_downstream 应包含交叉对比字段"""
        from app.agents.agent_02_product_selection.product_selection import analyze_products
        from app.schemas.selection import SelectionInput
        products = [
            {"product_id": 1, "title": "耳机", "category": "数码", "price": 89.0,
             "rating_rate": 4.5, "rating_count": 520, "avg_daily_sales": 35.0},
        ]
        cross_views = [
            {"product_id": 1, "derived": {"price_vs_market": -10.0, "stock_health": "充足", "margin_pct": 38.2}},
        ]
        with patch("app.agents.agent_02_product_selection.product_selection.get_feishu_products", return_value=products):
            with patch("app.agents.agent_02_product_selection.product_selection.get_demo_products", return_value=[]):
                with patch("app.services.cross_table.get_all_cross_views", return_value=cross_views):
                    result = analyze_products(SelectionInput(category="数码", top_n=1))
        ds = result.for_downstream
        recs = ds.get("recommended_products", [])
        assert len(recs) == 1
        assert "price_vs_market" in recs[0]
        assert "stock_health" in recs[0]
        assert "margin_pct" in recs[0]