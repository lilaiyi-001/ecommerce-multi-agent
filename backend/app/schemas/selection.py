"""选品分析智能体（Product Selection）数据模型"""
from __future__ import annotations
from typing import Optional, Any, List
from pydantic import BaseModel, Field


class ProductRank(BaseModel):
    """单个商品的爆款排名"""
    rank: int = Field(..., ge=1, description="排名")
    product_id: int = Field(..., description="商品ID")
    title: str = Field("", description="商品标题")
    price: float = Field(0.0, description="价格")
    rating_rate: float = Field(0.0, description="评分（1-5）")
    rating_count: int = Field(0, description="评论数")
    avg_daily_sales: float = Field(0.0, description="日均销量（模拟）")
    explosive_index: float = Field(0.0, description="爆款指数（0-100）")
    # --- 交叉对比指标 ---
    price_vs_market: Optional[float] = Field(None, description="vs 市场均价差（负=更便宜）")
    stock_health: str = Field("未知", description="库存健康度：充足/正常/预警/缺货/未知")
    margin_pct: Optional[float] = Field(None, description="利润率百分比")


class SelectionInput(BaseModel):
    """选品分析输入"""
    category: str = Field(..., description="类目名称")
    top_n: int = Field(default=5, ge=1, le=50, description="推荐商品数量")
    context: dict = Field(default_factory=dict, description="上下文")


class SelectionOutput(BaseModel):
    """选品分析输出"""
    agent_name: str = Field(default="product_selection")
    category: str = Field(..., description="分析类目")
    total_products: int = Field(0, description="该类目商品总数")
    price_distribution: dict = Field(default_factory=dict, description="价格带分布 {min, max, median, bands}")
    ranking: list[ProductRank] = Field(default_factory=list, description="爆款排行榜")
    cross_summary: str = Field("", description="交叉对比摘要（三表交叉数据概览）")
    for_downstream: dict = Field(default_factory=dict, description="给下游的数据")
    for_display: str = Field("", description="展示文本")