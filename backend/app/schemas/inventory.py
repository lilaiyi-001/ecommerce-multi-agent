"""补货/清仓建议智能体数据模型"""
from __future__ import annotations
from pydantic import BaseModel, Field


class InventoryInput(BaseModel):
    product_id: int = Field(0, description="商品ID")
    product: dict = Field(default_factory=dict, description="商品信息")
    trend_info: dict = Field(default_factory=dict, description="趋势信息")
    context: dict = Field(default_factory=dict, description="上下文")


class InventoryOutput(BaseModel):
    agent_name: str = Field(default="inventory_advice")
    product_id: int = Field(..., description="商品ID")
    advice: str = Field("", description="建议: 补货/清仓/维持")
    stockout_days: float = Field(0.0, description="库存可维持天数")
    suggested_quantity: int = Field(0, description="建议补货量/清仓量")
    urgency: str = Field("低", description="紧急程度 高/中/低")
    reason: str = Field("", description="判断理由")
    # --- 交叉对比增强 ---
    suggested_restock_qty: int = Field(0, description="建议补货量（来自库存表真实数据）")
    days_until_stockout: float = Field(0.0, description="按真实出库速度计算的断货天数")
    clearance_urgency: str = Field("正常", description="清仓紧迫度：紧急/建议/正常")
    restock_reason: str = Field("", description="补货/清仓详细理由")
    for_downstream: dict = Field(default_factory=dict, description="给下游数据")
    for_display: str = Field("", description="展示文本")