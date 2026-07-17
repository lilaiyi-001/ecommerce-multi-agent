"""趋势预测智能体 API 路由"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.trend import TrendInput, TrendOutput
from app.agents.agent_03_trend_forecast.trend_forecast import forecast
from app.utils.auth import require_auth

router = APIRouter(dependencies=[Depends(require_auth)], prefix="/api/v1/trend", tags=["趋势预测"])


@router.post("/forecast", response_model=TrendOutput)
def post_forecast(input_data: TrendInput):
    """趋势预测：给定商品ID列表，返回多算法融合的销量预测"""
    try:
        result = forecast(input_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"趋势预测失败: {str(e)}")
