"""活动策划智能体 API 路由"""
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.promotion import PromotionPlanInput, PromotionPlanOutput
from app.agents.agent_09_promotion_plan.promotion_plan import create_plan
from app.utils.auth import require_auth

router = APIRouter(dependencies=[Depends(require_auth)], prefix="/api/v1/promotion", tags=["活动策划"])

@router.post("/plan", response_model=PromotionPlanOutput)
def post_promotion(input_data: PromotionPlanInput):
    try:
        return create_plan(input_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"活动策划失败: {str(e)}")
