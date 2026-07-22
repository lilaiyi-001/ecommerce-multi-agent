"""定价策略智能体数据模型"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class PriceRecommendation(BaseModel):
    suggested_min: float = Field(0.0, description="建议最低价")
    suggested_max: float = Field(0.0, description="建议最高价")
    suggested_best: float = Field(0.0, description="建议最优价")
    strategy: str = Field("", description="定价策略")
    reasoning: str = Field("", description="定价理由")
    risk_if_overprice: str = Field("", description="定价过高风险")
    risk_if_underprice: str = Field("", description="定价过低风险")


class PricingInput(BaseModel):
    product_id: int = Field(0, description="商品ID")
    product: dict = Field(default_factory=dict, description="商品信息")
    competitor_info: dict = Field(default_factory=dict, description="竞品信息")
    trend_info: dict = Field(default_factory=dict, description="趋势信息")
    user_profile: dict = Field(default_factory=dict, description="用户画像")
    assumed_cost_ratio: float = Field(0.6, ge=0.1, le=0.9, description="成本占比假设")
    context: dict = Field(default_factory=dict, description="上下文")


class PricingOutput(BaseModel):
    agent_name: str = Field(default="pricing_strategy")
    product_id: int = Field(0, description="商品ID")
    pricing_analysis: dict = Field(default_factory=dict, description="定价分析详情")
    recommendation: PriceRecommendation = Field(default_factory=PriceRecommendation)
    # --- 交叉对比增强 ---
    optimal_price_range: tuple[float, float] = Field(default=(0, 0), description="最优价格区间")
    max_discount: float = Field(0.0, description="最大可承受折扣")
    margin_analysis: str = Field("", description="利润率分析")
    for_downstream: dict = Field(default_factory=dict, description="给下游数据")
    for_display: str = Field("", description="展示文本")