"""活动策划智能体数据模型"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class PromotionPlanInput(BaseModel):
    """活动策划输入"""
    recommended_products: list[dict] = Field(default_factory=list, description="推荐商品列表")
    pricing_info: dict = Field(default_factory=dict, description="定价信息")
    inventory_info: dict = Field(default_factory=dict, description="库存信息")
    user_profile: dict = Field(default_factory=dict, description="用户画像")
    context: dict = Field(default_factory=dict, description="上下文")


class PromotionActivity(BaseModel):
    """促销活动方案"""
    type: str = Field("", description="活动类型")
    discount: str = Field("", description="折扣力度")
    time_frame: str = Field("", description="活动周期")
    time_frame_days: int = Field(7, description="活动天数")
    target_products: list[int] = Field(default_factory=list, description="目标商品ID")
    target_products_desc: str = Field("", description="目标商品描述")
    estimated_sales_lift: str = Field("", description="预计销量提升")
    estimated_revenue_impact: str = Field("", description="预计收入影响")


class PromotionPlanOutput(BaseModel):
    """活动策划输出"""
    agent_name: str = Field(default="promotion_plan")
    plan: PromotionActivity = Field(default_factory=PromotionActivity, description="活动方案")
    strategy_summary: str = Field("", description="策略说明")
    for_downstream: dict = Field(default_factory=dict, description="给下游数据")
    for_display: str = Field("", description="展示文本")
