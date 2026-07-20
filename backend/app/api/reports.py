"""报告生成 API 路由"""
from __future__ import annotations
import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.report import Report
from app.schemas.report import (
    ReportGenerateInput, ReportSummary, ReportDetail, ReportHistoryResponse,
    VALID_ACTIVITY_TYPES,
)
from app.schemas.intent import IntentInput
from app.agents.agent_00_intent_recognizer.intent_recognizer import recognize_intent
from app.agents.agent_01_orchestrator.orchestrator import orchestrate
from app.schemas.orchestrator import OrchestratorInput
from app.services.feishu_data import get_feishu_products
from app.services.data_generator import get_demo_products
from app.utils.auth import require_auth

router = APIRouter(dependencies=[Depends(require_auth)], prefix="/api/v1/reports", tags=["报告"])

ACTIVITY_LABELS = {
    "double11": "双11大促",
    "618": "618大促",
    "new_product": "新品发布",
    "clearance": "清仓促销",
    "daily": "日常促销",
}


@router.post("/generate")
def generate_report(input_data: ReportGenerateInput, db: Session = Depends(get_db)):
    """生成选品分析报告：用户选择商品 + 活动类型 -> 多智能体协作 -> 产出报告"""
    # 校验活动类型
    if input_data.activity_type not in VALID_ACTIVITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的活动类型: {input_data.activity_type}，可选: {', '.join(sorted(VALID_ACTIVITY_TYPES))}"
        )

    all_products = get_feishu_products()
    if not all_products:
        all_products = get_demo_products("", count=40)

    selected_products = [p for p in all_products if str(p["product_id"]) in input_data.product_ids]
    if not selected_products:
        raise HTTPException(status_code=400, detail="未找到匹配的商品，请检查商品ID")

    from collections import Counter
    categories = [p.get("category", "") for p in selected_products if p.get("category")]
    main_category = Counter(categories).most_common(1)[0][0] if categories else "综合"

    product_summary = "\n".join(
        f"- {p['title']}（ID: {p['product_id']}, 售价: {p.get('current_price', p.get('price', 0))}, 库存: {p.get('current_stock', '?')}）"
        for p in selected_products
    )
    activity_label = ACTIVITY_LABELS[input_data.activity_type]

    user_message = (
        f"请对以下 {len(selected_products)} 个商品进行综合分析，活动类型为「{activity_label}」。\n\n"
        f"商品列表：\n{product_summary}\n\n"
        f"要求：\n"
        f"1. 选品分析 —— 评估各商品爆款潜力，排序推荐\n"
        f"2. 定价策略 —— 结合活动类型给出最优定价建议\n"
        f"3. 竞品分析 —— 与市场上同类商品对比\n"
        f"4. 营销文案 —— 为本次活动生成推广文案\n"
        f"5. 活动策划 —— 制定完整活动方案\n"
        f"6. 补货建议 —— 根据库存和活动预期给出补货/清仓建议"
    )

    intent_input = IntentInput(
        user_message=user_message,
        session_id=input_data.session_id,
        turn_number=1,
    )
    try:
        intent_result = recognize_intent(intent_input)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"意图识别失败: {str(e)}")

    # 安全获取 for_downstream
    intent_downstream = (
        intent_result.for_downstream.copy()
        if intent_result.for_downstream
        else {}
    )
    intent_downstream["required_tasks"] = [
        "product_selection", "pricing_strategy", "competitor_analysis",
        "marketing_copy", "promotion_plan", "inventory_advice",
    ]
    intent_downstream["category"] = main_category
    intent_downstream["top_n"] = len(selected_products)

    orch_input = OrchestratorInput(
        intent_result={
            "parsed_result": intent_result.parsed_result.model_dump(),
            "for_downstream": intent_downstream,
            "for_display": intent_result.for_display or "",
        },
        session_id=input_data.session_id,
    )
    try:
        orch_result = orchestrate(orch_input)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"智能体编排失败: {str(e)}")

    report_content = {
        "activity_type": input_data.activity_type,
        "activity_label": activity_label,
        "category": main_category,
        "products": [
            {
                "product_id": p["product_id"],
                "title": p["title"],
                "price": p.get("current_price", p.get("price", 0)),
                "category": p.get("category", ""),
                "stock": p.get("current_stock", 0),
            }
            for p in selected_products
        ],
        "orchestrator_result": orch_result.model_dump(),
        "task_plan": orch_result.task_plan.model_dump() if orch_result.task_plan else {},
        "phase_results": [pr.model_dump() for pr in orch_result.phase_results] if orch_result.phase_results else [],
        "final_report": orch_result.final_report,
    }

    final_report = orch_result.final_report or {}
    summary = final_report.get("summary", "") if isinstance(final_report, dict) else ""

    try:
        report = Report(
            session_id=input_data.session_id,
            product_ids=input_data.product_ids,
            activity_type=input_data.activity_type,
            category=main_category,
            summary=summary,
            report_content=report_content,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"保存报告失败: {str(e)}")

    return {
        "report_id": report.id,
        "session_id": report.session_id,
        "activity_type": report.activity_type,
        "activity_label": activity_label,
        "category": report.category,
        "product_count": len(selected_products),
        "summary": report.summary,
        "report_content": report_content,
        "created_at": report.created_at.isoformat(),
    }


