"""定价策略智能体 API 路由"""
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.pricing import PricingInput, PricingOutput
from app.agents.agent_06_pricing_strategy.pricing_strategy import analyze_pricing
from app.utils.auth import require_auth

router = APIRouter(dependencies=[Depends(require_auth)], prefix="/api/v1/pricing", tags=["定价策略"])

@router.post("/analyze", response_model=PricingOutput)
def post_pricing(input_data: PricingInput):
    try:
        return analyze_pricing(input_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"定价分析失败: {str(e)}")
