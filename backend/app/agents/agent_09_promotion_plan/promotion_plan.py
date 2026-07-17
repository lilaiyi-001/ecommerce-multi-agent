"""活动策划智能体（Promotion Plan）

职责：基于选品、定价、库存、用户画像等数据，自动生成促销活动方案。
纯规则引擎，不依赖 LLM。

飞书权限：不可检索飞书  依赖 LLM：否
"""
from __future__ import annotations
from app.utils.llm_client import chat_completion
import json
from app.schemas.promotion import PromotionPlanInput, PromotionPlanOutput, PromotionActivity


def _llm_design_plan(products: list, pricing: dict, inventory: dict, profile: dict) -> dict:
    """用 LLM 设计活动方案，失败时用模板"""
    from app.utils.llm_client import chat_completion
    try:
        data = f"商品：{json.dumps(products, ensure_ascii=False)}\n定价：{pricing}\n库存：{inventory}\n用户画像：{profile}"
        result = chat_completion(
            "你是一个电商活动策划专家。设计促销活动方案，只返回JSON：{\"type\":\"活动类型\",\"discount\":\"折扣\",\"days\":7,\"reason\":\"理由\"}",
            data, temperature=0.5, max_tokens=400
        )
        import re
        m = re.search(r"\{.*?\}", result, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception:
        pass
    return {}


def _calc_margin(price: float, cost_ratio: float = 0.6) -> float:
    return (price - price * cost_ratio) / price * 100 if price > 0 else 0


def _estimate_effects(promo_type: str, sensitivity: str, has_clearance: bool) -> tuple[str, str]:
    """估算活动效果"""
    if promo_type == "清仓大促":
        return "预计销量提升60-80%", "预计收入下降5-10%（清仓回笼资金）"
    elif promo_type == "限时折扣":
        if sensitivity == "高":
            return "预计销量提升40-50%", "预计收入增长15-20%"
        elif sensitivity == "低":
            return "预计销量提升15-25%", "预计收入增长5-10%"
        return "预计销量提升30-40%", "预计收入增长10-15%"
    elif promo_type == "满减优惠":
        return "预计销量提升20-30%", "预计收入增长8-12%"
    elif promo_type == "组合促销":
        return "预计销量提升25-35%", "预计收入增长12-18%"
    return "预计销量提升20-30%", "预计收入增长10-15%"


def create_plan(input_data: PromotionPlanInput) -> PromotionPlanOutput:
    """活动策划主入口"""
    products = input_data.recommended_products
    pricing_info = input_data.pricing_info
    inventory_info = input_data.inventory_info
    profile = input_data.user_profile

    if not products:
        products = [{"product_id": 0, "title": "默认商品", "current_price": 100}]

    sensitivity = profile.get("price_sensitivity", "中等")
    strategy = pricing_info.get("strategy_summary", "")

    # -- 1. 筛选可参与活动的商品（排除库存不足的） --
    valid_products = []
    for p in products:
        stock = p.get("current_stock", 999)
        if stock <= 0 and p.get("avg_daily_sales", 0) > 0:
            continue
        valid_products.append(p)

    if not valid_products:
        valid_products = products

    ids = [p.get("product_id", 0) for p in valid_products]
    titles = [p.get("title", f"商品{pid}")[:12] for pid in ids]

    # -- 2. 判断活动类型 --
    # 默认值
    promo_type, discount, days = "限时折扣", "8折", 7

    llm_plan = _llm_design_plan(valid_products, pricing_info, inventory_info, profile)
    if llm_plan.get("type"):
        promo_type = llm_plan["type"]
        discount = llm_plan.get("discount", discount)
        days = llm_plan.get("days", days)

    has_clearance = any(p.get("advice") == "清仓" for p in products) or inventory_info.get("advice") == "清仓"
    low_margin_count = sum(1 for p in valid_products if _calc_margin(p.get("current_price", 0)) < 20)
    single_product = len(valid_products) <= 1

    if has_clearance:
        promo_type, discount, days = "清仓大促", "5折起", 5
    elif single_product:
        promo_type, discount, days = "单品促销", "8折", 7
    else:
        avg_price = sum(p.get("current_price", 0) for p in valid_products) / max(len(valid_products), 1)
        if avg_price < 20:
            promo_type, discount, days = "满减优惠", "满200减30", 7
        elif sensitivity == "高":
            promo_type, discount, days = "限时折扣", "7折", 7
        elif "溢价" in strategy:
            promo_type, discount, days = "组合促销", "买2件9折", 14
        else:
            promo_type, discount, days = "限时折扣", "8折", 7

    # -- 3. 策略说明 --
    strategy_lines = []
    if has_clearance:
        strategy_lines.append("部分商品库存较大，以清仓为主快速回笼资金")
    if single_product:
        strategy_lines.append("单商品促销，聚焦爆款打造")
    if low_margin_count > 0:
        strategy_lines.append(f"其中{low_margin_count}件商品利润空间较小，控制折扣深度")
    if sensitivity == "高":
        strategy_lines.append("用户价格敏感度较高，较大折扣可有效刺激转化")
    elif sensitivity == "低":
        strategy_lines.append("用户价格敏感度低，活动重点可放在品质宣传")
    if "溢价" in strategy:
        strategy_lines.append("商品定位中高端，组合购买有利于提升客单价")
    if not strategy_lines:
        strategy_lines.append("综合市场情况制定活动方案")

    strategy_text = "；".join(strategy_lines)
    sales_lift, revenue_impact = _estimate_effects(promo_type, sensitivity, has_clearance)

    # -- 4. 构建输出 --
    target_desc = "、".join(titles[:3])
    if len(titles) > 3:
        target_desc += f"等{len(titles)}款"

    plan = PromotionActivity(
        type=promo_type,
        discount=discount,
        time_frame=f"{days}天",
        time_frame_days=days,
        target_products=ids,
        target_products_desc=target_desc,
        estimated_sales_lift=sales_lift,
        estimated_revenue_impact=revenue_impact,
    )

    display = (
        f"📋 活动策划方案\n\n"
        f"活动类型：{promo_type}\n"
        f"折扣力度：{discount}\n"
        f"活动周期：{days}天\n"
        f"目标商品：{target_desc}\n\n"
        f"效果预估：\n"
        f"  \u2022 销量：{sales_lift}\n"
        f"  \u2022 收入：{revenue_impact}\n\n"
        f"策略说明：{strategy_text}"
    )

    return PromotionPlanOutput(
        plan=plan,
        strategy_summary=strategy_text,
        for_downstream={
            "promotion_type": promo_type,
            "discount": discount,
            "days": days,
            "target_products": ids,
        },
        for_display=display,
    )
