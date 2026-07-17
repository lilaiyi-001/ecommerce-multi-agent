"""竞品分析智能体（Competitor Analysis）

职责：给定一个商品，与同类目竞品对比价格/评分/销量，输出竞争力评估。
数据来源：Agent 2 的分析结果（使用模拟数据演示）
输入规范符合文档要求：接收 target_product、category_products、category_sales_data

飞书权限：不可检索飞书  依赖 LLM：否（纯代码计算）
"""
from __future__ import annotations
from app.utils.llm_client import chat_completion
from app.schemas.competitor import (
    CompetitorInput, CompetitorOutput, CompetitorInfo, CompetitionAssessment,
)
from app.services.data_generator import get_demo_products
from app.services.feishu_data import get_feishu_products


def _price_score(target_price: float, min_p: float, max_p: float) -> float:
    if max_p == min_p:
        return 50.0
    return max(0, min(100, (max_p - target_price) / (max_p - min_p) * 100))


def _rating_score(target_rating: float, min_r: float, max_r: float) -> float:
    if max_r == min_r:
        return 50.0
    return max(0, min(100, (target_rating - min_r) / (max_r - min_r) * 100))


def _sales_score(target_sales: float, min_s: float, max_s: float) -> float:
    if max_s == min_s:
        return 50.0
    return max(0, min(100, (target_sales - min_s) / (max_s - min_s) * 100))


def _position(value: float, competitors: list[tuple], reverse: bool = False) -> str:
    if not competitors:
        return "唯一商品"
    sorted_vals = sorted([c[0] for c in competitors], reverse=reverse)
    rank = 1
    for i, v in enumerate(sorted_vals):
        if (reverse and value >= v) or (not reverse and value <= v):
            rank = i + 1
            break
    else:
        rank = len(sorted_vals) + 1
    total = len(sorted_vals) + 1
    pct = rank / total
    if rank == 1:
        return "最高" if reverse else "最低"
    elif pct <= 0.33:
        return "较高" if reverse else "较低"
    elif pct <= 0.66:
        return "中等"
    elif pct <= 0.90:
        return "较低" if reverse else "较高"
    else:
        return "最低" if reverse else "最高"


def _llm_generate_assessment(target_title: str, score: float, strengths: list, weaknesses: list) -> str:
    """用 LLM 生成竞争力评估文字，失败时用模板"""
    from app.utils.llm_client import chat_completion
    try:
        prompt = f"商品：{target_title}\n综合评分：{score}\n优势：{strengths}\n劣势：{weaknesses}\n请给出简洁的竞争力评估（50字以内）"
        result = chat_completion(
            "你是一个电商竞品分析助手。只基于提供的数据做评估，不要编造。",
            prompt, temperature=0.3, max_tokens=200
        )
        return result.strip()
    except Exception:
        return ""


