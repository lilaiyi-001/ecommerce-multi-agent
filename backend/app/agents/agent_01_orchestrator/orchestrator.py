"""主控智能体核心逻辑

职责：接收意图识别结果，拆解为子任务，编排执行，汇总报告。
"""
from __future__ import annotations
from app.utils.llm_client import chat_completion
import logging
from datetime import datetime, timezone
from typing import Optional
from app.schemas.orchestrator import (
    AgentTask, TaskPlan, AgentResult, PhaseResult,
    OrchestratorInput, OrchestratorOutput,
)
from app.schemas.common import wrap_envelope

logger = logging.getLogger(__name__)

# ── 智能体注册表 ──────────────────────────────────────────────
TASK_REGISTRY = {
    "product_selection": {
        "agent_id": "agent_02_product_selection",
        "label": "选品分析",
        "phase": 1,
        "feishu_access": True,
        "depends_on": [],
    },
    "trend_forecast": {
        "agent_id": "agent_03_trend_forecast",
        "label": "趋势预测",
        "phase": 1,
        "feishu_access": True,
        "depends_on": [],
    },
    "user_profile": {
        "agent_id": "agent_05_user_profile",
        "label": "用户画像",
        "phase": 1,
        "feishu_access": True,
        "depends_on": [],
    },
    "competitor_analysis": {
        "agent_id": "agent_04_competitor_analysis",
        "label": "竞品分析",
        "phase": 2,
        "feishu_access": False,
        "depends_on": ["product_selection"],
    },
    "pricing_strategy": {
        "agent_id": "agent_06_pricing_strategy",
        "label": "定价策略",
        "phase": 2,
        "feishu_access": False,
        "depends_on": ["product_selection", "competitor_analysis"],
    },
    "inventory_advice": {
        "agent_id": "agent_08_inventory_advice",
        "label": "补货/清仓建议",
        "phase": 2,
        "feishu_access": False,
        "depends_on": ["product_selection", "trend_forecast"],
    },
    "marketing_copy": {
        "agent_id": "agent_07_marketing_copy",
        "label": "营销文案",
        "phase": 3,
        "feishu_access": False,
        "depends_on": ["pricing_strategy", "competitor_analysis"],
    },
    "promotion_plan": {
        "agent_id": "agent_09_promotion_plan",
        "label": "活动策划",
        "phase": 3,
        "feishu_access": False,
        "depends_on": ["pricing_strategy", "inventory_advice"],
    },
}

AVAILABLE_AGENTS: set[str] = set()
TASK_HANDLERS: dict[str, callable] = {}


def register_agent(task_type: str, handler: callable = None):
    """注册一个已实现的智能体及其处理函数"""
    if task_type in TASK_REGISTRY:
        AVAILABLE_AGENTS.add(task_type)
        label = TASK_REGISTRY[task_type]["label"]
    else:
        label = task_type
    if handler:
        TASK_HANDLERS[task_type] = handler
    logger.info(f"智能体已注册: {task_type} ({label})")


def build_task_plan(intent_downstream: dict) -> TaskPlan:
    """根据意图识别结果构建任务执行计划"""
    category = intent_downstream.get("category")
    top_n = intent_downstream.get("top_n") or 10
    required_tasks = intent_downstream.get("required_tasks", [])
    # 递归收集任务及其依赖
    def _collect(ttype: str, collected: set):
        info = TASK_REGISTRY.get(ttype)
        if not info or ttype in collected:
            return
        for dep in info.get("depends_on", []):
            _collect(dep, collected)
        collected.add(ttype)
    
    task_set: set[str] = set()
    for t in required_tasks:
        _collect(t, task_set)
    
    tasks: list[AgentTask] = []
    max_phase = 0
    for task_type in task_set:
        info = TASK_REGISTRY.get(task_type)
        if not info:
            continue
        input_data = {"category": category, "top_n": top_n}
        # 为竞品分析/定价/补货等需要具体商品ID的任务添加默认product_id
        if task_type in ("competitor_analysis", "pricing_strategy", "inventory_advice"):
            try:
                from app.services.data_generator import get_demo_products
                prods = get_demo_products(category) if category else []
                if prods:
                    pid = prods[0]["product_id"]
                    prod_data = prods[0]
                    if task_type == "competitor_analysis":
                        input_data["target_product_id"] = pid
                        input_data["product"] = prod_data
                    else:
                        input_data["product_id"] = pid
                        input_data["product"] = prod_data
            except Exception:
                pass
        tasks.append(AgentTask(
            agent_id=info["agent_id"],
            task_type=task_type,
            task_label=info["label"],
            phase=info["phase"],
            depends_on=info["depends_on"],
            feishu_access=info["feishu_access"],
            input_data=input_data,
        ))
        max_phase = max(max_phase, info["phase"])
    return TaskPlan(category=category, top_n=top_n, tasks=tasks, total_phases=max_phase)


