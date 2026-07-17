from __future__ import annotations
from typing import TypedDict, Optional, Any
from app.graph.langgraph_compat import StateGraph, END
from app.schemas.orchestrator import TaskPlan, PhaseResult
from app.agents.agent_01_orchestrator.orchestrator import (
    build_task_plan, execute_phase, generate_report,
)


class AgentState(TypedDict):
    intent_result: dict
    task_plan: Optional[dict]
    phase_results: list[dict]
    prev_results: dict[str, Any]
    final_report: Optional[dict]
    errors: list[str]


def plan_tasks(state: AgentState) -> dict:
    intent_downstream = state["intent_result"].get("for_downstream", {})
    plan = build_task_plan(intent_downstream)
    return {"task_plan": plan.model_dump() if plan else None,
            "phase_results": [], "prev_results": {}, "errors": []}


def execute_phase1(state: AgentState) -> dict:
    plan = TaskPlan(**state["task_plan"])
    result = execute_phase(1, plan.tasks, state["prev_results"])
    prev = dict(state["prev_results"])
    for ar in result.agents: prev[ar.task_type] = ar
    return {"phase_results": [result.model_dump()], "prev_results": prev}


def execute_phase2(state: AgentState) -> dict:
    plan = TaskPlan(**state["task_plan"])
    result = execute_phase(2, plan.tasks, state["prev_results"])
    prev = dict(state["prev_results"])
    for ar in result.agents: prev[ar.task_type] = ar
    phases = list(state["phase_results"])
    phases.append(result.model_dump())
    return {"phase_results": phases, "prev_results": prev}


def execute_phase3(state: AgentState) -> dict:
    plan = TaskPlan(**state["task_plan"])
    result = execute_phase(3, plan.tasks, state["prev_results"])
    prev = dict(state["prev_results"])
    for ar in result.agents: prev[ar.task_type] = ar
    phases = list(state["phase_results"])
    phases.append(result.model_dump())
    return {"phase_results": phases, "prev_results": prev}


def compile_report(state: AgentState) -> dict:
    plan = TaskPlan(**state["task_plan"])
    phase_results = [PhaseResult(**p) for p in state["phase_results"]]
    report = generate_report(plan, phase_results)
    return {"final_report": report}


def _phase_done(state: AgentState, phase_num: int) -> bool:
    return any(r.get("phase") == phase_num for r in state.get("phase_results", []))


def need_phase(state: AgentState, target_phase: int) -> str:
    """检查是否需要执行某一阶段，否则跳到 compile_report"""
    plan = state.get("task_plan")
    if not plan: return "compile_report"
    plan_obj = TaskPlan(**plan)
    if _phase_done(state, target_phase):
        return "compile_report"
    if any(t.phase >= target_phase for t in plan_obj.tasks):
        return f"execute_phase{target_phase}"
    return "compile_report"


def build_execution_graph():
    graph = StateGraph(AgentState)

    graph.add_node("plan_tasks", plan_tasks)
    graph.add_node("execute_phase1", execute_phase1)
    graph.add_node("execute_phase2", execute_phase2)
    graph.add_node("execute_phase3", execute_phase3)
    graph.add_node("compile_report", compile_report)

    graph.set_entry_point("plan_tasks")

    graph.add_conditional_edges(
        "plan_tasks", lambda s: need_phase(s, 1),
        {"execute_phase1": "execute_phase1", "compile_report": "compile_report"},
    )
    graph.add_conditional_edges(
        "execute_phase1", lambda s: need_phase(s, 2),
        {"execute_phase2": "execute_phase2", "compile_report": "compile_report"},
    )
    graph.add_conditional_edges(
        "execute_phase2", lambda s: need_phase(s, 3),
        {"execute_phase3": "execute_phase3", "compile_report": "compile_report"},
    )
    graph.add_edge("execute_phase3", "compile_report")
    graph.add_edge("compile_report", "END")

    return graph.compile()


_executor = None
def get_executor():
    global _executor
    if _executor is None:
        _executor = build_execution_graph()
    return _executor


def run_langgraph_flow(intent_result: dict, session_id: str) -> dict:
    executor = get_executor()
    initial_state: AgentState = {
        "intent_result": intent_result, "task_plan": None,
        "phase_results": [], "prev_results": {},
        "final_report": None, "errors": [],
    }
    return executor.invoke(initial_state)
