"""竞品分析智能体数据模型"""
from __future__ import annotations
from typing import Optional, Any
from pydantic import BaseModel, Field


class CompetitorInfo(BaseModel):
    product_id: int = Field(..., description="商品ID")
    title: str = Field("", description="商品标题")
    price: float = Field(0.0, description="价格")
    rating_rate: float = Field(0.0, description="评分")
    rating_count: int = Field(0, description="评论数")
    avg_daily_sales: float = Field(0.0, description="日均销量")


class CompetitionAssessment(BaseModel):
    price_position: str = Field("", description="价格定位")
    rating_position: str = Field("", description="评分定位")
    sales_position: str = Field("", description="销量定位")
    overall_score: float = Field(0.0, ge=0, le=100, description="综合得分")
    verdict: str = Field("", description="综合评语")
    strengths: list[str] = Field(default_factory=list, description="优势")
    weaknesses: list[str] = Field(default_factory=list, description="劣势")


class CompetitorInput(BaseModel):
    target_product_id: int = Field(0, description="目标商品ID")
    target_product: dict = Field(default_factory=dict, description="目标商品信息")
    category_products: list[dict] = Field(default_factory=list, description="同类目商品列表")
    category: str = Field("", description="类目")
    context: dict = Field(default_factory=dict, description="上下文")


class CompetitorOutput(BaseModel):
    agent_name: str = Field(default="competitor_analysis")
    target_product_id: int = Field(..., description="目标商品ID")
    target_product_title: str = Field("", description="目标商品标题")
    competitors: list[CompetitorInfo] = Field(default_factory=list, description="竞品列表")
    competition_assessment: CompetitionAssessment = Field(default_factory=CompetitionAssessment)
    # --- 交叉对比增强 ---
    comparison_table: list[dict] = Field(default_factory=list, description="逐商品 vs 市场均值对比表")
    competitive_edge: str = Field("", description="差异化优势分析")
    for_downstream: dict = Field(default_factory=dict, description="给下游数据")
    for_display: str = Field("", description="展示文本")