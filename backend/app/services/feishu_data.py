"""飞书 Bitable 数据适配器 — 多数据源支持

职责：
1. 商品主表（原有）— 40商品/8类目，供 Agent 02-07 使用
2. 库存表格（新增）— 实时库存/出入库数据，供 Agent 08 使用
3. 爬取商品数据（新增）— 竞品市场数据，供 Agent 04/06 使用

设计原则：
- 每个数据源使用独立的 App ID/Secret + Bitable Token/Table ID
- Token 按 app_id 维度缓存，互不干扰
- 任何失败均安全降级（返回空结果），调用方自行 fallback
- 所有网络调用带超时 + 指数退避重试

依赖：httpx（已在 requirements.txt 中）
"""
from __future__ import annotations
import logging
import time
from typing import Optional

from app.config import settings
from app.services.category_registry import normalize_category

logger = logging.getLogger(__name__)

_BASE = "https://open.feishu.cn"

# ================================================================
#  Token 管理
# ================================================================

# 商品主表 token 缓存（兼容旧代码）
_TOKEN_CACHE: dict = {"token": "", "expires_at": 0}

# 多 App token 缓存
_TOKEN_CACHE_MULTI: dict = {}  # app_id -> {"token": str, "expires_at": float}


def _get_tenant_access_token() -> str:
    """获取商品主表的 tenant_access_token（带 2 小时缓存）"""
    now = time.time()
    if _TOKEN_CACHE["token"] and now < _TOKEN_CACHE["expires_at"] - 60:
        return _TOKEN_CACHE["token"]
    app_id = settings.FEISHU_APP_ID
    app_secret = settings.FEISHU_APP_SECRET
    if not app_id or not app_secret:
        logger.warning("飞书 APP_ID 或 APP_SECRET 未配置")
        return ""
    import httpx
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                f"{_BASE}/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": app_id, "app_secret": app_secret},
            )
            data = resp.json()
            if data.get("code") == 0:
                _TOKEN_CACHE["token"] = data.get("tenant_access_token", "")
                _TOKEN_CACHE["expires_at"] = now + data.get("expire", 7200)
                logger.info("飞书 tenant_access_token 获取成功")
                return _TOKEN_CACHE["token"]
            logger.warning(f"飞书 token 获取失败: code={data.get('code')} msg={data.get('msg','')}")
            return ""
    except Exception as e:
        logger.warning(f"飞书 token 获取异常: {type(e).__name__}: {e}")
        return ""


def _get_token_for_app(app_id: str, app_secret: str, label: str = "") -> str:
    """获取指定应用的 tenant_access_token（带独立缓存）"""
    if not app_id or not app_secret:
        logger.warning(f"飞书 {label}: APP_ID 或 APP_SECRET 未配置")
        return ""
    now = time.time()
    entry = _TOKEN_CACHE_MULTI.get(app_id)
    if entry and entry.get("token") and now < entry.get("expires_at", 0) - 60:
        return entry["token"]
    import httpx
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                f"{_BASE}/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": app_id, "app_secret": app_secret},
            )
            data = resp.json()
            if data.get("code") == 0:
                _TOKEN_CACHE_MULTI[app_id] = {
                    "token": data.get("tenant_access_token", ""),
                    "expires_at": now + data.get("expire", 7200),
                }
                logger.info(f"飞书 {label} tenant_access_token 获取成功")
                return _TOKEN_CACHE_MULTI[app_id]["token"]
            logger.warning(f"飞书 {label} token 失败: code={data.get('code')}")
            return ""
    except Exception as e:
        logger.warning(f"飞书 {label} token 异常: {type(e).__name__}: {e}")
        return ""


