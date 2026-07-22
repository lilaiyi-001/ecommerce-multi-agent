"""选品分析智能体（Product Selection）

职责：从商品数据中计算爆款指数排行榜，选出最值得关注的商品。
数据来源：优先从飞书 Bitable 拉取，不可用时使用模拟数据。
v0.3: 接入三表交叉对比引擎，注入价格差、库存健康、利润率等衍生指标。

飞书权限：✅ 可调飞书数据
依赖 LLM：❌ 不依赖（纯代码计算 + 可选 LLM 增强）
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


def _safe_normalize_and_get(val: float, norm_map: dict, key: float) -> float:
    """安全地从归一化映射中取值"""
    return norm_map.get(key, 0.0)


def calculate_explosive_index(products: list[dict], cross_map: dict | None = None) -> list[dict]:
    """计算爆款指数（多维度加权评分）。

    维度权重：
    - 日均销量: 30%
    - 评分: 25%
    - 评论数: 15%
    - 价格优势: 15%（交叉对比：vs 市场均价，便宜加分）
    - 库存健康: 15%（交叉对比：充足/正常加分，预警/缺货扣分）
    """
    sales_vals = [p.get("avg_daily_sales", 0) for p in products]
    rating_vals = [p.get("rating_rate", 0) for p in products]
    review_vals = [p.get("rating_count", 0) for p in products]

    sales_norm = _normalize(sales_vals)
    rating_norm = _normalize(rating_vals)
    review_norm = _normalize(review_vals)

    # 价格优势：负值（便宜）=高分，做反向归一化
    price_advantage_vals: list[float] = []
    for p in products:
        pid = str(p.get("product_id", ""))
        d = (cross_map or {}).get(pid, {})
        pvm = d.get("price_vs_market")
        if pvm is not None:
            # 取负值：便宜加分
            price_advantage_vals.append(-pvm)
        else:
            price_advantage_vals.append(0.0)
    price_adv_norm = _normalize(price_advantage_vals) if price_advantage_vals else {}

    # 库存健康：充足=1.0, 正常=0.7, 未知=0.5, 预警=0.3, 缺货=0.0
    STOCK_SCORE = {"充足": 1.0, "正常": 0.7, "未知": 0.5, "预警": 0.3, "缺货": 0.0}

    W_SALES, W_RATING, W_REVIEWS, W_PRICE_ADV, W_STOCK = 0.30, 0.25, 0.15, 0.15, 0.15

    for p in products:
        s = _safe_normalize_and_get(p["avg_daily_sales"], sales_norm, p["avg_daily_sales"])
        r = _safe_normalize_and_get(p["rating_rate"], rating_norm, p["rating_rate"])
        rv = _safe_normalize_and_get(p["rating_count"], review_norm, p["rating_count"])

        pid = str(p.get("product_id", ""))
        d = (cross_map or {}).get(pid, {})
        pa = price_adv_norm.get(-(d.get("price_vs_market") or 0), 0.5)
        sh = STOCK_SCORE.get(d.get("stock_health", "未知"), 0.5)

        score = (W_SALES * s + W_RATING * r + W_REVIEWS * rv +
                 W_PRICE_ADV * pa + W_STOCK * sh) * 100
        p["explosive_index"] = round(score, 1)

    return products


def compute_price_distribution(products: list[dict]) -> dict:
    """计算价格带分布"""
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


def _build_cross_summary(cross_map: dict, products: list[dict]) -> str:
    """生成交叉对比摘要文本"""
    if not cross_map:
        return ""

    total = len(products)
    with_cross = sum(1 for p in products if str(p.get("product_id")) in cross_map)
    cheaper = sum(1 for p in products
                  if (cross_map.get(str(p.get("product_id")), {}).get("price_vs_market") or 0) < 0)
    low_stock = sum(1 for p in products
                    if cross_map.get(str(p.get("product_id")), {}).get("stock_health") in ("预警", "缺货"))

    parts = [f"三表交叉对比：{with_cross}/{total} 个商品有交叉数据"]
    if cheaper:
        parts.append(f"{cheaper} 个商品价格低于市场均价")
    if low_stock:
        parts.append(f"{low_stock} 个商品库存预警或缺货")
    return "；".join(parts)



# ================================================================
#  LLM 增强：生成选品推荐理由
# ================================================================

def _llm_generate_ranking_reasons(ranking: list[ProductRank], cross_map: dict) -> list[str]:
    """调用 LLM 为 Top N 商品生成推荐理由（降级时返回空列表）。

    输入：Top N 商品的交叉数据（价格差、库存健康、利润率、市场评分等）
    输出：每个商品 2-3 句推荐理由，引用具体数据。

    失败时安全降级返回空列表，不影响主流程。
    """
    if not ranking:
        return []

    # 构建简洁的数据上下文
    products_data = []
    for r in ranking[:5]:  # 最多 5 个商品
        pid = str(r.product_id)
        d = cross_map.get(pid, {})
        pvm = d.get("price_vs_market")
        price_note = ""
        if pvm is not None:
            if pvm < 0:
                price_note = f"低于市场均价{abs(pvm):.0f}元"
            else:
                price_note = f"高于市场均价{pvm:.0f}元"
        products_data.append(
            f"{r.rank}. {r.title} | 售价{r.price}元({price_note}) | "
            f"评分{r.rating_rate} | 库存{d.get('stock_health','?')} | "
            f"利润率{d.get('margin_pct','?')}% | 爆款指数{r.explosive_index}"
        )

    prompt = (
        "你是电商选品分析师。根据以下商品的交叉对比数据，为每个商品写 2-3 句推荐理由。\n"
        "要求：\n"
        "1. 引用具体数据（价格差、评分、库存状态、利润率等）\n"
        "2. 说明该商品为什么值得推荐（价格优势？口碑好？库存充足？利润高？）\n"
        "3. 每条理由以 '第N名：「商品名」' 开头\n"
        "4. 禁止编造数据，只用提供的数字\n\n"
        + "\n".join(products_data)
    )

    try:
        from app.utils.llm_client import chat_completion
        result = chat_completion(
            system_prompt="你是电商选品分析师，输出简洁有力的商品推荐理由。",
            user_message=prompt,
            temperature=0.4,
            max_tokens=600,
        )
        if result:
            lines = [line.strip() for line in result.strip().split("\n") if line.strip()]
            logger.info("LLM 推荐理由生成成功: %d 条", len(lines))
            return lines[:10]
    except Exception as e:
        logger.warning("LLM 推荐理由生成失败（降级）: %s", e)

    return []

def analyze_products(input_data: SelectionInput) -> SelectionOutput:
    """选品分析主入口（v0.3：接入三表交叉对比引擎）"""
    try:
        category = normalize_category(input_data.category)
        top_n = input_data.top_n

        # 1. 获取商品数据（飞书 → 降级模拟）
        products = get_feishu_products(category)
        if not products:
            products = get_demo_products(category)

        if not products:
            return SelectionOutput(
                category=category,
                total_products=0,
                for_display=f"该类目「{category}」暂无商品数据，请先检查类目名称是否正确",
            )

        # 2. 获取三表交叉视图（安全降级：失败不影响主流程）
        cross_map: dict = {}
        try:
            from app.services.cross_table import get_all_cross_views
            cross_views = get_all_cross_views(category)
            for cv in cross_views:
                pid = str(cv.get("product_id", ""))
                if pid:
                    cross_map[pid] = cv.get("derived", {})
            logger.info("交叉视图加载成功: %d 个商品", len(cross_map))
        except Exception as e:
            logger.warning("交叉视图加载失败（降级继续）: %s", e)

        # 3. 边界：仅 1 个商品时不排序
        if len(products) == 1:
            p = products[0]
            pid = str(p["product_id"])
            d = cross_map.get(pid, {})
            cross_summary = _build_cross_summary(cross_map, products)
            ranking = [ProductRank(
                rank=1,
                product_id=p["product_id"],
                title=p.get("title", ""),
                price=p.get("price", 0),
                rating_rate=p.get("rating_rate", 0),
                rating_count=p.get("rating_count", 0),
                avg_daily_sales=p.get("avg_daily_sales", 0),
                explosive_index=50.0,
                price_vs_market=d.get("price_vs_market"),
                stock_health=d.get("stock_health", "未知"),
                margin_pct=d.get("margin_pct"),
            )]
            display = (
                f"【{category}】类目仅 1 个商品：{p.get('title','')} | "
                f"价格 {p.get('price',0)} 元 | "
                f"评分 {p.get('rating_rate',0)} | "
                f"日均 {p.get('avg_daily_sales',0)} 件"
            )
            if cross_summary:
                display += f"\n{cross_summary}"
            return SelectionOutput(
                category=category,
                total_products=1,
                price_distribution=compute_price_distribution(products),
                ranking=ranking,
                cross_summary=cross_summary,
                for_downstream={
                    "recommended_products": [
                        {"product_id": r.product_id, "title": r.title, "price": r.price,
                         "rating_rate": r.rating_rate, "explosive_index": r.explosive_index,
                         "price_vs_market": r.price_vs_market, "stock_health": r.stock_health,
                         "margin_pct": r.margin_pct}
                        for r in ranking
                    ],
                },
                for_display=display,
            )

        # 4. 计算爆款指数（含交叉对比维度）
        products = calculate_explosive_index(products, cross_map)

        # 5. 排序 + Top N
        products.sort(key=lambda p: p["explosive_index"], reverse=True)
        top_products = products[:top_n]

        # 6. 价格带分布
        price_dist = compute_price_distribution(products)

        # 7. 交叉对比摘要
        cross_summary = _build_cross_summary(cross_map, products)

        # 8. 构建输出
        ranking = []
        for i, p in enumerate(top_products, 1):
            pid = str(p["product_id"])
            d = cross_map.get(pid, {})
            ranking.append(ProductRank(
                rank=i,
                product_id=p["product_id"],
                title=p["title"],
                price=p["price"],
                rating_rate=p["rating_rate"],
                rating_count=p["rating_count"],
                avg_daily_sales=p["avg_daily_sales"],
                explosive_index=p["explosive_index"],
                price_vs_market=d.get("price_vs_market"),
                stock_health=d.get("stock_health", "未知"),
                margin_pct=d.get("margin_pct"),
            ))

        # 展示文本
        band_text = " | ".join(f"{b['range']}元 {b['count']}个" for b in price_dist.get("bands", []))
        ranking_lines = []
        for r in ranking:
            extra = ""
            if r.price_vs_market is not None:
                direction = "↓便宜" if r.price_vs_market < 0 else "↑贵"
                extra += f" | vs市场 {r.price_vs_market:+.0f}元{direction}"
            if r.stock_health != "未知":
                extra += f" | 库存{r.stock_health}"
            ranking_lines.append(
                f"  {r.rank}. {r.title[:30]} -- 爆款指数 {r.explosive_index} "
                f"| 评分 {r.rating_rate} | 评论 {r.rating_count} | 日均 {r.avg_daily_sales:.0f}件{extra}"
            )

        display = (
            f"【{category}】类目共 {len(products)} 个商品\n"
            f"价格分布：{band_text}\n"
            + (f"{cross_summary}\n" if cross_summary else "") +
            f"爆款 TOP{top_n}：\n" + "\n".join(ranking_lines)
        )

        ranking_reasons = []
        if cross_map:
            try:
                ranking_reasons = _llm_generate_ranking_reasons(ranking, cross_map)
            except Exception as e:
                logger.warning("LLM ranking reasons failed: %s", e)
        result = SelectionOutput(
            category=category,
            total_products=len(products),
            price_distribution=price_dist,
            ranking=ranking,
            cross_summary=cross_summary,
        for_downstream={
                "ranking_reasons": ranking_reasons,
                "recommended_products": [
                    {"product_id": r.product_id, "title": r.title, "price": r.price,
                     "rating_rate": r.rating_rate, "explosive_index": r.explosive_index,
                     "price_vs_market": r.price_vs_market, "stock_health": r.stock_health,
                     "margin_pct": r.margin_pct}
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