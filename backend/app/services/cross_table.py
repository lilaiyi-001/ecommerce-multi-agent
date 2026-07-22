"""三表交叉对比引擎 — 统一数据访问层

职责：
1. 一次性拉取商品主表、库存表、爬取表，做内存缓存
2. 按 product_id / SKU / 商品名称 在三表间匹配
3. 计算衍生指标（价格差、库存健康度、利润率等）

设计原则：
- 所有 fetch 函数带 5 分钟内存缓存，避免重复调飞书 API
- 任何拉取失败安全降级（返回空 dict），不阻断下游
- 匹配策略：SKU 精准匹配 → 商品名称模糊匹配（降级）
"""
from __future__ import annotations
import logging
import time
from typing import Optional

from app.services.feishu_data import (
    get_feishu_products,
    get_feishu_inventory,
    get_feishu_crawled_products,
)

logger = logging.getLogger(__name__)

# ---- 缓存 ----
_cache: dict = {
    "master": {"data": None, "ts": 0},
    "inventory": {"data": None, "ts": 0},
    "crawled": {"data": None, "ts": 0},
}
_CACHE_TTL = 300  # 5 分钟


def _is_cache_valid(key: str) -> bool:
    entry = _cache.get(key)
    if not entry or entry["data"] is None:
        return False
    return (time.time() - entry["ts"]) < _CACHE_TTL


# ================================================================
#  1. 三表全量拉取（带缓存）
# ================================================================

def _fetch_master_products() -> dict:
    """拉取商品主表，返回 {product_id: {...}} 字典。
    失败返回空 dict，不抛异常。"""
    cache_key = "master"
    if _is_cache_valid(cache_key):
        logger.debug("商品主表命中缓存，%d 条记录", len(_cache[cache_key]["data"]))
        return _cache[cache_key]["data"]

    try:
        products = get_feishu_products()
        if not products:
            logger.warning("商品主表拉取为空")
            return {}
        result = {}
        for p in products:
            pid = p.get("product_id")
            if pid is not None:
                result[str(pid)] = p
        _cache[cache_key] = {"data": result, "ts": time.time()}
        logger.info("商品主表拉取成功: %d 条记录", len(result))
        return result
    except Exception as e:
        logger.warning("商品主表拉取失败: %s", e)
        return {}


def _fetch_inventory_records() -> dict:
    """拉取库存表，返回 {sku: {...}} 字典。
    失败返回空 dict。"""
    cache_key = "inventory"
    if _is_cache_valid(cache_key):
        logger.debug("库存表命中缓存，%d 条记录", len(_cache[cache_key]["data"]))
        return _cache[cache_key]["data"]

    try:
        records = get_feishu_inventory()
        if not records:
            logger.warning("库存表拉取为空")
            return {}
        result = {}
        for r in records:
            sku = r.get("sku", "")
            if sku:
                result[str(sku)] = r
        _cache[cache_key] = {"data": result, "ts": time.time()}
        logger.info("库存表拉取成功: %d 条记录", len(result))
        return result
    except Exception as e:
        logger.warning("库存表拉取失败: %s", e)
        return {}


def _fetch_crawled_products() -> dict:
    """拉取爬取商品表，返回 {sku: {...}} 字典。
    失败返回空 dict。"""
    cache_key = "crawled"
    if _is_cache_valid(cache_key):
        logger.debug("爬取表命中缓存，%d 条记录", len(_cache[cache_key]["data"]))
        return _cache[cache_key]["data"]

    try:
        records = get_feishu_crawled_products()
        if not records:
            logger.warning("爬取表拉取为空")
            return {}
        result = {}
        for r in records:
            sku = r.get("sku", "")
            if sku:
                result[str(sku)] = r
        _cache[cache_key] = {"data": result, "ts": time.time()}
        logger.info("爬取表拉取成功: %d 条记录", len(result))
        return result
    except Exception as e:
        logger.warning("爬取表拉取失败: %s", e)
        return {}


def clear_cache():
    """清除所有缓存（供测试使用）"""
    for key in _cache:
        _cache[key] = {"data": None, "ts": 0}
    logger.debug("cross_table 缓存已清除")
# ================================================================
#  2. SKU 精准匹配器
# ================================================================