@router.get("/history", response_model=ReportHistoryResponse)
def list_reports(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """获取历史报告列表（按时间倒序）"""
    total = db.query(Report).count()
    reports = (
        db.query(Report)
        .order_by(Report.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    items = [
        ReportSummary(
            id=r.id,
            session_id=r.session_id,
            product_count=len(r.product_ids) if r.product_ids else 0,
            activity_type=r.activity_type,
            category=r.category,
            summary=r.summary,
            created_at=r.created_at.isoformat(),
        )
        for r in reports
    ]
    return ReportHistoryResponse(reports=items, total=total)


@router.get("/{report_id}", response_model=ReportDetail)
def get_report(report_id: str, db: Session = Depends(get_db)):
    """获取单份报告详情"""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    return ReportDetail(
        id=report.id,
        session_id=report.session_id,
        product_ids=report.product_ids or [],
        activity_type=report.activity_type,
        category=report.category,
        summary=report.summary,
        report_content=report.report_content or {},
        created_at=report.created_at.isoformat(),
    )


# === 追问对话 ===
from pydantic import BaseModel, Field


class ReportChatInput(BaseModel):
    user_message: str = Field(..., min_length=1, description="用户追问内容")
    conversation_history: list[dict] = Field(default_factory=list, description="之前的对话历史")


@router.post("/{report_id}/chat")
def chat_followup(report_id: str, input_data: ReportChatInput, db: Session = Depends(get_db)):
    """基于报告上下文进行追问对话"""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    report_content = report.report_content or {}
    products = report_content.get("products", [])
    activity_label = report_content.get("activity_label", report.activity_type)
    category = report.category or "综合"
    summary = report.summary or ""

    if products:
        product_context = "\n".join(
            f"- {p.get('title', '未知')}（{p.get('price', '?')}，{p.get('category', '?')}）"
            for p in products[:10]
        )
    else:
        product_context = "（无具体商品数据）"

    context = (
        f"你是一个电商选品分析助手。用户刚才生成了以下分析报告：\n\n"
        f"活动类型：{activity_label}\n"
        f"类目：{category}\n"
        f"涉及商品：\n{product_context}\n\n"
        f"报告摘要：{summary[:1000]}\n\n"
        f"现在用户追问：{input_data.user_message}\n\n"
        f"请基于以上报告上下文，用中文简洁回答用户的问题。直接输出最终回答，不要输出思考过程。"
        f"如果是具体的数据/建议，尽量引用报告中的内容。"
    )

    from app.utils.llm_client import chat_completion
    try:
        reply = chat_completion(
            "你是一个专业的电商选品分析助手，回答基于已有分析报告，语气专业友好。直接回答，不要输出思考过程。",
            context,
            temperature=0.4,
            max_tokens=1024,
        )
        reply = reply.strip()
        reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL).strip()
        if not reply:
            reply = "抱歉，未能生成有效回复，请重新提问。"
    except Exception as e:
        reply = f"抱歉，处理追问时出错：{str(e)}"

    history = list(input_data.conversation_history or [])
    history.append({"role": "user", "content": input_data.user_message})
    history.append({"role": "assistant", "content": reply})

    if len(history) > 20:
        history = history[-20:]

    return {"reply": reply, "conversation_history": history}
