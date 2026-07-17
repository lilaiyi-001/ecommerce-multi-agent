"""营销文案智能体 API 路由"""
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.copy import CopyInput, CopyOutput
from app.agents.agent_07_marketing_copy.marketing_copy import generate_copy
from app.utils.auth import require_auth

router = APIRouter(dependencies=[Depends(require_auth)], prefix="/api/v1/copy", tags=["营销文案"])

@router.post("/generate", response_model=CopyOutput)
def post_copy(input_data: CopyInput):
    try:
        return generate_copy(input_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文案生成失败: {str(e)}")
