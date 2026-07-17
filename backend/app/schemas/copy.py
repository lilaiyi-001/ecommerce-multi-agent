"""营销文案智能体数据模型"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class CopyInput(BaseModel):
    """营销文案输入"""
    product_id: int = Field(0, description="商品ID (0=自动选择)")
    product: dict = Field(default_factory=dict, description="商品信息")
    pricing_info: dict = Field(default_factory=dict, description="定价信息")
    competitor_info: dict = Field(default_factory=dict, description="竞品信息")
    trend_info: dict = Field(default_factory=dict, description="趋势信息")
    user_profile: dict = Field(default_factory=dict, description="用户画像")
    context: dict = Field(default_factory=dict, description="上下文")


class CopyOutput(BaseModel):
    """营销文案输出"""
    agent_name: str = Field(default="marketing_copy")
    product_id: int = Field(..., description="商品ID")
    copy_text: str = Field("", description="生成的文案")
    highlights: list[str] = Field(default_factory=list, description="卖点列表")
    quality_check: dict = Field(default_factory=dict, description="质量检查结果")
    for_downstream: dict = Field(default_factory=dict, description="给下游数据")
    for_display: str = Field("", description="展示文本")
