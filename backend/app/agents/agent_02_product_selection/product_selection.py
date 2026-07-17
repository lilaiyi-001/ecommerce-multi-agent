"""选品分析智能体（Product Selection）

职责：从商品数据中计算爆款指数排行榜，选出最值得关注的商品。
数据来源：优先从飞书 Bitable 拉取，不可用时使用模拟数据。

飞书权限：✅ 可调飞书数据
依赖 LLM：❌ 不依赖（纯代码计算）
"""
from __future__ import annotations
import logging
import statistics
from typing import Optional
from app.schemas.selection import SelectionInput, SelectionOutput, ProductRank
from app.services.data_generator import get_demo_products
from app.services.feishu_data import get_feishu_products
from app.services.category_registry import normalize_category
from app.config import settings

logger = logging.getLogger(__name__)


def _normalize(values: list[float]) -> dict[float, float]:
    """Min-Max 归一化到 [0, 1]"""
    if not values:
        return {}
    mn, mx = min(values), max(values)
    if mx == mn:
        return {v: 0.5 for v in values}
    return {v: (v - mn) / (mx - mn) for v in values}


def calculate_explosive_index(products: list[dict]) -> list[dict]:
    """计算爆款指数（加权评分）"""
    sales_vals = [p.get("avg_daily_sales", 0) for p in products]
    rating_vals = [p.get("rating_rate", 0) for p in products]
    review_vals = [p.get("rating_count", 0) for p in products]

    sales_norm = _normalize(sales_vals)
    rating_norm = _normalize(rating_vals)
    review_norm = _normalize(review_vals)

    W_SALES, W_RATING, W_REVIEWS = 0.40, 0.35, 0.25

    for p in products:
        s = sales_norm.get(p["avg_daily_sales"], 0)
        r = rating_norm.get(p["rating_rate"], 0)
        rv = review_norm.get(p["rating_count"], 0)
        p["explosive_index"] = round((W_SALES * s + W_RATING * r + W_REVIEWS * rv) * 100, 1)

    return products


def compute_price_distribution(products: list[dict]) -> dict:
    """计算价格带分布（文档格式：{min, max, median, bands: [{range, count}]}）"""
    if not products:
        return {"min": 0, "max": 0, "median": 0, "bands": []}
    prices = sorted([p["price"] for p in products])
    p_min, p_max = min(prices), max(prices)
    p_median = statistics.median(prices)
    if p_min == p_max:
        bands = [{"range": f"{p_min:.0f}-{p_max:.0f}", "count": len(prices)}]
    else:
        step = (p_max - p_min) / 4
        band_edges = [
            (p_min, p_min + step),
            (p_min + step, p_min + 2 * step),
            (p_min + 2 * step, p_min + 3 * step),
            (p_min + 3 * step, p_max + 0.01),
        ]
        bands = []
        for lo, hi in band_edges:
            count = sum(1 for p in products if lo <= p["price"] < hi)
            bands.append({"range": f"{lo:.0f}-{hi:.0f}", "count": count})
    return {"min": round(p_min, 2), "max": round(p_max, 2), "median": round(p_median, 2), "bands": bands}


def analyze_products(input_data: SelectionInput) -> SelectionOutput:
    """选品分析主入口"""
    try:
        category = normalize_category(input_data.category)
        top_n = input_data.top_n

        # 1. 获取商品数据（尝试飞书 -> 降级到模拟数据）
        products = get_feishu_products(category)
        if not products:
            products = get_demo_products(category)

        if not products:
            return SelectionOutput(
                category=category,
                total_products=0,
                for_display=f"该类目「{category}」暂无商品数据，请先检查类目名称是否正确",
            )

        # 边界处理：只有1个商品时不排序，直接输出
        if len(products) == 1:
            p = products[0]
            price_dist = compute_price_distribution(products)
            display = (
                f"【{category}】类目仅有1个商品，无法进行排名比较\n"
                f"商品：{p.get('title','')} | 价格{p.get('price',0)}元 | "
                f"评分{p.get('rating_rate',0)} | 日均{p.get('avg_daily_sales',0)}件"
            )
            return SelectionOutput(
                category=category,
                total_products=1,
                price_distribution=price_dist,
                for_display=display,
            )

        # 2. 计算爆款指数
        products = calculate_explosive_index(products)

        # 3. 排序
        products.sort(key=lambda p: p["explosive_index"], reverse=True)

        # 4. 取 top_n
        top_products = products[:top_n]

        # 5. 价格带分布
        price_dist = compute_price_distribution(products)

        # 6. 构建输出
        ranking = []
        for i, p in enumerate(top_products, 1):
            ranking.append(ProductRank(
                rank=i,
                product_id=p["product_id"],
                title=p["title"],
                price=p["price"],
                rating_rate=p["rating_rate"],
                rating_count=p["rating_count"],
                avg_daily_sales=p["avg_daily_sales"],
                explosive_index=p["explosive_index"],
            ))

        band_text = " | ".join(f"{b['range']}元 {b['count']}个" for b in price_dist.get("bands", []))
        ranking_lines = [
            f"  {r.rank}. {r.title[:30]} -- 爆款指数{r.explosive_index}、"
            f"评分{r.rating_rate}、评论{r.rating_count}、日均{r.avg_daily_sales:.0f}件"
            for r in ranking
        ]
        display = (
            f"【{category}】类目共{len(products)}个商品\n"
            f"价格分布：{band_text}\n"
            f"爆款TOP{top_n}：\n" + "\n".join(ranking_lines)
        )

        result = SelectionOutput(
            category=category,
            total_products=len(products),
            price_distribution=price_dist,
            ranking=ranking,
            for_downstream={
                "recommended_products": [
                    {"product_id": r.product_id, "title": r.title, "price": r.price,
                     "rating_rate": r.rating_rate, "explosive_index": r.explosive_index}
                    for r in ranking
                ],
            },
            for_display=display,
        )
        return result
    except Exception as e:
        logger.error(f"analyze_products 异常: {e}")
        return SelectionOutput(
            category=getattr(input_data, "category", "?"),
            total_products=0,
            for_display=f"选品分析异常: {e}",
        )