"""报告相关数据模型"""
from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field

VALID_ACTIVITY_TYPES = {"double11", "618", "new_product", "clearance", "daily"}


class ReportGenerateInput(BaseModel):
    """生成报告请求"""
    product_ids: list[str] = Field(..., min_length=1, description="选择的商品ID列表，至少1个")
    activity_type: str = Field(..., description="活动类型：double11/618/new_product/clearance/daily")
    session_id: str = Field(..., description="会话ID，用于关联对话历史")

    model_config = {
        "json_schema_extra": {
            "example": {
                "product_ids": ["1", "2"],
                "activity_type": "double11",
                "session_id": "sess_abc123",
            }
        }
    }


class ReportSummary(BaseModel):
    """报告列表摘要（不含完整内容）"""
    id: str
    session_id: str
    product_count: int
    activity_type: str
    category: Optional[str] = None
    summary: Optional[str] = None
    created_at: str


class ReportDetail(BaseModel):
    """报告详情（含完整内容）"""
    id: str
    session_id: str
    product_ids: list[str]
    activity_type: str
    category: Optional[str] = None
    summary: Optional[str] = None
    report_content: dict
    created_at: str


class ReportHistoryResponse(BaseModel):
    """历史报告列表响应"""
    reports: list[ReportSummary]
    total: int