def execute_single_task(task_type: str, input_data: dict, session_id: str = "") -> AgentResult:
    """执行单个智能体任务，结果按文档规范包装为 Envelope 格式"""
    info = TASK_REGISTRY.get(task_type)
    if not info:
        return AgentResult(agent_id="?", task_type=task_type, status="failed", error="未知任务类型")

    if task_type in TASK_HANDLERS:
        try:
            handler = TASK_HANDLERS[task_type]
            result = handler(input_data)
            # 按文档 5.2 节包装为 Envelope 格式
            envelope_output = wrap_envelope(
                from_agent=info["agent_id"],
                to_agent="orchestrator",
                session_id=session_id,
                payload=result if isinstance(result, dict) else {},
                task_id=f"task_{task_type}_{datetime.now(timezone.utc).strftime('%H%M%S')}",
            )
            return AgentResult(
                agent_id=info["agent_id"],
                task_type=task_type,
                task_label=info["label"],
                status="completed",
                summary=str(result.get("for_display", ""))[:200] if isinstance(result, dict) else f"{info['label']}：执行完成",
                output=envelope_output,
            )
        except Exception as e:
            logger.error(f"智能体 {task_type} 执行失败: {e}")
            return AgentResult(agent_id=info["agent_id"], task_type=task_type, task_label=info["label"], status="failed", error=str(e))
    elif task_type in AVAILABLE_AGENTS:
        return AgentResult(agent_id=info["agent_id"], task_type=task_type, task_label=info["label"], status="skipped",
                           summary=f"{info['label']}：智能体已注册但未接入处理函数")
    else:
        return AgentResult(agent_id=info["agent_id"], task_type=task_type, task_label=info["label"], status="skipped",
                           summary=f"{info['label']}：智能体尚未开发")


def _merge_upstream_data(task_type, input_data, prev_results, task_deps):
    FIELD_MAP = {
        "competitor_analysis": "competitor_info",
        "trend_forecast": "trend_info",
        "user_profile": "user_profile",
        "pricing_strategy": "pricing_info",
        "inventory_advice": "inventory_info",
    }
    for dep in task_deps:
        dr = prev_results.get(dep)
        if not dr or dr.status != "completed":
            continue
        payload = {}
        if hasattr(dr, "output") and dr.output:
            payload = dr.output.get("payload", {})
        fd = payload.get("for_downstream", {}) if isinstance(payload, dict) else {}
        if not fd:
            continue
        if dep == "product_selection":
            recs = fd.get("recommended_products", [])
            if recs and not input_data.get("product"):
                input_data["product"] = recs[0]
            if recs:
                input_data["recommended_products"] = recs
        elif dep in FIELD_MAP:
            k = FIELD_MAP[dep]
            if not input_data.get(k):
                input_data[k] = fd
    return input_data


def execute_phase(phase, tasks, prev_results, session_id=""):
    pending = [t for t in tasks if t.phase == phase]
    pending.sort(key=lambda t: len(t.depends_on))
    phase_result = PhaseResult(phase=phase)
    max_attempts = len(pending) * 2
    for _ in range(max_attempts):
        if not pending:
            break
        task = pending.pop(0)
        deps_ok = True
        for dep in task.depends_on:
            dep_result = prev_results.get(dep)
            if not dep_result or dep_result.status != "completed":
                deps_ok = False
                break
        if not deps_ok:
            pending.append(task)
            continue
        task.input_data = _merge_upstream_data(
            task.task_type, task.input_data, prev_results, task.depends_on
        )
        result = execute_single_task(task.task_type, task.input_data, session_id)
        phase_result.agents.append(result)
        prev_results[task.task_type] = result
    for task in pending:
        phase_result.agents.append(AgentResult(
            agent_id=task.agent_id, task_type=task.task_type,
            task_label=task.task_label, status="skipped",
            summary=f"{task.task_label}: deps not met, skipped",
        ))
    return phase_result

