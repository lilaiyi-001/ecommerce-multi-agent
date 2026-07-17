"""主控智能体 API 路由 — 支持 LangGraph 编排"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.orchestrator import OrchestratorInput, OrchestratorOutput
from app.schemas.intent import IntentInput
from app.agents.agent_01_orchestrator.orchestrator import orchestrate
from app.agents.agent_00_intent_recognizer.intent_recognizer import recognize_intent
from app.graph.workflow import run_langgraph_flow
from app.utils.auth import require_auth

router = APIRouter(dependencies=[Depends(require_auth)], prefix="/api/v1", tags=["主控智能体"])


@router.post("/orchestrate", response_model=OrchestratorOutput)
def post_orchestrate(input_data: OrchestratorInput):
    """接收 Agent 0 的意图识别结果，执行编排并返回报告"""
    try:
        result = orchestrate(input_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"编排失败: {str(e)}")


@router.post("/chat")
def post_chat(input_data: IntentInput):
    """全流程接口：接收用户消息 -> Agent 0 意图识别 -> Agent 1 编排 -> 返回结果"""
    try:
        intent_result = recognize_intent(input_data)
        intent_output = intent_result.model_dump()

        orch_input = OrchestratorInput(
            intent_result=intent_output,
            session_id=input_data.session_id,
        )
        orch_result = orchestrate(orch_input)
        orch_output = orch_result.model_dump()

        return {
            "session_id": input_data.session_id,
            "intent_result": intent_output,
            "orchestrator_result": orch_output,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"全流程执行失败: {str(e)}")


@router.post("/langgraph/run")
def post_langgraph_run(input_data: IntentInput):
    """LangGraph 编排流程：接收用户消息 -> 意图识别 -> LangGraph 编排"""
    try:
        intent_result = recognize_intent(input_data)
        intent_output = intent_result.model_dump()

        final_state = run_langgraph_flow(intent_output, input_data.session_id)

        display = intent_output.get("for_display", "")
        report = final_state.get("final_report", {})
        if report:
            display += "\n\n" + report.get("summary", "")

        return {
            "session_id": input_data.session_id,
            "intent_result": intent_output,
            "langgraph_result": {
                "task_plan": final_state.get("task_plan"),
                "phase_results": final_state.get("phase_results"),
                "final_report": report,
                "for_display": display,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LangGraph 流程执行失败: {str(e)}")
