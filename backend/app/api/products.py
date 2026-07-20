"""产品列表 API"""
from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, Query
from app.services.feishu_data import get_feishu_products
from app.services.data_generator import get_demo_products
from app.utils.auth import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_auth)], prefix="/api/v1", tags=["产品"])


@router.get("/products")
def list_products(category: str = Query(default="", description="类目筛选，空=全部")):
    """获取可用产品列表（飞书优先，fallback 到模拟数据）"""
    try:
        products = get_feishu_products(category)
    except Exception as e:
        logger.warning(f"飞书数据拉取失败，回退模拟数据: {e}")
        products = []

    if not products:
        try:
            products = get_demo_products(category, count=40)
        except Exception as e:
            logger.error(f"模拟数据生成失败: {e}")
            return {"products": [], "total": 0}

    result = []
    for p in products:
        try:
            result.append({
                "product_id": p.get("product_id", 0),
                "title": p.get("title", ""),
                "price": p.get("current_price") or p.get("price", 0),
                "category": p.get("category", ""),
                "stock": p.get("current_stock", 0),
                "rating": p.get("rating_rate", 0),
                "image_url": p.get("image_url", ""),
            })
        except Exception:
            continue

    return {"products": result, "total": len(result)}
