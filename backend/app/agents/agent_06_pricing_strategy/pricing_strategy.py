"""定价策略智能体（Pricing Strategy）

职责：结合成本假设、竞品价格、用户画像和需求趋势，
给出商品的合理定价建议及理由。

飞书权限：不可检索飞书  依赖 LLM：否（纯代码计算）
"""
from __future__ import annotations
from app.utils.llm_client import chat_completion
import json
from app.schemas.pricing import PricingInput, PricingOutput, PriceRecommendation


def _calc_cost_based(price: float, cost_ratio: float) -> float:
    return round(price * cost_ratio, 2)


def _estimate_elasticity(sensitivity: str, trend: str) -> str:
    """估算需求弹性"""
    if sensitivity == "高":
        return "高度弹性（降价5%预计销量提升10%+）"
    elif sensitivity == "低":
        return "低弹性（价格变动对销量影响较小）"
    else:
        trend_desc = "且需求上升" if "上升" in trend else ("且需求下降" if "下降" in trend else "")
        return f"中等弹性（降价5%预计销量提升8%）{trend_desc}"


def _calc_adjustments(sensitivity: str, trend: str) -> tuple[float, float]:
    """计算价格调整系数 (sensitivity_adjust, trend_adjust)"""
    sens_map = {"高": -0.10, "中等": 0.0, "低": 0.08}
    trend_map = {"上升": 0.08, "平稳": 0.0, "下降": -0.08}
    sa = sens_map.get(sensitivity, 0.0)
    ta = trend_map.get(trend, 0.0)
    return (sa, ta)


def _llm_generate_reasoning(product: dict, best: float, strategy: str, comp_avg) -> str:
    """用 LLM 生成定价理由，失败时用模板"""
    try:
        prompt = f"商品：{json.dumps(product, ensure_ascii=False)}\n建议价：{best}\n策略：{strategy}\n竞品均价：{comp_avg}"
        return chat_completion(
            "你是一个电商定价策略分析师。基于提供的数据解释定价理由，不要编造数据。",
            prompt, temperature=0.3, max_tokens=400
        )
    except Exception:
        return ""


