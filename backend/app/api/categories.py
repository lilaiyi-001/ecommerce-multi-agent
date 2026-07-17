"""类目统计 API"""
from fastapi import APIRouter, Depends
from app.utils.auth import require_auth
from app.services.data_generator import PRODUCT_TEMPLATES
from app.services.category_registry import get_standard_categories

router = APIRouter(prefix="/api/v1/categories", tags=["categories"])


@router.get("")
async def list_categories(user=Depends(require_auth)):
    """返回所有类目及其模拟商品数量"""
    standard = set(get_standard_categories())
    return {
        "categories": [
            {"name": cat, "product_count": len(templates)}
            for cat, templates in PRODUCT_TEMPLATES.items()
            if cat in standard
        ]
    }
