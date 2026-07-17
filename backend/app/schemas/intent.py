"""意图识别智能体的数据模型"""
from __future__ import annotations
import uuid
import enum
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class IntentCategory(str, enum.Enum):
    """意图类别枚举"""
    PRODUCT_ANALYSIS = "product_analysis"
    TREND_QUERY = "trend_query"
    PRICING_ADVICE = "pricing_advice"
    MARKETING_COPY = "marketing_copy"
    PROMOTION_PLAN = "promotion_plan"
    INVENTORY_ADVICE = "inventory_advice"
    GENERAL_QUERY = "general_query"


class ParsedIntent(BaseModel):
    """解析后的结构化意图"""
    intent_category: IntentCategory = Field(..., description="意图类别")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度")
    extracted_params: dict = Field(default_factory=dict, description="提取的参数")
    required_tasks: list[str] = Field(default_factory=list, description="需要的子任务列表")
    task_description: str = Field("", description="任务描述")


class IntentInput(BaseModel):
    """意图识别智能体输入"""
    user_message: str = Field(..., description="用户输入的自然语言消息")
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="会话ID")
    turn_number: int = Field(default=1, description="当前对话轮次")
    conversation_history: list[dict] = Field(default_factory=list, description="对话历史")

    model_config = {"json_schema_extra": {
        "example": {
            "user_message": "帮我分析 electronics 类目，推荐3个值得主推的商品",
            "session_id": "sess_abc123",
            "turn_number": 1,
            "conversation_history": []
        }
    }}


class IntentOutput(BaseModel):
    """意图识别智能体输出"""
    agent_name: str = Field(default="intent_recognizer", description="智能体名称")
    session_id: str = Field(..., description="会话ID")
    turn_number: int = Field(..., description="当前轮次")
    parsed_result: ParsedIntent = Field(..., description="解析结果")
    for_downstream: dict = Field(default_factory=dict, description="给下游的结构化数据")
    for_display: str = Field("", description="给用户看的自然语言摘要")
