"""cross_table 交叉对比引擎 — 单元测试"""
from __future__ import annotations
import pytest
from unittest.mock import patch

MOCK_MASTER = [
    {"product_id": 1, "title": "无线蓝牙耳机", "category": "数码", "price": 89.0,
     "cost": 55.0, "rating_rate": 4.5, "rating_count": 520, "avg_daily_sales": 35.0},
    {"product_id": 2, "title": "纯棉T恤", "category": "服饰", "price": 49.0,
     "cost": 20.0, "rating_rate": 4.2, "rating_count": 310, "avg_daily_sales": 60.0},
]

MOCK_INVENTORY = [
    {"sku": "SKU-001", "product_name": "无线蓝牙耳机", "stock_qty": 200,
     "warning_stock": 50, "stock_status": "正常",
     "cumulative_outbound": 1200, "cumulative_sales": 1050},
    {"sku": "SKU-002", "product_name": "纯棉T恤", "stock_qty": 15,
     "warning_stock": 30, "stock_status": "预警",
     "cumulative_outbound": 800, "cumulative_sales": 780},
]

MOCK_CRAWLED = [
    {"sku": "SKU-001", "product_name": "蓝牙耳机Pro", "current_price": 99.0,
     "rating": 4.3, "sales": 420},
    {"sku": "SKU-003", "product_name": "充电宝20000mAh", "current_price": 79.0,
     "rating": 4.1, "sales": 310},
]


class TestFetchMasterProducts:
    def test_returns_dict(self):
        from app.services.cross_table import _fetch_master_products, clear_cache
        clear_cache()
        with patch("app.services.cross_table.get_feishu_products", return_value=MOCK_MASTER):
            result = _fetch_master_products()
        assert len(result) == 2
        assert result["1"]["title"] == "无线蓝牙耳机"

    def test_uses_cache(self):
        from app.services.cross_table import _fetch_master_products, clear_cache
        clear_cache()
        call_count = [0]

        def cf(category=""):
            call_count[0] += 1
            return MOCK_MASTER[:1]

        with patch("app.services.cross_table.get_feishu_products", side_effect=cf):
            _fetch_master_products()
            _fetch_master_products()
        assert call_count[0] == 1

    def test_empty_on_failure(self):
        from app.services.cross_table import _fetch_master_products, clear_cache
        clear_cache()
        with patch("app.services.cross_table.get_feishu_products", side_effect=RuntimeError):
            result = _fetch_master_products()
        assert result == {}


class TestFetchInventoryRecords:
    def test_returns_dict_by_sku(self):
        from app.services.cross_table import _fetch_inventory_records, clear_cache
        clear_cache()
        with patch("app.services.cross_table.get_feishu_inventory", return_value=MOCK_INVENTORY):
            result = _fetch_inventory_records()
        assert len(result) == 2
        assert result["SKU-001"]["stock_qty"] == 200

    def test_empty_on_failure(self):
        from app.services.cross_table import _fetch_inventory_records, clear_cache
        clear_cache()
        with patch("app.services.cross_table.get_feishu_inventory", side_effect=RuntimeError):
            result = _fetch_inventory_records()
        assert result == {}

    def test_skips_empty_sku(self):
        from app.services.cross_table import _fetch_inventory_records, clear_cache
        clear_cache()
        with patch("app.services.cross_table.get_feishu_inventory",
                   return_value=[{"sku": "", "product_name": "bad"}]):
            result = _fetch_inventory_records()
        assert result == {}


class TestFetchCrawledProducts:
    def test_returns_dict_by_sku(self):
        from app.services.cross_table import _fetch_crawled_products, clear_cache
        clear_cache()
        with patch("app.services.cross_table.get_feishu_crawled_products", return_value=MOCK_CRAWLED):
            result = _fetch_crawled_products()
        assert len(result) == 2
        assert result["SKU-001"]["current_price"] == 99.0

    def test_empty_on_failure(self):
        from app.services.cross_table import _fetch_crawled_products, clear_cache
        clear_cache()
        with patch("app.services.cross_table.get_feishu_crawled_products", side_effect=RuntimeError):
            result = _fetch_crawled_products()
        assert result == {}
# ---- 1.2 SKU 精准匹配器 ----

MOCK_INV_FOR_SKU = [
    {"sku": "SKU-001", "product_name": "无线蓝牙耳机", "stock_qty": 200},
    {"sku": "SKU-002", "product_name": "纯棉T恤", "stock_qty": 15},
]