def _list_records(
    app_token: str, table_id: str, access_token: str,
    page_size: int = 100, view_id: str = "", filter_formula: str = "",
) -> list[dict]:
    """从飞书 Bitable 拉取记录（支持分页 + 筛选），带自动重试"""
    if not access_token or not app_token or not table_id:
        return []
    import httpx
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    params: dict = {"page_size": page_size}
    if view_id:
        params["view_id"] = view_id
    if filter_formula:
        params["filter"] = filter_formula
    all_records: list[dict] = []
    page_token: Optional[str] = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=15) as client:
                while True:
                    if page_token:
                        params["page_token"] = page_token
                    resp = client.get(
                        f"{_BASE}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
                        headers=headers, params=params,
                    )
                    data = resp.json()
                    if data.get("code") != 0:
                        logger.warning(
                            f"飞书 Bitable 拉取失败 (尝试{attempt+1}/3): "
                            f"code={data.get('code')} msg={data.get('msg','')}"
                        )
                        break
                    items = data.get("data", {}).get("items", [])
                    all_records.extend(items)
                    if not data.get("data", {}).get("has_more"):
                        return all_records
                    page_token = data.get("data", {}).get("page_token")
            if all_records:
                return all_records
        except Exception as e:
            logger.warning(f"飞书 Bitable 拉取异常 (尝试{attempt+1}/3): {type(e).__name__}: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)
    logger.error("飞书 Bitable 拉取失败，已达最大重试次数")
    return all_records


# ================================================================
#  数值清洗工具
# ================================================================

def _clean_numeric(value) -> float:
    """安全浮点转换：处理 \xa5 / ￥ / , / % / 空值 / N/A"""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    for ch in ["\xa5", ",", "%", "\uffe5", " ", "\u5143"]:
        text = text.replace(ch, "")
    if not text or text in ("-", "--", "N/A"):
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _safe_int(value) -> int:
    return int(_clean_numeric(value))


# ================================================================
#  商品主表 (原有) — 40商品/8类目
# ================================================================

# 字段别名映射 — 兼容中英文表头
_FIELD_ALIASES: dict[str, list[str]] = {
    "product_id": ["商品ID", "product_id", "SKU编码", "SKU", "sku"],
    "title": ["商品名称", "title", "名称", "name"],
    "price": ["售价", "price", "价格", "现价", "current_price", "建议售价"],
    "rating_rate": ["评分", "rating_rate", "商品评分"],
    "rating_count": ["评论数", "rating_count", "review_count", "评价数"],
    "avg_daily_sales": ["日均销量", "avg_daily_sales", "销量", "sales", "累计销量"],
    "category": ["所属类目", "类目", "类别", "category"],
    "current_price": ["售价", "价格", "price", "current_price"],
    "current_stock": ["库存", "current_stock", "stock"],
    "cost_price": ["成本价", "cost_price"],
    "max_stock": ["最大库存", "max_stock"],
    "reorder_point": ["补货点", "reorder_point"],
    "safety_stock": ["安全库存", "safety_stock"],
    "seasonal_factor": ["季节系数", "seasonal_factor"],
    "growth_trend": ["增长趋势", "growth_trend"],
    "description": ["商品描述", "description", "描述"],
    "image_url": ["商品图片链接", "image_url", "图片链接", "图片"],
}


def _get_field(fields: dict, field_name: str, default=None):
    """按别名列表依次查找字段值"""
    aliases = _FIELD_ALIASES.get(field_name, [field_name])
    for alias in aliases:
        val = fields.get(alias)
        if val is not None:
            return val
    return default


def check_feishu_config() -> dict:
    """检查飞书配置完整性，返回状态字典"""
    checks = {
        "app_id": bool(settings.FEISHU_APP_ID),
        "app_secret": bool(settings.FEISHU_APP_SECRET),
        "bitable_token": bool(settings.FEISHU_BITABLE_APP_TOKEN),
        "table_id": bool(settings.FEISHU_BITABLE_TABLE_ID),
    }
    all_ok = all(checks.values())
    return {
        "configured": all_ok,
        "message": "飞书 Bitable 配置完整" if all_ok
        else f"缺少配置: {[k for k, v in checks.items() if not v]}",
        "checks": checks,
    }


def get_feishu_products(category: str = "") -> list[dict]:
    """从飞书 Bitable 拉取商品数据"""
    category = normalize_category(category)
    config_check = check_feishu_config()
    if not config_check["configured"]:
        logger.warning(f"get_feishu_products 跳过: {config_check['message']}")
        return []
    token = _get_tenant_access_token()
    if not token:
        logger.warning("get_feishu_products 跳过: 无法获取 token")
        return []
    app_token = settings.FEISHU_BITABLE_APP_TOKEN
    table_id = settings.FEISHU_BITABLE_TABLE_ID
    view_id = settings.FEISHU_BITABLE_VIEW_ID or ""
    filter_formula = ""
    if category:
        safe_cat = category.replace('"', '\\"')
        filter_formula = f'CurrentValue.[所属类目]="{safe_cat}"'
    records = _list_records(app_token, table_id, token, view_id=view_id, filter_formula=filter_formula)
    products = []
    for rec in records:
        fields = rec.get("fields", {})
        pid = _get_field(fields, "product_id", 0)
        if not pid:
            continue
        product = {
            "product_id": int(pid) if pid else 0,
            "title": _get_field(fields, "title", "") or "",
            "price": float(_get_field(fields, "price", 0) or 0),
            "rating_rate": float(_get_field(fields, "rating_rate", 0) or 0),
            "rating_count": int(_get_field(fields, "rating_count", 0) or 0),
            "avg_daily_sales": float(_get_field(fields, "avg_daily_sales", 0) or 0),
            "category": _get_field(fields, "category", category) or category,
            "current_price": float(_get_field(fields, "current_price", 0) or 0),
            "current_stock": int(_get_field(fields, "current_stock", 999) or 999),
            "cost_price": float(_get_field(fields, "cost_price", 0) or 0),
            "max_stock": int(_get_field(fields, "max_stock", 0) or 0),
            "reorder_point": int(_get_field(fields, "reorder_point", 0) or 0),
            "safety_stock": int(_get_field(fields, "safety_stock", 0) or 0),
            "seasonal_factor": float(_get_field(fields, "seasonal_factor", 1.0) or 1.0),
            "growth_trend": _get_field(fields, "growth_trend", "stable") or "stable",
            "description": _get_field(fields, "description", "") or "",
            "image_url": _get_field(fields, "image_url", "") or "",
            "_source": "feishu",
        }
        if product["current_price"] == 0 and product["price"] > 0:
            product["current_price"] = product["price"]
        products.append(product)
    seen = set()
    deduped = []
    for p in products:
        if p["product_id"] not in seen:
            seen.add(p["product_id"])
            deduped.append(p)
    logger.info(f"飞书拉取商品: {len(records)} 条记录 -> {len(deduped)} 个有效商品 (类目={category or '全部'})")
    return deduped


def get_feishu_sales_history(product_ids: list[int]) -> dict[int, list[float]]:
    """从飞书获取商品历史销量数据

    TODO: 飞书 Bitable 中尚无销量历史表结构，待对接后实现。
          当前返回空字典，调用方使用模拟数据。
    """
    return {}


def get_feishu_user_behavior(category: str = "") -> list[dict]:
    """从飞书获取用户行为数据

    TODO: 飞书 Bitable 中尚无用户行为表结构，待对接后实现。
          当前返回空列表，调用方使用模拟数据。
    """
    return []


# ================================================================
#  库存表格 (新增) — 实时库存/出入库数据 → Agent 08
# ================================================================

_INVENTORY_FIELD_ALIASES: dict[str, list[str]] = {
    "sku": ["SKU编码", "SKU", "sku", "商品SKU"],
    "product_name": ["商品名称", "商品名", "product_name", "名称"],
    "category": ["商品分类", "类别", "所属类目", "category"],
    "stock_quantity": ["库存数量", "库存", "stock_quantity", "当前库存"],
    "stock_amount": ["库存金额", "库存总金额", "stock_amount"],
    "selling_price": ["售价", "价格", "selling_price", "建议售价"],
    "warning_stock": ["预警库存", "预警", "warning_stock"],
    "stock_status": ["库存状态", "状态", "stock_status"],
    "last_entry_time": ["最近入库时间", "入库时间", "last_entry_time"],
    "cumulative_outbound": ["累计出库量", "出库量", "cumulative_outbound"],
    "cumulative_sales": ["累计销量", "销量", "cumulative_sales"],
    "product_rating": ["商品评分", "评分", "product_rating"],
    "description": ["商品描述", "描述", "description"],
    "image_url": ["商品图片链接", "图片链接", "image_url", "图片"],
}


def _inv_field(fields: dict, name: str, default=None):
    """按别名列表查找库存表格字段"""
    for alias in _INVENTORY_FIELD_ALIASES.get(name, [name]):
        val = fields.get(alias)
        if val is not None:
            return val
    return default


def get_feishu_inventory(category: str = "") -> list[dict]:
    """从飞书库存表格拉取实时库存数据 → Agent 08 补货/清仓建议

    失败时返回空列表，调用方使用模拟数据 fallback。
    """
    app_id = settings.FEISHU_INVENTORY_APP_ID
    app_secret = settings.FEISHU_INVENTORY_APP_SECRET
    app_token = settings.FEISHU_INVENTORY_BITABLE_APP_TOKEN
    table_id = settings.FEISHU_INVENTORY_TABLE_ID
    view_id = settings.FEISHU_INVENTORY_VIEW_ID or ""

    if not app_token or not table_id:
        logger.warning("get_feishu_inventory 跳过: Bitable 未配置")
        return []

    token = _get_token_for_app(app_id, app_secret, label="库存表格")
    if not token:
        logger.warning("get_feishu_inventory 跳过: 无法获取 token")
        return []

    records = _list_records(
        app_token, table_id, token, view_id=view_id,
    )

    results: list[dict] = []
    for rec in records:
        fields = rec.get("fields", {})
        sku = _inv_field(fields, "sku", "")
        if not sku:
            continue

        item_category = normalize_category(_inv_field(fields, "category", "") or "")
        if category and item_category != category:
            continue

        results.append({
            "sku": str(sku),
            "product_name": _inv_field(fields, "product_name", "") or "",
            "category": normalize_category(_inv_field(fields, "category", "") or ""),
            "stock_quantity": _safe_int(_inv_field(fields, "stock_quantity", 0)),
            "stock_amount": _clean_numeric(_inv_field(fields, "stock_amount", 0)),
            "selling_price": _clean_numeric(_inv_field(fields, "selling_price", 0)),
            "warning_stock": _safe_int(_inv_field(fields, "warning_stock", 0)),
            "stock_status": _inv_field(fields, "stock_status", "正常") or "正常",
            "last_entry_time": _inv_field(fields, "last_entry_time", "") or "",
            "cumulative_outbound": _safe_int(_inv_field(fields, "cumulative_outbound", 0)),
            "cumulative_sales": _safe_int(_inv_field(fields, "cumulative_sales", 0)),
            "product_rating": _clean_numeric(_inv_field(fields, "product_rating", 0)),
            "description": _inv_field(fields, "description", "") or "",
            "image_url": _inv_field(fields, "image_url", "") or "",
            "_source": "feishu_inventory",
        })

    logger.info(
        f"飞书库存拉取: {len(records)} 条记录 -> "
        f"{len(results)} 个有效商品 (类目={category or '全部'})"
    )
    return results


# ================================================================
#  爬取商品数据 (新增) — 竞品市场数据 → Agent 04/06
# ================================================================

_CRAWLED_FIELD_ALIASES: dict[str, list[str]] = {
    "sku": ["SKU", "sku", "商品SKU", "SKU编码"],
    "product_name": ["商品名称", "商品名", "product_name", "名称"],
    "category": ["类别", "商品分类", "所属类目", "category"],
    "original_price": ["原价", "original_price", "市场价"],
    "current_price": ["现价", "current_price", "售价", "价格"],
    "description": ["描述", "商品描述", "description"],
    "image_url": ["图片链接", "商品图片链接", "image_url", "图片"],
    "rating": ["评分", "商品评分", "rating"],
    "sales": ["销量", "月销量", "sales"],
}


def _cr_field(fields: dict, name: str, default=None):
    """按别名列表查找爬取表格字段"""
    for alias in _CRAWLED_FIELD_ALIASES.get(name, [name]):
        val = fields.get(alias)
        if val is not None:
            return val
    return default


def get_feishu_crawled_products(category: str = "") -> list[dict]:
    """从飞书爬取商品表格拉取竞品市场数据 → Agent 04/06

    用于竞品分析和定价策略，提供市场对标数据。
    失败时返回空列表，调用方使用模拟数据 fallback。
    """
    app_id = settings.FEISHU_CRAWLED_APP_ID
    app_secret = settings.FEISHU_CRAWLED_APP_SECRET
    app_token = settings.FEISHU_CRAWLED_BITABLE_APP_TOKEN
    table_id = settings.FEISHU_CRAWLED_TABLE_ID
    view_id = settings.FEISHU_CRAWLED_VIEW_ID or ""

    if not app_token or not table_id:
        logger.warning("get_feishu_crawled_products 跳过: Bitable 未配置")
        return []

    token = _get_token_for_app(app_id, app_secret, label="爬取数据表格")
    if not token:
        logger.warning("get_feishu_crawled_products 跳过: 无法获取 token")
        return []

    records = _list_records(
        app_token, table_id, token, view_id=view_id,
    )

    results: list[dict] = []
    seen_skus: set = set()
    for rec in records:
        fields = rec.get("fields", {})
        sku = _cr_field(fields, "sku", "")
        if not sku or str(sku) in seen_skus:
            continue
        seen_skus.add(str(sku))

        item_category = normalize_category(_cr_field(fields, "category", "") or "")
        if category and item_category != category:
            continue

        original = _clean_numeric(_cr_field(fields, "original_price", 0))
        current = _clean_numeric(_cr_field(fields, "current_price", 0))
        discount_rate = round((original - current) / original, 3) if original > 0 else 0.0

        results.append({
            "sku": str(sku),
            "product_name": _cr_field(fields, "product_name", "") or "",
            "category": normalize_category(_cr_field(fields, "category", "") or ""),
            "original_price": original,
            "current_price": current if current > 0 else original,
            "discount_rate": discount_rate,
            "description": _cr_field(fields, "description", "") or "",
            "image_url": _cr_field(fields, "image_url", "") or "",
            "rating": _clean_numeric(_cr_field(fields, "rating", 0)),
            "sales": _safe_int(_cr_field(fields, "sales", 0)),
            "_source": "feishu_crawled",
        })

    logger.info(
        f"飞书爬取数据拉取: {len(records)} 条记录 -> "
        f"{len(results)} 个有效商品 (类别={category or '全部'})"
    )
    return results