def match_by_sku(sku: str) -> dict:
    """按 SKU 精准匹配库存表和爬取表。

    Args:
        sku: SKU 编码（字符串）

    Returns:
        字典，inventory 和 crawled 字段各为 dict 或 None。
        两张表都无匹配时两个字段均为 None。
    """
    if not sku:
        return {"inventory": None, "crawled": None}

    sku_key = str(sku)

    inventory = _fetch_inventory_records()
    crawled = _fetch_crawled_products()

    result = {
        "inventory": inventory.get(sku_key),
        "crawled": crawled.get(sku_key),
    }
    return result
# ================================================================
#  3. 商品名称模糊匹配器（SKU 不匹配时的降级策略）
# ================================================================

import difflib

_NAME_MATCH_THRESHOLD = 0.6


def _best_name_match(name: str, records: dict) -> dict | None:
    """在 records 字典中按商品名称模糊匹配，返回最佳匹配记录或 None。

    records 格式：{key: {"product_name": str, ...}, ...}
    """
    if not name or not records:
        return None

    best_score = 0.0
    best_record = None

    for key, record in records.items():
        candidate = record.get("product_name", "") or record.get("title", "") or ""
        if not candidate:
            continue
        score = difflib.SequenceMatcher(None, name, candidate).ratio()
        if score > best_score:
            best_score = score
            best_record = record

    if best_score >= _NAME_MATCH_THRESHOLD and best_record is not None:
        logger.debug(
            "名称模糊匹配成功: '%s' -> '%s' (score=%.2f)",
            name, best_record.get("product_name", "?"), best_score
        )
        return best_record

    logger.debug("名称模糊匹配无结果: '%s' (best_score=%.2f)", name, best_score)
    return None


def match_by_name(name: str) -> dict:
    """按商品名称模糊匹配库存表和爬取表。

    当 SKU 精确匹配失败时，使用此函数作为降级策略。
    在库存表和爬取表中分别做 difflib.SequenceMatcher 匹配（阈值 0.6）。

    Args:
        name: 商品名称

    Returns:
        {"inventory": {...} | None, "crawled": {...} | None}
    """
    if not name:
        return {"inventory": None, "crawled": None}

    inventory = _fetch_inventory_records()
    crawled = _fetch_crawled_products()

    return {
        "inventory": _best_name_match(name, inventory),
        "crawled": _best_name_match(name, crawled),
    }
# ================================================================
#  4. 统一交叉视图入口
# ================================================================

def get_product_cross_view(product: dict) -> dict:
    """获取单个商品的完整交叉视图。

    输入主表商品记录，按 SKU 精准匹配库存表和爬取表，
    SKU 无匹配时降级为商品名称模糊匹配。

    Args:
        product: 主表商品 dict，必须含 product_id 和 title 字段

    Returns:
        {
            "product_id": int | str,
            "title": str,
            "category": str,
            "master": {...},       # 原始主表商品数据
            "inventory": {...} | None,  # 库存表匹配结果
            "crawled": {...} | None,    # 爬取表匹配结果
            "derived": {}               # 衍生指标（由 compute_derived_metrics 填充）
        }
    """
    product_id = product.get("product_id", "")
    title = product.get("title", "")
    category = product.get("category", "")

    # Step 1: SKU 精准匹配
    if product_id:
        sku_match = match_by_sku(str(product_id))
        inv = sku_match.get("inventory")
        cr = sku_match.get("crawled")
    else:
        inv = None
        cr = None

    # Step 2: SKU 无匹配时降级为名称模糊匹配
    if inv is None and cr is None and title:
        name_match = match_by_name(title)
        inv = name_match.get("inventory")
        cr = name_match.get("crawled")

    # Step 3: 部分匹配补充（SKU 匹配到一张表但另一张表无数据时）
    if inv is None and title and cr is not None:
        name_match_inv = match_by_name(title)
        if name_match_inv.get("inventory"):
            inv = name_match_inv["inventory"]
    if cr is None and title and inv is not None:
        name_match_cr = match_by_name(title)
        if name_match_cr.get("crawled"):
            cr = name_match_cr["crawled"]

    result = {
        "product_id": product_id,
        "title": title,
        "category": category,
        "master": product,
        "inventory": inv,
        "crawled": cr,
        "derived": {},
    }

    match_parts = []
    if inv: match_parts.append("库存")
    if cr: match_parts.append("爬取")
    logger.debug(
        "cross_view: product_id=%s title=%s -> %s",
        product_id, title[:20] if title else "?", "+".join(match_parts) or "无匹配"
    )
    return result
# ================================================================
#  5. 衍生指标计算
# ================================================================

