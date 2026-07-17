"""选品分析智能体 API 路由"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.selection import SelectionInput, SelectionOutput
from app.agents.agent_02_product_selection.product_selection import analyze_products
from app.utils.auth import require_auth

router = APIRouter(dependencies=[Depends(require_auth)], prefix="/api/v1/selection", tags=["选品分析"])


@router.post("/analyze", response_model=SelectionOutput)
def post_analyze(input_data: SelectionInput):
    """选品分析：给定类目和数量，返回爆款排行榜"""
    try:
        result = analyze_products(input_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"选品分析失败: {str(e)}")
