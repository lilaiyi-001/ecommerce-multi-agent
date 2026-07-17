"""用户画像智能体 API 路由"""
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.profile import ProfileInput, ProfileOutput
from app.agents.agent_05_user_profile.user_profile import analyze_profile
from app.utils.auth import require_auth

router = APIRouter(dependencies=[Depends(require_auth)], prefix="/api/v1/profile", tags=["用户画像"])

@router.post("/analyze", response_model=ProfileOutput)
def post_profile(input_data: ProfileInput):
    try:
        return analyze_profile(input_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"用户画像分析失败: {str(e)}")
