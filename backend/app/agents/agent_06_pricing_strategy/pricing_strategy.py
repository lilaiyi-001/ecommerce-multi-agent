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
    
    cat = product.get("category", "electronics")
    fallback = get_demo_products(cat)
    if fallback:
        input_data.product_id = fallback[0]["product_id"]
        product = fallback[0]
        product["current_price"] = product.get("price", product.get("current_price", 0))

    title = product.get("title", f"商品{input_data.product_id}")
    price = product.get("current_price", product.get("price", 0))
    cost = price * input_data.assumed_cost_ratio
    product_id = input_data.product_id

    # ---- 交叉数据注入 ----
    margin_analysis = f"成本{cost:.0f}元/售价{price:.0f}元/毛利率{round((price-cost)/price*100,1) if price>0 else 0}%"
    max_discount_val = round((price - cost) / price * 100, 1) if price > 0 else 0
    try:
        from app.services.cross_table import get_all_cross_views
        cross_views = get_all_cross_views("")
        for cv in cross_views:
            if str(cv.get("product_id", "")) == str(product_id):
                d = cv.get("derived", {})
                mp = d.get("margin_pct")
                if mp is not None:
                    margin_analysis = f"成本{cost:.0f}元/售价{price:.0f}元/毛利率{mp}%"
                pvm = d.get("price_vs_market")
                if pvm is not None:
                    margin_analysis += f" | vs市场价差{pvm:+.0f}元"
                break
    except Exception:
        pass

    optimal_range = (round(cost * 1.1, 0), round(price * 1.1, 0))

    comp_info = input_data.competitor_info
    comp_price = (comp_info.get("competitor_avg_price", price * 1.2)
                  if isinstance(comp_info, dict) else price * 1.2)
    profile = input_data.user_profile
    sensitivity = profile.get("price_sensitivity", "\u4e2d\u7b49") if isinstance(profile, dict) else "\u4e2d\u7b49"
    trend = input_data.trend_info
    trend_dir = trend.get("trend_direction", "\u5e73\u7a33") if isinstance(trend, dict) else "\u5e73\u7a33"

    current_margin = round((price - cost) / price * 100, 1) if price > 0 else 0
    if sensitivity and "\u9ad8" in str(sensitivity):
        strategy = "\u8ddf\u968f\u7b56\u7565" if price > comp_price else "\u6e17\u900f\u7b56\u7565"
        elasticity = "\u9ad8"
    elif sensitivity and "\u4f4e" in str(sensitivity):
        strategy = "\u6ea2\u4ef7\u7b56\u7565"
        elasticity = "\u4f4e"
    else:
        strategy = "\u5747\u8861\u7b56\u7565"
        elasticity = "\u4e2d"

    if trend_dir == "\u4e0a\u5347":
        best = round(price * 1.05, 0)
        min_p = round(price * 0.95, 0)
        max_p = round(price * 1.08, 0)
    elif trend_dir == "\u4e0b\u964d":
        best = round(price * 0.93, 0)
        min_p = round(price * 0.85, 0)
        max_p = round(price, 0)
    else:
        best = round(price * 0.98, 0)
        min_p = round(price * 0.90, 0)
        max_p = round(price * 1.02, 0)

    if best < cost * 1.05:
        best = round(cost * 1.05, 0)
    if min_p < cost:
        min_p = round(cost * 1.01, 0)
    if max_p > comp_price * 1.5:
        max_p = round(comp_price * 1.3, 0)

    analysis = {
        "current_price": price, "assumed_cost": round(cost, 2),
        "current_margin_pct": current_margin,
        "competitor_avg_price": round(comp_price, 2),
        "elasticity": elasticity, "strategy": strategy,
    }
    reasoning = (
        f"\u5f53\u524d\u552e\u4ef7{price}\u5143\uff0c\u4f30\u7b97\u6210\u672c{cost:.0f}\u5143\uff0c\u6bdb\u5229\u7387{current_margin}%\u3002"
        f"\u7528\u6237\u4ef7\u683c\u654f\u611f\u5ea6{elasticity}\uff0c\u7ade\u54c1\u5747\u4ef7{comp_price:.0f}\u5143\uff0c\u8d8b\u52bf{trend_dir}\u3002"
    )
    risk_over = f"\u5b9a\u4ef7\u8fc7\u9ad8\u53ef\u80fd\u5bfc\u81f4\u8f6c\u5316\u7387\u4e0b\u964d\uff0c\u7ade\u54c1\u5747\u4ef7\u4ec5{comp_price:.0f}\u5143"
    risk_under = f"\u5b9a\u4ef7\u8fc7\u4f4e\u4fb5\u8680\u5229\u6da6\u7a7a\u95f4\uff0c\u6210\u672c\u5df2\u8fbe{cost:.0f}\u5143"

    from app.schemas.pricing import PriceRecommendation
    rec = PriceRecommendation(
        suggested_min=min_p, suggested_max=max_p, suggested_best=best,
        strategy=strategy, reasoning=reasoning,
        risk_if_overprice=risk_over, risk_if_underprice=risk_under,
    )

    display = (
        f"\u3010{title[:25]}\u3011\u5b9a\u4ef7\u5efa\u8bae\n"
        f"\u7b56\u7565\uff1a{strategy}\n"
        f"\u63a8\u8350\u552e\u4ef7\uff1a{best}\u5143\uff08\u533a\u95f4{min_p}~{max_p}\u5143\uff09\n"
        f"\u5f53\u524d\u552e\u4ef7\uff1a{price}\u5143 | \u5047\u5b9a\u6210\u672c\uff1a{cost:.0f}\u5143\n"
        f"\u5f53\u524d\u6bdb\u5229\u7387\uff1a{current_margin}%\n"
        f"\u5f39\u6027\uff1a{elasticity}\n"
        f"\u5b9a\u4ef7\u7406\u7531\uff1a{reasoning[:120]}\n"
        f"\u8fc7\u9ad8\u98ce\u9669\uff1a{risk_over}\n"
        f"\u8fc7\u4f4e\u98ce\u9669\uff1a{risk_under}"
    )

    return PricingOutput(
        product_id=input_data.product_id,
        pricing_analysis=analysis,
        recommendation=rec,
        optimal_price_range=optimal_range,
        max_discount=max_discount_val,
        margin_analysis=margin_analysis,
        for_downstream={
            "best_price": best,
            "price_range": [min_p, max_p],
            "strategy_summary": strategy,
            "margin_analysis": margin_analysis,
            "max_discount": max_discount_val,
        },
        for_display=display,
    )
