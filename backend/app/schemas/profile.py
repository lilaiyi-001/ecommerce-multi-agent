"""用户画像智能体数据模型"""
from __future__ import annotations
from typing import Optional, Any
from pydantic import BaseModel, Field


class PricePreference(BaseModel):
    """价格偏好"""
    most_viewed_price_band: str = Field("", description="最高浏览的价格区间")
    avg_order_price: float = Field(0.0, description="平均订单价")
    price_sensitivity: str = Field("中等", description="价格敏感度 高/中/低")


class BehaviorFunnel(BaseModel):
    """行为转化漏斗"""
    view_count: int = Field(0, description="浏览数")
    cart_count: int = Field(0, description="加购数")
    purchase_count: int = Field(0, description="购买数")
    view_to_cart_rate: str = Field("0%", description="浏览→加购转化率")
    cart_to_purchase_rate: str = Field("0%", description="加购→购买转化率")


class ProfileInput(BaseModel):
    """用户画像输入"""
    category: str = Field(..., description="类目名称")
    context: dict = Field(default_factory=dict, description="上下文")


class ProfileOutput(BaseModel):
    """用户画像输出"""
    agent_name: str = Field(default="user_profile")
    category: str = Field("", description="分析类目")
    total_users: int = Field(0, description="覆盖用户数")
    total_behavior_records: int = Field(0, description="行为记录总数")
    profile: dict = Field(default_factory=dict, description="用户画像详情")
    # --- 交叉数据指标 ---
    purchase_power: str = Field("中等", description="购买力：高/中/低")
    category_preference: dict = Field(default_factory=dict, description="类目偏好分布")
    data_sources_used: list[str] = Field(default_factory=list, description="使用了哪些数据源")
    for_downstream: dict = Field(default_factory=dict, description="给下游数据")
    for_display: str = Field("", description="展示文本")