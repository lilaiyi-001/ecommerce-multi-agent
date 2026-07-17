"""飞书 Bitable 数据适配器

职责：
1. 自动获取 tenant_access_token（无需用户 OAuth）
2. 从飞书 Bitable 拉取商品/用户行为/销量数据
3. 任何失败均安全降级（返回空结果），调用方自行 fallback

飞书权限：仅在 agent_02/03/04/05 中调用
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

# Token 缓存
_TOKEN_CACHE: dict = {"token": "", "expires_at": 0}


def _get_tenant_access_token() -> str:
    """获取应用级别的 tenant_access_token（带2小时缓存）"""
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
                token = data.get("tenant_access_token", "")
                expire = data.get("expire", 7200)
                _TOKEN_CACHE["token"] = token
                _TOKEN_CACHE["expires_at"] = now + expire
                logger.info("飞书 tenant_access_token 获取成功")
                return token
            logger.warning(f"飞书 token 获取失败: code={data.get('code')} msg={data.get('msg','')}")
            return ""
    except Exception as e:
        logger.warning(f"飞书 token 获取异常: {type(e).__name__}: {e}")
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
    max_retries = 3

    for attempt in range(max_retries):
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
                            f"飞书 Bitable 拉取失败 (尝试{attempt+1}/{max_retries}): "
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
            logger.warning(
                f"飞书 Bitable 拉取异常 (尝试{attempt+1}/{max_retries}): {type(e).__name__}: {e}"
            )
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.info(f"等待 {wait}s 后重试...")
                time.sleep(wait)
            else:
                logger.error(f"飞书 Bitable 拉取失败，已达最大重试次数")
    return all_records


def check_feishu_config() -> dict:
    """检查飞书配置完整性，返回状态字典"""
    checks = {
        "app_id": bool(settings.FEISHU_APP_ID),
        "app_secret": bool(settings.FEISHU_APP_SECRET),
        "bitable_token": bool(settings.FEISHU_BITABLE_APP_TOKEN),
        "table_id": bool(settings.FEISHU_BITABLE_TABLE_ID),
    }
    missing = [k for k, v in checks.items() if not v]
    return {
        "configured": len(missing) == 0,
        "checks": checks,
        "missing": missing,
        "message": "飞书配置完整" if len(missing) == 0 else f"缺少配置项: {', '.join(missing)}",
    }


_FIELD_ALIASES = {
    "product_id": ["商品ID", "product_id", "ID"],
    "title": ["商品名称", "title", "名称"],
    "price": ["售价", "价格", "price"],
    "rating_rate": ["评分", "rating_rate"],
    "rating_count": ["评论数", "rating_count"],
    "avg_daily_sales": ["日均销量", "avg_daily_sales"],
    "category": ["所属类目", "类目", "category"],
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


def get_feishu_products(category: str = "") -> list[dict]:
    """从飞书 Bitable 拉取商品数据"""
    category = normalize_category(category)
    config_check = check_feishu_config()
    if not config_check["configured"]:
        logger.warning(f"get_feishu_products 跳过: {config_check['message']}")
        return []

    token = _get_tenant_access_token()
    if not token:
        logger.warning("get_feishu_products 跳过: 无法获取飞书 token")
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