def compute_derived_metrics(cross_view: dict) -> dict:
    """计算交叉视图的衍生指标，直接修改 cross_view["derived"]。

    计算的指标：
    - price_vs_market: 主表售价 - 爬取表市场均价（正数=我方更贵）
    - price_vs_market_pct: 价差百分比
    - stock_health: 库存健康度标签（充足/正常/预警/缺货/未知）
    - stock_health_ratio: 库存数量 / 预警库存（<1 表示低于预警线）
    - margin: 利润率 (售价 - 成本) / 售价
    - margin_pct: 利润率百分比
    - turnover_days: 库存周转天数（>90 表示滞销风险）
    - has_inventory_data: bool，是否有库存表数据
    - has_crawled_data: bool，是否有爬取表数据
    """
    if not cross_view:
        return cross_view

    master = cross_view.get("master", {})
    inventory = cross_view.get("inventory")
    crawled = cross_view.get("crawled")
    derived: dict = {}

    # --- 价格差 ---
    my_price = master.get("price", 0) or master.get("current_price", 0)
    market_price = None
    if crawled:
        market_price = crawled.get("current_price") or crawled.get("original_price")

    if my_price and market_price and market_price > 0:
        derived["price_vs_market"] = round(my_price - market_price, 2)
        derived["price_vs_market_pct"] = round((my_price - market_price) / market_price * 100, 1)
    else:
        derived["price_vs_market"] = None
        derived["price_vs_market_pct"] = None

    # --- 库存健康度 ---
    if inventory:
        stock_qty = inventory.get("stock_qty", 0)
        warning = inventory.get("warning_stock", 0)
        derived["has_inventory_data"] = True
        if warning and warning > 0:
            ratio = stock_qty / warning
            derived["stock_health_ratio"] = round(ratio, 2)
            if ratio >= 2.0:
                derived["stock_health"] = "充足"
            elif ratio >= 1.0:
                derived["stock_health"] = "正常"
            elif ratio >= 0.5:
                derived["stock_health"] = "预警"
            else:
                derived["stock_health"] = "缺货"
        else:
            derived["stock_health_ratio"] = None
            derived["stock_health"] = "正常" if stock_qty > 0 else "缺货"
    else:
        derived["has_inventory_data"] = False
        derived["stock_health"] = "未知"
        derived["stock_health_ratio"] = None

    # --- 利润率 ---
    cost = master.get("cost", 0)
    if my_price and my_price > 0 and cost is not None:
        derived["margin"] = round((my_price - cost) / my_price, 4)
        derived["margin_pct"] = round((my_price - cost) / my_price * 100, 1)
    else:
        derived["margin"] = None
        derived["margin_pct"] = None

    # --- 周转天数 ---
    if inventory:
        outbound = inventory.get("cumulative_outbound", 0)
        stock_qty = inventory.get("stock_qty", 0)
        if outbound and outbound > 0:
            daily_avg = outbound / 30  # 按30天估算日均出库
            if daily_avg > 0:
                derived["turnover_days"] = round(stock_qty / daily_avg, 1)
                derived["turnover_risk"] = "滞销" if derived["turnover_days"] > 90 else "正常"
            else:
                derived["turnover_days"] = None
                derived["turnover_risk"] = "未知"
        else:
            derived["turnover_days"] = None
            derived["turnover_risk"] = "未知"
    else:
        derived["turnover_days"] = None
        derived["turnover_risk"] = "未知"

    # --- 数据可用性 ---
    derived["has_crawled_data"] = crawled is not None

    cross_view["derived"] = derived
    return cross_view


# ================================================================
#  6. 全量批量接口
# ================================================================

def get_all_cross_views(category: str = "") -> list[dict]:
    """获取全量（或指定类目）商品的交叉视图。

    一次性拉取三表数据，对每个主表商品执行 get_product_cross_view
    并计算衍生指标。

    Args:
        category: 类目筛选，空字符串表示全量

    Returns:
        交叉视图列表，每个元素是 get_product_cross_view 的输出
    """
    master = _fetch_master_products()
    if not master:
        logger.warning("get_all_cross_views: 主表数据为空")
        return []

    results: list[dict] = []
    for pid, product in master.items():
        if category and product.get("category", "") != category:
            continue
        cv = get_product_cross_view(product)
        compute_derived_metrics(cv)
        results.append(cv)

    logger.info(
        "get_all_cross_views: category=%s -> %d 个商品交叉视图",
        category or "全量", len(results)
    )
    return results