MOCK_CR_FOR_SKU = [
    {"sku": "SKU-001", "product_name": "蓝牙耳机Pro", "current_price": 99.0},
    {"sku": "SKU-003", "product_name": "充电宝20000mAh", "current_price": 79.0},
]


class TestMatchBySku:
    def test_both_tables_matched(self):
        from app.services.cross_table import match_by_sku, clear_cache
        clear_cache()
        with patch("app.services.cross_table._fetch_inventory_records",
                   return_value={"SKU-001": MOCK_INV_FOR_SKU[0]}):
            with patch("app.services.cross_table._fetch_crawled_products",
                       return_value={"SKU-001": MOCK_CR_FOR_SKU[0]}):
                r = match_by_sku("SKU-001")
        assert r["inventory"] is not None
        assert r["crawled"] is not None
        assert r["inventory"]["stock_qty"] == 200
        assert r["crawled"]["current_price"] == 99.0

    def test_only_inventory_matched(self):
        from app.services.cross_table import match_by_sku, clear_cache
        clear_cache()
        with patch("app.services.cross_table._fetch_inventory_records",
                   return_value={"SKU-002": MOCK_INV_FOR_SKU[1]}):
            with patch("app.services.cross_table._fetch_crawled_products",
                       return_value={}):
                r = match_by_sku("SKU-002")
        assert r["inventory"] is not None
        assert r["crawled"] is None

    def test_only_crawled_matched(self):
        from app.services.cross_table import match_by_sku, clear_cache
        clear_cache()
        with patch("app.services.cross_table._fetch_inventory_records",
                   return_value={}):
            with patch("app.services.cross_table._fetch_crawled_products",
                       return_value={"SKU-003": MOCK_CR_FOR_SKU[1]}):
                r = match_by_sku("SKU-003")
        assert r["inventory"] is None
        assert r["crawled"] is not None

    def test_no_match_at_all(self):
        from app.services.cross_table import match_by_sku, clear_cache
        clear_cache()
        with patch("app.services.cross_table._fetch_inventory_records",
                   return_value={}):
            with patch("app.services.cross_table._fetch_crawled_products",
                       return_value={}):
                r = match_by_sku("NONEXISTENT")
        assert r["inventory"] is None
        assert r["crawled"] is None

    def test_empty_sku_returns_none(self):
        from app.services.cross_table import match_by_sku
        r = match_by_sku("")
        assert r["inventory"] is None
        assert r["crawled"] is None
# ---- 1.3 商品名称模糊匹配器 ----

MOCK_INV_FOR_NAME = {
    "SKU-A": {"product_name": "无线蓝牙耳机Pro", "stock_qty": 200},
    "SKU-B": {"product_name": "纯棉圆领T恤", "stock_qty": 15},
}

MOCK_CR_FOR_NAME = {
    "SKU-X": {"product_name": "蓝牙耳机运动版", "current_price": 99.0},
    "SKU-Y": {"product_name": "电冰箱双开门", "current_price": 2999.0},
}


class TestMatchByName:
    def test_close_match_both_tables(self):
        from app.services.cross_table import match_by_name, clear_cache
        clear_cache()
        with patch("app.services.cross_table._fetch_inventory_records",
                   return_value=MOCK_INV_FOR_NAME):
            with patch("app.services.cross_table._fetch_crawled_products",
                       return_value=MOCK_CR_FOR_NAME):
                r = match_by_name("无线蓝牙耳机")
        assert r["inventory"] is not None
        assert r["crawled"] is not None

    def test_only_inventory_close_match(self):
        from app.services.cross_table import match_by_name, clear_cache
        clear_cache()
        with patch("app.services.cross_table._fetch_inventory_records",
                   return_value=MOCK_INV_FOR_NAME):
            with patch("app.services.cross_table._fetch_crawled_products",
                       return_value={"SKU-Z": {"product_name": "跑步机", "current_price": 1999.0}}):
                r = match_by_name("纯棉T恤")
        assert r["inventory"] is not None
        assert r["crawled"] is None

    def test_no_match_at_all(self):
        from app.services.cross_table import match_by_name, clear_cache
        clear_cache()
        with patch("app.services.cross_table._fetch_inventory_records",
                   return_value=MOCK_INV_FOR_NAME):
            with patch("app.services.cross_table._fetch_crawled_products",
                       return_value=MOCK_CR_FOR_NAME):
                r = match_by_name("太空飞船")
        assert r["inventory"] is None
        assert r["crawled"] is None

    def test_empty_name(self):
        from app.services.cross_table import match_by_name
        r = match_by_name("")
        assert r["inventory"] is None
        assert r["crawled"] is None

    def test_partial_substring_match(self):
        """电冰箱 应匹配到 电冰箱双开门"""
        from app.services.cross_table import match_by_name, clear_cache
        clear_cache()
        with patch("app.services.cross_table._fetch_inventory_records",
                   return_value={}):
            with patch("app.services.cross_table._fetch_crawled_products",
                       return_value=MOCK_CR_FOR_NAME):
                r = match_by_name("电冰箱")
        assert r["crawled"] is not None
        assert r["crawled"]["current_price"] == 2999.0