def analyze_pricing(input_data: PricingInput) -> PricingOutput:
    """定价策略主入口"""
    product = input_data.product
    comp_info = input_data.competitor_info
    trend_info = input_data.trend_info
    profile = input_data.user_profile

    # product_id=0（未指定）时自动选择类目下第一个商品
    if input_data.product_id == 0 and not product.get("current_price"):
        from app.services.data_generator import get_demo_products
        cat = product.get("category", input_data.context.get("category", "electronics") if hasattr(input_data, "context") and input_data.context else "electronics")
        fallback = get_demo_products(cat)
        if fallback:
            input_data.product_id = fallback[0]["product_id"]
            product = fallback[0]
            product["current_price"] = product.get("price", product.get("current_price", 0))

    title = product.get("title", f"商品{input_data.product_id}")
    price = product.get("current_price") or product.get("price", 0)
    if price <= 0:
        return PricingOutput(
            product_id=input_data.product_id,
            for_display=f"商品价格异常（{price}），无法进行定价分析",
        )
    category = product.get("category", "")
    cost_ratio = input_data.assumed_cost_ratio

    competitor_avg = comp_info.get("competitor_avg_price")
    competitor_score = comp_info.get("overall_score")
    sensitivity = profile.get("price_sensitivity", "中等")
    demand_trend = trend_info.get("demand_trend", "平稳")

    # 1. 成本分析
    cost = _calc_cost_based(price, cost_ratio)
    current_margin = round((price - cost) / price * 100, 1) if price > 0 else 0
    elasticity = _estimate_elasticity(sensitivity, demand_trend)

    # 2. 计算建议价格
    sa, ta = _calc_adjustments(sensitivity, demand_trend)

    # 基础价格：成本加成 (1.6 = ~37.5%毛利率)
    cost_plus = round(cost * 1.6, 2)

    # 竞品参考价
    if competitor_avg and competitor_avg > 0:
        competitor_ref = round(competitor_avg, 2)
        competitor_range_str = f"竞品均价{competitor_avg:.2f}元"
    else:
        competitor_ref = cost_plus
        competitor_range_str = "无竞品数据（采用成本加成法）"

    # 混合计算: 成本法x0.5 + 竞品法x0.5 + 用户调整 + 趋势调整
    blended = round(cost_plus * 0.5 + competitor_ref * 0.5 * (1 + sa + ta), 2)

    # 确保不亏本
    if blended < cost * 1.15:
        blended = round(cost * 1.15, 2)

    best = blended
    min_price = round(best * 0.92, 2)
    max_price = round(best * 1.08, 2)

    # 3. 定价策略
    if competitor_avg and competitor_avg > 0:
        ratio = best / competitor_avg
        if ratio < 0.92:
            strategy = "走性价比路线，低于竞品平均价"
            llm_reasoning = _llm_generate_reasoning(product, best, strategy, competitor_avg)
            reasoning = llm_reasoning if llm_reasoning else f"当前售价{price}元，竞品均价{competitor_avg:.2f}元。建议定价{best}元，以性价比优势抢占市场份额，同时保持{round((best-cost)/best*100,1)}%毛利率。"
        elif ratio < 1.08:
            strategy = "跟随市场定价，维持竞争中性"
            reasoning = f"当前售价{price}元，竞品均价{competitor_avg:.2f}元。建议定价{best}元，与竞品持平，靠产品力和服务差异化竞争。"
        else:
            strategy = "略有溢价，突出品质差异化"
            reasoning = f"当前售价{price}元，竞品均价{competitor_avg:.2f}元。建议定价{best}元，强调品质优势获取溢价，目标用户对价格不敏感。"
    else:
        strategy = "成本加成法（无竞品数据）"
        reasoning = f"由于缺少竞品数据，采用成本加成法定价。成本{cost}元，建议定价{best}元，毛利率{round((best-cost)/best*100,1)}%。"

    # 4. 风险
    if sensitivity in ("高", "中等"):
        risk_over = f"若定价超过{max_price}元，预计流失约15%价格敏感用户"
    else:
        risk_over = f"若定价超过{max_price}元，可能影响部分价格敏感用户的转化"

    if best < cost * 1.2:
        risk_under = f"若定价低于{min_price}元，毛利压缩至{round((min_price-cost)/min_price*100,1)}%，不建议"
    else:
        risk_under = "定价空间充裕，有促销弹性"

    # 5. 构建输出
    analysis = {
        "assumed_cost": cost,
        "current_margin": f"{current_margin}%",
        "competitor_range": competitor_range_str,
        "demand_elasticity_estimate": elasticity,
    }

    rec = PriceRecommendation(
        suggested_price_range={"min": min_price, "max": max_price, "best": best},
        suggested_min=min_price,
        suggested_max=max_price,
        suggested_best=best,
        strategy=strategy,
        reasoning=reasoning,
        risk_if_overprice=risk_over,
        risk_if_underprice=risk_under,
    )

    # 展示文本
    display = (
        f"【{title[:25]}】定价建议\n"
        f"策略：{strategy}\n"
        f"推荐售价：{best}元（区间{min_price}~{max_price}元）\n"
        f"当前售价：{price}元 | 假定成本：{cost}元\n"
        f"当前毛利率：{current_margin}%\n"
        f"弹性：{elasticity}\n"
        f"定价理由：{reasoning[:120]}\n"
        f"过高风险：{risk_over}\n"
        f"过低风险：{risk_under}"
    )

    return PricingOutput(
        product_id=input_data.product_id,
        pricing_analysis=analysis,
        recommendation=rec,
        for_downstream={
            "best_price": best,
            "price_range": [min_price, max_price],
            "strategy_summary": strategy,
        },
        for_display=display,
    )


