"""活动策划智能体（Promotion Plan）v0.4

职责：基于选品、定价、库存、用户画像等数据，自动生成促销活动方案。
v0.4：LLM驱动为主，规则引擎降级。
"""
from __future__ import annotations
import json, re, logging
from app.schemas.promotion import PromotionPlanInput, PromotionPlanOutput, PromotionActivity
logger = logging.getLogger(__name__)


def create_plan(input_data: PromotionPlanInput) -> PromotionPlanOutput:
    products = input_data.recommended_products
    pricing_info = input_data.pricing_info
    inventory_info = input_data.inventory_info
    profile = input_data.user_profile

    if not products:
        products = [{"product_id": 0, "title": "默认商品", "current_price": 100}]

    sensitivity = profile.get("price_sensitivity", "中等") if isinstance(profile, dict) else "中等"
    strategy = pricing_info.get("strategy_summary", "") if isinstance(pricing_info, dict) else ""

    valid_products = [p for p in products if p.get("current_stock", 999) > 0]
    if not valid_products: valid_products = products
    ids = [p.get("product_id", 0) for p in valid_products]
    titles = [p.get("title", "")[:12] for p in valid_products]

    promo_type, discount, days = "限时折扣", "8折", 7
    theme, objective, execution = "", "", ""

    # LLM 生成活动方案
    try:
        product_list = json.dumps(
            [{"title": p.get("title",""), "price": p.get("current_price",0)} for p in valid_products[:5]],
            ensure_ascii=False)
        prompt_parts = [
            "请为以下商品设计促销活动方案。",
            "商品：" + product_list,
            "定价策略：" + strategy,
            "库存：" + str(inventory_info),
            "用户敏感度：" + sensitivity,
            "",
            "返回JSON格式数据，包含theme/type/discount/days/objective/execution字段",
        ]
        prompt = chr(10).join(prompt_parts)
        from app.utils.llm_client import chat_completion
        result = chat_completion("你是电商活动策划专家。只返回JSON。", prompt, temperature=0.5, max_tokens=500)
        if result:
            m = re.search(r"\{.*?\}", result, re.DOTALL)
            if m:
                d = json.loads(m.group())
                promo_type = d.get("type", promo_type)
                discount = d.get("discount", discount)
                days = d.get("days", days)
                theme = d.get("theme", "")
                objective = d.get("objective", "")
                execution = d.get("execution", "")
    except Exception as e:
        logger.warning("LLM活动策划失败: %s", e)

    # 降级规则引擎
    if not theme:
        has_cl = any(p.get("advice") == "清仓" for p in products)
        single = len(valid_products) <= 1
        avg_p = sum(p.get("current_price",0) for p in valid_products) / max(len(valid_products),1)
        if has_cl:
            promo_type, discount, days = "清仓大促", "5折起", 5
            theme = "开仓放价·限时清仓"
            objective = "清库存回笼资金"
        elif single:
            promo_type, discount, days = "单品促销", "8折", 7
            theme = "爆款直降·" + titles[0] + "特惠"
            objective = "打爆款"
        elif "高" in str(sensitivity):
            promo_type, discount, days = "限时折扣", "7折", 7
            theme = "限时狂欢·错过等一年"
            objective = "冲销量"
        else:
            promo_type, discount, days = "限时折扣", "8折", 7
            theme = "品质好物·限时特惠"
            objective = "提升转化率"
    if not execution:
        execution = "预热1天->活动" + str(days-1) + "天->返场1天"

    sales_lift = "预计销量提升20-50%"
    revenue_impact = "预计收入增长10-20%"
    if "清仓" in promo_type:
        sales_lift = "预计销量提升50-80%"
        revenue_impact = "快速回笼资金"

    target_desc = titles[0] if len(titles) == 1 else titles[0] + "等" + str(len(titles)) + "款"
    plan = PromotionActivity(
        type=promo_type, discount=discount, time_frame=str(days)+"天",
        time_frame_days=days, target_products=ids,
        target_products_desc=target_desc,
        estimated_sales_lift=sales_lift,
        estimated_revenue_impact=revenue_impact)

    strategy_parts = []
    if objective: strategy_parts.append("目标："+objective)
    if theme: strategy_parts.append("主题："+theme)
    strategy_parts.append("节奏："+execution)
    strategy_text = "；".join(strategy_parts)

    display_lines = [
        "活动主题：" + theme,
        "活动类型：" + promo_type,
        "折扣力度：" + discount,
        "活动周期：" + str(days) + "天",
        "目标商品：" + target_desc,
        "活动目标：" + objective,
        "执行节奏：" + execution,
        "效果：" + sales_lift + " | " + revenue_impact,
    ]
    display = chr(10).join(display_lines)

    return PromotionPlanOutput(
        plan=plan, strategy_summary=strategy_text,
        for_downstream={"promotion_type":promo_type,"discount":discount,
            "days":days,"theme":theme,"objective":objective,
            "target_products":ids},
        for_display=display)