def analyze_competitor(input_data: CompetitorInput) -> CompetitorOutput:
    """竞品分析主入口"""
    target_id = input_data.target_product_id
    category = input_data.category

    # 获取目标商品：优先使用文档标准输入中的 target_product，降级到从类目数据中查找
    target = None

    # product_id=0（未指定）时自动选择类目下第一个商品
    if target_id == 0:
        fallback_products = (get_feishu_products(category) or get_demo_products(category)) if not input_data.category_products else list(input_data.category_products)
        if fallback_products:
            target_id = fallback_products[0]["product_id"]
            if not input_data.category_products:
                input_data.category_products = fallback_products

    if input_data.target_product and input_data.target_product.get("title"):
        target = {
            "product_id": target_id,
            "title": input_data.target_product.get("title", ""),
            "price": input_data.target_product.get("price", 0),
            "rating_rate": input_data.target_product.get("rating_rate", 0),
            "rating_count": input_data.target_product.get("rating_count", 0),
            "avg_daily_sales": (input_data.category_sales_data.get(str(target_id), {}).get("avg_daily_sales", 0)
                                if isinstance(input_data.category_sales_data, dict) else 0),
            "category": category,
        }

    # 获取类目商品列表：优先 category_products，降级到模拟数据
    products = None
    if input_data.category_products:
        products = list(input_data.category_products)
    else:
        products = get_feishu_products(category) or get_demo_products(category)

    if not target and products:
        for p in products:
            if p["product_id"] == target_id:
                target = p
                break

    if not target:
        return CompetitorOutput(
            target_product_id=target_id,
            for_display=f"商品ID={target_id}在类目「{category}」中未找到",
        )

    if not products:
        return CompetitorOutput(
            target_product_id=target_id,
            for_display=f"类目「{category}」暂无商品数据",
        )

    # 筛选竞品
    price_lo = target["price"] * 0.5
    price_hi = target["price"] * 1.5
    competitors_raw = [
        p for p in products
        if p["product_id"] != target_id
        and price_lo <= p["price"] <= price_hi
    ]

    if not competitors_raw:
        competitors_raw = [p for p in products if p["product_id"] != target_id]

    if not competitors_raw:
        return CompetitorOutput(
            target_product_id=target_id,
            target_product_title=target["title"],
            competition_assessment=CompetitionAssessment(
                overall_score=50, verdict="该商品在同类目中无直接竞品",
            ),
            for_display=f"【{target['title'][:30]}】在类目「{category}」中无竞品",
        )

    # 构建竞品列表
    competitors_info = []
    for c in competitors_raw:
        competitors_info.append(CompetitorInfo(
            product_id=c["product_id"],
            title=c["title"],
            price=c["price"],
            rating_rate=c["rating_rate"],
            rating_count=c["rating_count"],
            avg_daily_sales=c["avg_daily_sales"],
        ))

    # 计算各维度分数
    prices = [(c["price"], c["product_id"]) for c in competitors_raw + [target]]
    ratings = [(c["rating_rate"], c["product_id"]) for c in competitors_raw + [target]]
    sales = [(c["avg_daily_sales"], c["product_id"]) for c in competitors_raw + [target]]

    tp, tr, ts = target["price"], target["rating_rate"], target["avg_daily_sales"]
    min_p, max_p = min(p[0] for p in prices), max(p[0] for p in prices)
    min_r, max_r = min(r[0] for r in ratings), max(r[0] for r in ratings)
    min_s, max_s = min(s[0] for s in sales), max(s[0] for s in sales)

    ps = _price_score(tp, min_p, max_p)
    rs = _rating_score(tr, min_r, max_r)
    ss = _sales_score(ts, min_s, max_s)
    overall = round(ps * 0.30 + rs * 0.35 + ss * 0.35, 1)

    price_pos = _position(tp, [(c["price"], c["product_id"]) for c in competitors_raw], reverse=False)
    rating_pos = _position(tr, [(c["rating_rate"], c["product_id"]) for c in competitors_raw], reverse=True)
    sales_pos = _position(ts, [(c["avg_daily_sales"], c["product_id"]) for c in competitors_raw], reverse=True)

    strengths, weaknesses = [], []
    if ps >= 65: strengths.append("价格有优势")
    elif ps < 40: weaknesses.append("价格偏高")
    if rs >= 65: strengths.append("评分高")
    elif rs < 40: weaknesses.append("评分偏低")
    if ss >= 65: strengths.append("销量领先")
    elif ss < 40: weaknesses.append("销量偏低")
    if target.get("rating_count", 0) > 1000:
        strengths.append("口碑好（评价数多）")

    if overall >= 80:
        verdict = "竞争力强，在多个维度上领先竞品"
    elif overall >= 60:
        verdict = "竞争力中等，部分维度有优势"
    elif overall >= 40:
        verdict = "竞争力一般，需要针对性改进"
    else:
        verdict = "竞争力较弱，建议重新评估定价和推广策略"

    avg_competitor_price = sum(c["price"] for c in competitors_raw) / max(len(competitors_raw), 1)
    price_diff = f"高于竞品均价{abs(tp - avg_competitor_price):.1f}元" if tp > avg_competitor_price else f"低于竞品均价{abs(tp - avg_competitor_price):.1f}元"
    avg_sales = sum(c["avg_daily_sales"] for c in competitors_raw) / max(len(competitors_raw), 1)

    display = (
        f"【{target['title'][:30]}】竞争力评分 {overall}/100\n"
        f"价格定位：{price_pos}（{price_diff}）\n"
        f"评分定位：{rating_pos}（{tr:.1f}分）\n"
        f"销量定位：{sales_pos}（日均{ts:.0f}件，竞品平均{avg_sales:.0f}件）\n"
        f"优势：{'、'.join(strengths) if strengths else '无明显优势'}\n"
        f"劣势：{'、'.join(weaknesses) if weaknesses else '无明显劣势'}\n"
        f"综合评语：{verdict}"
    )

    full_assessment = CompetitionAssessment(
        price_position=price_pos,
        rating_position=rating_pos,
        sales_position=sales_pos,
        overall_score=overall,
        verdict=verdict,
        strengths=strengths,
        weaknesses=weaknesses,
    )

    return CompetitorOutput(
        target_product_id=target_id,
        target_product_title=target["title"],
        competitors=competitors_info,
        competition_assessment=full_assessment,
        for_downstream={
            "target_product_id": target_id,
            "overall_score": overall,
            "competitor_avg_price": round(avg_competitor_price, 2),
            "strengths": strengths,
            "weaknesses": weaknesses,
        },
        for_display=display,
    )

