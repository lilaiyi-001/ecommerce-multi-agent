"""竞品分析智能体 API 路由"""
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.competitor import CompetitorInput, CompetitorOutput
from app.agents.agent_04_competitor_analysis.competitor_analysis import analyze_competitor
from app.utils.auth import require_auth

router = APIRouter(dependencies=[Depends(require_auth)], prefix="/api/v1/competitor", tags=["竞品分析"])

@router.post("/analyze", response_model=CompetitorOutput)
def post_competitor(input_data: CompetitorInput):
    try:
        return analyze_competitor(input_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"竞品分析失败: {str(e)}")
