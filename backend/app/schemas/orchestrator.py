"""主控智能体（Orchestrator）数据模型"""
from __future__ import annotations
from typing import Optional, Any
from pydantic import BaseModel, Field


class AgentTask(BaseModel):
    """单个智能体的执行任务"""
    agent_id: str = Field(..., description="智能体ID，如 agent_02_product_selection")
    task_type: str = Field(..., description="任务类型，如 product_selection")
    task_label: str = Field(..., description="任务中文名称，如 选品分析")
    phase: int = Field(..., ge=1, le=3, description="执行阶段（1/2/3）")
    depends_on: list[str] = Field(default_factory=list, description="前置依赖的任务类型")
    input_data: dict = Field(default_factory=dict, description="传递给智能体的输入数据")
    feishu_access: bool = Field(default=False, description="是否需要飞书权限")


class TaskPlan(BaseModel):
    """任务执行计划"""
    category: Optional[str] = Field(None, description="分析的类目")
    top_n: Optional[int] = Field(None, description="推荐商品数量")
    tasks: list[AgentTask] = Field(default_factory=list, description="所有待执行任务")
    total_phases: int = Field(0, description="总阶段数")


class AgentResult(BaseModel):
    """单个智能体的执行结果"""
    agent_id: str = Field(..., description="智能体ID")
    task_type: str = Field(..., description="任务类型")
    task_label: str = Field("", description="任务名称")
    status: str = Field(..., description="状态: completed/failed/skipped")
    summary: str = Field("", description="执行摘要")
    output: dict = Field(default_factory=dict, description="详细输出")
    error: Optional[str] = Field(None, description="错误信息")


class PhaseResult(BaseModel):
    """单个阶段的执行结果"""
    phase: int = Field(..., description="阶段号")
    agents: list[AgentResult] = Field(default_factory=list, description="该阶段所有智能体的结果")


class OrchestratorInput(BaseModel):
    """主控智能体输入"""
    intent_result: dict = Field(..., description="Agent 0 的输出")
    session_id: str = Field(..., description="会话ID")

    model_config = {"json_schema_extra": {
        "example": {
            "intent_result": {
                "parsed_result": {
                    "intent_category": "product_analysis",
                    "confidence": 0.85,
                    "extracted_params": {"category": "electronics", "top_n": 3},
                    "required_tasks": ["product_selection", "pricing_strategy"],
                },
                "for_downstream": {"category": "electronics", "top_n": 3},
            },
            "session_id": "sess_abc123",
        }
    }}


class OrchestratorOutput(BaseModel):
    """主控智能体输出"""
    agent_name: str = Field(default="orchestrator", description="智能体名称")
    session_id: str = Field(..., description="会话ID")
    task_plan: TaskPlan = Field(..., description="任务执行计划")
    phase_results: list[PhaseResult] = Field(default_factory=list, description="各阶段执行结果")
    final_report: Optional[dict] = Field(None, description="最终汇总报告")
    for_display: str = Field("", description="给用户看的报告文本")
