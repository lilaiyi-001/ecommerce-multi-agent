"""趋势预测智能体数据模型"""
from __future__ import annotations
from typing import Optional, Any, List
from pydantic import BaseModel, Field


class AlgorithmInfo(BaseModel):
    """算法选择信息"""
    selected_method: str = Field(..., description="选中的方法名称")
    reason: str = Field("", description="选择理由")
    weights: dict[str, float] = Field(default_factory=dict, description="各算法权重")
    confidence: str = Field("中", description="置信度 高/中/低")


class DailyForecast(BaseModel):
    """单日预测"""
    day: int = Field(..., description="第几天")
    value: float = Field(0.0, description="预测值")


class ProductTrend(BaseModel):
    """单个商品的趋势预测"""
    product_id: int = Field(..., description="商品ID")
    title: str = Field("", description="商品标题")
    historical_avg: float = Field(0.0, description="历史日均销量")
    trend_direction: str = Field("平稳", description="趋势方向: 上升/下降/平稳")
    algorithm_selection: AlgorithmInfo = Field(default_factory=AlgorithmInfo)
    forecast_7d: dict = Field(default_factory=dict, description="未来7天预测")
    forecast_30d_total: float = Field(0.0, description="30天总预测")
    forecast_30d_avg: float = Field(0.0, description="30天日均预测")
    confidence: str = Field("中", description="置信度 高/中/低")
    # --- 库存关联指标 ---
    sales_velocity: Optional[float] = Field(None, description="销售速度（日均出库量，来自库存表）")
    trend_reason: str = Field("", description="LLM生成的趋势分析理由")


class TrendInput(BaseModel):
    """趋势预测输入"""
    product_ids: list[int] = Field(default_factory=list, description="需要预测的商品ID列表")
    category: str = Field("", description="类目")
    forecast_days: list[int] = Field(default_factory=lambda: [7, 30], description="预测天数")
    context: dict = Field(default_factory=dict, description="上下文")


class TrendOutput(BaseModel):
    """趋势预测输出"""
    agent_name: str = Field(default="trend_forecast")
    category: str = Field("", description="分析类目")
    forecasts: list[ProductTrend] = Field(default_factory=list, description="各商品的预测结果")
    inventory_trend_summary: str = Field("", description="库存趋势摘要（来自库存表交叉数据）")
    for_downstream: dict = Field(default_factory=dict, description="给下游的数据")
    for_display: str = Field("", description="展示文本")