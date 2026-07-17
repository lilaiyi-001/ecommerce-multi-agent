"""统一信封格式规范（文档 5.2 节）"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field


class Envelope(BaseModel):
    """智能体间数据传递的统一信封格式"""
    from_agent: str = Field(..., description="发送方智能体名称")
    to_agent: str = Field(..., description="接收方智能体名称")
    session_id: str = Field(..., description="会话ID")
    timestamp: str = Field(..., description="发送时间 ISO8601")
    task_id: Optional[str] = Field(None, description="任务ID")


class ErrorPayload(BaseModel):
    """错误信息标准格式"""
    code: str = Field(..., description="错误码")
    message: str = Field(..., description="错误描述")
    fallback_used: bool = Field(False, description="是否使用了降级方案")
    fallback_description: Optional[str] = Field(None, description="降级方案说明")


def wrap_envelope(
    from_agent: str,
    to_agent: str,
    session_id: str,
    payload: dict,
    task_id: Optional[str] = None,
) -> dict:
    """将智能体输出包装为 Envelope 格式

    返回格式（文档 5.2）：
    {
        "envelope": { "from_agent": "...", "to_agent": "...", ... },
        "payload": { ... }
    }
    """
    return {
        "envelope": Envelope(
            from_agent=from_agent,
            to_agent=to_agent,
            session_id=session_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            task_id=task_id,
        ).model_dump(),
        "payload": payload,
    }
