"""补货/清仓建议智能体数据模型"""
from __future__ import annotations
from pydantic import BaseModel, Field


class InventoryInput(BaseModel):
    """补货/清仓输入"""
    product_id: int = Field(0, description="商品ID (0=自动选择)")
    product: dict = Field(default_factory=dict, description="商品信息 {title, current_stock, avg_daily_sales}")
    trend_info: dict = Field(default_factory=dict, description="趋势信息 {demand_trend}")
    context: dict = Field(default_factory=dict, description="上下文")


class InventoryOutput(BaseModel):
    """补货/清仓输出"""
    agent_name: str = Field(default="inventory_advice")
    product_id: int = Field(..., description="商品ID")
    advice: str = Field("", description="建议: 补货/清仓/维持")
    stockout_days: float = Field(0.0, description="库存可维持天数")
    suggested_quantity: int = Field(0, description="建议补货量/清仓量")
    urgency: str = Field("低", description="紧急程度: 高/中/低")
    reason: str = Field("", description="判断理由")
    for_downstream: dict = Field(default_factory=dict, description="给下游数据")
    for_display: str = Field("", description="展示文本")
