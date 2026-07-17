"""编排层单元测试"""
from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from app.agents.agent_01_orchestrator.orchestrator import (
    build_task_plan, _merge_upstream_data, execute_phase, generate_report,
    TASK_REGISTRY, AVAILABLE_AGENTS, TASK_HANDLERS,
)
from app.schemas.orchestrator import AgentTask, TaskPlan, AgentResult, PhaseResult

@pytest.fixture(autouse=True)
def setup_agents():
    for t in TASK_REGISTRY:
        AVAILABLE_AGENTS.add(t)
        if t not in TASK_HANDLERS:
            TASK_HANDLERS[t] = MagicMock(return_value={"ok": True})
    yield

class TestBuildTaskPlan:
    def test_single_task_no_deps(self):
        plan = build_task_plan({"category": "electronics", "top_n": 5, "required_tasks": ["product_selection"]})
        assert len(plan.tasks) == 1
        assert plan.tasks[0].phase == 1
    def test_dependency_chain_resolved(self):
        plan = build_task_plan({"category": "electronics", "top_n": 5, "required_tasks": ["pricing_strategy"]})
        task_types = {t.task_type for t in plan.tasks}
        assert "product_selection" in task_types
        assert "competitor_analysis" in task_types
    def test_phase_grouping(self):
        plan = build_task_plan({"category": "electronics", "top_n": 3, "required_tasks": ["promotion_plan"]})
        phases = {t.phase for t in plan.tasks}
        assert phases == {1, 2, 3}
    def test_empty_required_tasks(self):
        plan = build_task_plan({"category": "electronics", "top_n": 3, "required_tasks": []})
        assert plan.tasks == []

class TestMergeUpstreamData:
    def test_inject_product_selection(self):
        prev = {"product_selection": AgentResult(
            agent_id="a2", task_type="product_selection", task_label="sel", status="completed",
            output={"payload": {"for_downstream": {"recommended_products": [{"product_id": 1, "title": "P1"}]}}},
        )}
        result = _merge_upstream_data("competitor_analysis", {"category": "e"}, prev, ["product_selection"])
        assert "recommended_products" in result
    def test_skip_missing_dep(self):
        result = _merge_upstream_data("competitor_analysis", {"category": "e"}, {}, ["product_selection"])
        assert result == {"category": "e"}

class TestExecutePhase:
    def test_phase1_completed(self):
        tasks = [AgentTask(agent_id="a2", task_type="product_selection", task_label="sel", phase=1, depends_on=[], feishu_access=False, input_data={"category": "e", "top_n": 3})]
        phase = execute_phase(1, tasks, {}, "s1")
        assert phase.agents[0].status == "completed"
    def test_missing_dep_skipped(self):
        tasks = [AgentTask(agent_id="a4", task_type="competitor_analysis", task_label="comp", phase=2, depends_on=["product_selection"], feishu_access=False, input_data={"category": "e"})]
        phase = execute_phase(2, tasks, {}, "s1")
        assert phase.agents[0].status == "skipped"

class TestGenerateReport:
    def test_structure(self):
        plan = TaskPlan(task_plan_id="tp1", category="e", top_n=3, total_phases=1, tasks=[])
        phases = [PhaseResult(phase=1, agents=[AgentResult(agent_id="a2", task_type="product_selection", task_label="sel", status="completed", summary="ok")])]
        report = generate_report(plan, phases)
        assert "report_id" in report
        assert report["total_tasks"] == 1
        assert report["completed_tasks"] == 1