def _llm_generate_report(task_plan: dict, phase_results_raw: list) -> str:
    """LLM generate professional Markdown report."""
    try:
        agent_outputs = []
        for phase in phase_results_raw:
            for agent in phase.get("agents", []):
                if agent.get("status") == "completed":
                    agent_outputs.append({
                        "agent": agent.get("task_type","?"),
                        "label": agent.get("task_label","?"),
                        "summary": agent.get("summary","")[:500],
                    })
        ctx = json.dumps(agent_outputs, ensure_ascii=False, indent=2)
        prompt_lines = [
            "你是电商选品分析报告撰写专家。根据以下多智能体分析结果，撰写完整选品分析报告。",
            "智能体结果：" + ctx,
            "按以下Markdown结构输出：",
            "## 执行摘要（2-3句核心发现）",
            "## 选品推荐（Top商品+理由+爆款指数）",
            "## 市场对比分析（价格/评分/销量 vs 市场）",
            "## 定价建议（最优区间+折扣空间）",
            "## 营销文案（各商品推广文案）",
            "## 活动策划方案（主题/目标/组合/节奏）",
            "## 风险提示与补货建议",
            "要求：引用数据、建议可落地、禁止编造。",
        ]
        prompt = chr(10).join(prompt_lines)
        result = chat_completion(
            "你是电商分析报告专家。输出专业翔实的Markdown报告。",
            prompt, temperature=0.3, max_tokens=4096)
        if result and len(result.strip()) > 100:
            return result.strip()
    except Exception as e:
        logger.warning("LLM报告失败: %s", e)

    # 降级模板
    parts = []
    total = completed = skipped = 0
    for phase in phase_results_raw:
        for agent in phase.get("agents", []):
            total += 1
            if agent.get("status")=="completed": completed+=1
            elif agent.get("status")=="skipped": skipped+=1
            label = agent.get("task_label","?")
            summary = agent.get("summary","")
            if summary: parts.append("### "+label+"\n\n"+str(summary)[:1000]+"\n")
    return "## 执行摘要\n\n共"+str(total)+"个任务，完成"+str(completed)+"个。\n\n"+"\n".join(parts)


def generate_report(task_plan: TaskPlan, phase_results: list[PhaseResult]) -> dict:
    """汇总所有结果生成最终报告（v0.4：LLM驱动+模板降级）"""
    sections = {}
    total = completed = skipped = 0
    for phase in phase_results:
        for ar in phase.agents:
            total += 1
            if ar.status == "completed": completed += 1
            elif ar.status == "skipped": skipped += 1
            sections[ar.task_type] = {"label": ar.task_label, "status": ar.status, "summary": ar.summary}

    plan_raw = task_plan.model_dump() if hasattr(task_plan,"model_dump") else task_plan
    phases_raw = [p.model_dump() if hasattr(p,"model_dump") else p for p in phase_results]
    markdown = _llm_generate_report(plan_raw, phases_raw)

    summary = "共"+str(total)+"个任务，完成"+str(completed)+"个"
    if markdown and "执行摘要" in markdown:
        idx = markdown.find("执行摘要")
        end_idx = markdown.find("##", idx+10)
        exec_text = markdown[idx:(end_idx if end_idx>0 else idx+300)]
        summary = exec_text.replace("## ","").replace("\n"," ")[:200]

    return {
        "report_id": "rpt_"+datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "category": task_plan.category, "top_n": task_plan.top_n,
        "total_tasks": total, "completed_tasks": completed, "skipped_tasks": skipped,
        "sections": sections, "summary": summary, "markdown_report": markdown,
    }

def orchestrate(input_data: OrchestratorInput) -> OrchestratorOutput:
    """主控智能体主入口"""
    intent_downstream = input_data.intent_result.get("for_downstream", {})
    intent_display = input_data.intent_result.get("for_display", "")
    task_plan = build_task_plan(intent_downstream)

    prev_results = {}
    phase_results: list[PhaseResult] = []
    session_id = input_data.session_id

    for phase in range(1, task_plan.total_phases + 1):
        phase_result = execute_phase(phase, task_plan.tasks, prev_results, session_id)
        phase_results.append(phase_result)

    final_report = generate_report(task_plan, phase_results)

    display_parts = [intent_display, ""]
    if task_plan.tasks:
        display_parts.append(f"执行计划（共 {task_plan.total_phases} 个阶段，{len(task_plan.tasks)} 个子任务）：")
        for t in task_plan.tasks:
            deps = f"（依赖: {', '.join(t.depends_on)}）" if t.depends_on else "（无依赖）"
            access = "可调飞书" if t.feishu_access else ""
            display_parts.append(f"  [阶段{t.phase}] {t.task_label} {access} {deps}")

    display_parts.append("")
    display_parts.append(final_report.get("summary", ""))

    return OrchestratorOutput(
        agent_name="orchestrator", session_id=session_id,
        task_plan=task_plan, phase_results=phase_results,
        final_report=final_report, for_display="\n".join(display_parts),
    )