# ---- 1.4 统一交叉视图入口 ----

PROD_MOCK_1 = {"product_id": 1, "title": "无线蓝牙耳机", "category": "数码", "price": 89.0}
PROD_MOCK_2 = {"product_id": 99, "title": "太空飞船模型", "category": "玩具", "price": 199.0}
PROD_MOCK_3 = {"product_id": 3, "title": "充电宝10000mAh", "category": "数码", "price": 69.0}
PROD_MOCK_NO_ID = {"product_id": "", "title": "无线蓝牙耳机", "category": "数码", "price": 89.0}

INV_FOR_CV = {
    "1": {"sku": "1", "product_name": "无线蓝牙耳机", "stock_qty": 200},
}
CR_FOR_CV = {
    "1": {"sku": "1", "product_name": "蓝牙耳机Pro", "current_price": 99.0},
}


class TestGetProductCrossView:
    def test_sku_match_both_tables(self):
        from app.services.cross_table import get_product_cross_view, clear_cache
        clear_cache()
        with patch("app.services.cross_table._fetch_inventory_records",
                   return_value=INV_FOR_CV):
            with patch("app.services.cross_table._fetch_crawled_products",
                       return_value=CR_FOR_CV):
                r = get_product_cross_view(PROD_MOCK_1)
        assert r["inventory"] is not None
        assert r["crawled"] is not None
        assert r["inventory"]["stock_qty"] == 200
        assert r["crawled"]["current_price"] == 99.0

    def test_no_match_at_all(self):
        from app.services.cross_table import get_product_cross_view, clear_cache
        clear_cache()
        with patch("app.services.cross_table._fetch_inventory_records",
                   return_value=INV_FOR_CV):
            with patch("app.services.cross_table._fetch_crawled_products",
                       return_value=CR_FOR_CV):
                r = get_product_cross_view(PROD_MOCK_2)
        assert r["inventory"] is None
        assert r["crawled"] is None
        assert r["derived"] == {}

    def test_output_structure_complete(self):
        from app.services.cross_table import get_product_cross_view, clear_cache
        clear_cache()
        with patch("app.services.cross_table._fetch_inventory_records",
                   return_value=INV_FOR_CV):
            with patch("app.services.cross_table._fetch_crawled_products",
                       return_value=CR_FOR_CV):
                r = get_product_cross_view(PROD_MOCK_1)
        for key in ["product_id", "title", "category", "master", "inventory", "crawled", "derived"]:
            assert key in r

    def test_master_is_original_product(self):
        from app.services.cross_table import get_product_cross_view, clear_cache
        clear_cache()
        with patch("app.services.cross_table._fetch_inventory_records",
                   return_value={}):
            with patch("app.services.cross_table._fetch_crawled_products",
                       return_value={}):
                r = get_product_cross_view(PROD_MOCK_1)
        assert r["master"] == PROD_MOCK_1

    def test_empty_product_id_uses_name_fallback(self):
        """无 product_id 时走名称模糊匹配降级"""
        from app.services.cross_table import get_product_cross_view, clear_cache
        clear_cache()
        with patch("app.services.cross_table._fetch_inventory_records",
                   return_value=INV_FOR_CV):
            with patch("app.services.cross_table._fetch_crawled_products",
                       return_value=CR_FOR_CV):
                r = get_product_cross_view(PROD_MOCK_NO_ID)
        # 名称匹配"无线蓝牙耳机"应该在库存表中找到
        assert r["inventory"] is not None
        assert r["inventory"]["stock_qty"] == 200
# Shared mock data for 1.5
MASTER_PRODUCT = {"product_id": 1, "title": "无线蓝牙耳机", "category": "数码", "price": 89.0, "cost": 55.0}
MASTER_PRODUCT_2 = {"product_id": 2, "title": "纯棉T恤", "category": "服饰", "price": 49.0, "cost": 20.0}
INVENTORY_RECORD = {"sku": "1", "stock_qty": 200, "warning_stock": 50, "cumulative_outbound": 1200}
CRAWLED_RECORD = {"sku": "1", "current_price": 99.0, "rating": 4.3, "sales": 420}
# ---- 1.5 衍生指标计算 + 全量批量 ----

