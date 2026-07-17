"""意图识别 API 路由"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.intent import IntentInput, IntentOutput
from app.agents.agent_00_intent_recognizer.intent_recognizer import recognize_intent
from app.utils.auth import require_auth

router = APIRouter(dependencies=[Depends(require_auth)], prefix="/api/v1/intent", tags=["意图识别"])


@router.post("/recognize", response_model=IntentOutput)
def post_recognize_intent(input_data: IntentInput):
    """接收用户消息，返回结构化意图识别结果"""
    try:
        result = recognize_intent(input_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"意图识别失败: {str(e)}")