class TestComputeDerivedMetrics:
    def test_full_data_all_metrics(self):
        from app.services.cross_table import compute_derived_metrics
        cv = {
            "master": {"price": 89.0, "cost": 55.0, "title": "耳机"},
            "inventory": {"stock_qty": 200, "warning_stock": 50, "cumulative_outbound": 1200},
            "crawled": {"current_price": 99.0},
            "derived": {},
        }
        r = compute_derived_metrics(cv)
        d = r["derived"]
        assert d["price_vs_market"] == -10.0
        assert d["price_vs_market_pct"] == -10.1
        assert d["stock_health"] == "充足"
        assert d["margin_pct"] == 38.2
        assert d["turnover_days"] == 5.0
        assert d["has_inventory_data"] is True
        assert d["has_crawled_data"] is True

    def test_higher_price_low_stock(self):
        from app.services.cross_table import compute_derived_metrics
        cv = {
            "master": {"price": 120.0, "cost": 80.0},
            "inventory": {"stock_qty": 5, "warning_stock": 30, "cumulative_outbound": 100},
            "crawled": {"current_price": 99.0},
            "derived": {},
        }
        d = compute_derived_metrics(cv)["derived"]
        assert d["price_vs_market"] == 21.0
        assert d["stock_health"] == "缺货"

    def test_no_external_data(self):
        from app.services.cross_table import compute_derived_metrics
        cv = {"master": {"price": 50.0, "cost": 30.0}, "inventory": None, "crawled": None, "derived": {}}
        d = compute_derived_metrics(cv)["derived"]
        assert d["price_vs_market"] is None
        assert d["stock_health"] == "未知"
        assert d["has_inventory_data"] is False
        assert d["has_crawled_data"] is False

    def test_empty_input(self):
        from app.services.cross_table import compute_derived_metrics
        assert compute_derived_metrics({}) == {}
        assert compute_derived_metrics(None) is None

    def test_zero_cost(self):
        from app.services.cross_table import compute_derived_metrics
        cv = {"master": {"price": 50.0, "cost": 0}, "inventory": None, "crawled": None, "derived": {}}
        d = compute_derived_metrics(cv)["derived"]
        assert d["margin_pct"] == 100.0

    def test_inventory_only(self):
        from app.services.cross_table import compute_derived_metrics
        cv = {
            "master": {"price": 89.0, "cost": 55.0},
            "inventory": {"stock_qty": 300, "warning_stock": 60, "cumulative_outbound": 100},
            "crawled": None, "derived": {},
        }
        d = compute_derived_metrics(cv)["derived"]
        assert d["stock_health"] == "充足"
        assert d["turnover_days"] == 90.0
        assert d["has_crawled_data"] is False


class TestGetAllCrossViews:
    def test_returns_list_of_cross_views(self):
        from app.services.cross_table import get_all_cross_views, clear_cache
        clear_cache()
        master = {"1": MASTER_PRODUCT, "2": MASTER_PRODUCT_2}
        inv = {"1": INVENTORY_RECORD}
        cr = {"1": CRAWLED_RECORD}
        with patch("app.services.cross_table._fetch_master_products", return_value=master):
            with patch("app.services.cross_table._fetch_inventory_records", return_value=inv):
                with patch("app.services.cross_table._fetch_crawled_products", return_value=cr):
                    results = get_all_cross_views()
        assert isinstance(results, list)
        assert len(results) == 2
        assert all("derived" in r for r in results)
        assert all("stock_health" in r["derived"] for r in results)

    def test_category_filter(self):
        from app.services.cross_table import get_all_cross_views, clear_cache
        clear_cache()
        master = {
            "1": {"product_id": 1, "title": "耳机", "category": "数码", "price": 89.0, "cost": 55.0},
            "2": {"product_id": 2, "title": "T恤", "category": "服饰", "price": 49.0, "cost": 20.0},
        }
        with patch("app.services.cross_table._fetch_master_products", return_value=master):
            with patch("app.services.cross_table._fetch_inventory_records", return_value={}):
                with patch("app.services.cross_table._fetch_crawled_products", return_value={}):
                    results = get_all_cross_views(category="数码")
        assert len(results) == 1
        assert results[0]["category"] == "数码"

    def test_empty_master_returns_empty_list(self):
        from app.services.cross_table import get_all_cross_views, clear_cache
        clear_cache()
        with patch("app.services.cross_table._fetch_master_products", return_value={}):
            results = get_all_cross_views()
        assert results == []