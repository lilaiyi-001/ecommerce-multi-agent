"""用户画像智能体（User Profile）v0.3

职责：基于用户行为数据 + 库存销量数据 + 爬取市场评分，
分析类目用户的偏好特征，包括价格敏感度、购买力、品类偏好。

飞书权限：可调飞书数据
依赖 LLM：部分（标签提取 + 画像总结）
"""
from __future__ import annotations
import json
import logging
import statistics
from collections import Counter
from app.schemas.profile import ProfileInput, ProfileOutput, BehaviorFunnel
from app.services.data_generator import get_demo_products, generate_user_behavior
from app.services.feishu_data import get_feishu_products
from app.services.category_registry import normalize_category

logger = logging.getLogger(__name__)

TAG_KEYWORDS = {
    "存储设备": ["hard drive", "ssd", "storage", "硬盘", "存储"],
    "电脑配件": ["monitor", "keyboard", "mouse", "显示器", "键盘"],
    "服饰": ["shirt", "jacket", "coat", "dress", "服饰", "衣服"],
    "珠宝首饰": ["ring", "necklace", "bracelet", "珠宝", "首饰"],
    "户外运动": ["jacket", "snowboard", "outdoor", "运动", "户外"],
    "性价比": ["casual", "basic", "cotton", "经典", "基础"],
    "品牌商品": ["brand", "premium", "luxury", "品牌", "奢侈"],
    "数码产品": ["electronic", "wireless", "bluetooth", "充电", "无线"],
}


def _extract_tags(titles: list[str]) -> list[str]:
    """从商品标题中提取偏好标签"""
    found: set = set()
    for title in titles:
        lower = title.lower()
        for tag, keywords in TAG_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in lower:
                    found.add(tag)
                    break
    return list(found)[:5]


def _llm_extract_tags(titles: list[str]) -> list[str]:
    """LLM 提取偏好标签，失败时降级"""
    try:
        from app.utils.llm_client import chat_completion
        import re
        prompt = f"从以下商品标题中提取用户偏好标签，只返回JSON数组，最多5个：{titles}"
        result = chat_completion(
            "你是电商用户画像分析助手。只从提供的数据中提取标签，不编造。",
            prompt, temperature=0.1, max_tokens=300
        )
        arr = re.search(r'\[.*?\]', result, re.DOTALL)
        if arr:
            return [t for t in json.loads(arr.group()) if isinstance(t, str)][:5]
    except Exception:
        pass
    return []


def _calc_price_sensitivity(prices: list[float]) -> str:
    """根据价格分布估算价格敏感度"""
    if len(prices) < 5:
        return "中等"
    avg = sum(prices) / len(prices)
    std = statistics.stdev(prices)
    cv = std / avg if avg > 0 else 0
    if cv > 0.6:
        return "高（价格跨度大，用户比价行为多）"
    elif cv < 0.2:
        return "低（价格集中，用户对价格不敏感）"
    return "中等"


def _format_pct(a: int, b: int) -> str:
    if b == 0:
        return "0%"
    return f"{a * 100 // b}%"


def _llm_summarize_profile(profile_data: dict, cross_data: dict) -> str:
    """LLM 生成用户画像总结"""
    if not profile_data and not cross_data:
        return ""
    prompt = (
        f"用户画像数据：{json.dumps(profile_data, ensure_ascii=False)}\n"
        f"交叉数据（库存+市场）：{json.dumps(cross_data, ensure_ascii=False)}\n"
        "请用 2-3 句话总结该类目用户的画像特征和购买行为模式。"
    )
    try:
        from app.utils.llm_client import chat_completion
        result = chat_completion(
            "你是电商用户画像分析专家。输出简洁的用户画像总结。",
            prompt, temperature=0.3, max_tokens=300
        )
        return result.strip() if result else ""
    except Exception as e:
        logger.warning("LLM 画像总结失败: %s", e)
        return ""


def analyze_profile(input_data: ProfileInput) -> ProfileOutput:
    """用户画像主入口（v0.3：注入库存+爬取双表交叉数据）"""
    category = normalize_category(input_data.category)

    # 1. 获取用户行为数据（模拟）
    behaviors = generate_user_behavior(category, num_users=150)
    if not behaviors:
        return ProfileOutput(category=category, for_display=f"暂无「{category}」类目的用户行为数据")

    total_records = len(behaviors)
    total_users = len(set(b["user_id"] for b in behaviors))
    products = get_feishu_products(category) or get_demo_products(category)

    # 2. 各维度分析
    views = [b for b in behaviors if b["behavior"] == "view"]
    carts = [b for b in behaviors if b["behavior"] == "cart"]
    purchases = [b for b in behaviors if b["behavior"] == "purchase"]

    # 价格偏好
    viewed_prices = [b["price"] for b in views]
    purchase_prices = [b["price"] for b in purchases]
    avg_order = round(sum(purchase_prices) / len(purchase_prices), 2) if purchase_prices else 0

    most_viewed_band = ""
    if viewed_prices:
        pmin, pmax = min(viewed_prices), max(viewed_prices)
        step = (pmax - pmin) / 4 if pmax > pmin else 1
        bands = Counter()
        for p in viewed_prices:
            idx = min(int((p - pmin) / step), 3)
            lo = round(pmin + idx * step, 0)
            hi = round(pmin + (idx + 1) * step, 0)
            bands[f"{lo:.0f}-{hi:.0f}"] += 1
        most_viewed_band = bands.most_common(1)[0][0] if bands else ""

    price_sensitivity = _calc_price_sensitivity(viewed_prices)

    # 活跃时段
    hour_counts = Counter(b["hour"] for b in views)
    peak_hours = [h for h, _ in hour_counts.most_common(3)]
    peak_hours.sort()

    # 转化漏斗
    bf = BehaviorFunnel(
        view_count=len(views),
        cart_count=len(carts),
        purchase_count=len(purchases),
        view_to_cart_rate=_format_pct(len(carts), len(views)),
        cart_to_purchase_rate=_format_pct(len(purchases), len(carts)),
    )

    # 偏好标签
    viewed_titles = list(set(b["title"] for b in views))
    llm_tags = _llm_extract_tags(viewed_titles)
    tags = llm_tags if llm_tags else _extract_tags(viewed_titles)

    # ---- 交叉数据注入：库存销量 + 爬取评分 ----
    data_sources = ["用户行为模拟"]
    purchase_power = "中等"
    category_pref: dict = {}

    try:
        from app.services.cross_table import get_all_cross_views
        cross_views = get_all_cross_views(category)
        if cross_views:
            data_sources.append(f"交叉对比({len(cross_views)}商品)")

            # 从库存表推断购买力：看售价分布和销量
            all_prices: list[float] = []
            total_sales = 0
            for cv in cross_views:
                master = cv.get("master", {})
                inv = cv.get("inventory")
                if master.get("price"):
                    all_prices.append(master["price"])
                if inv:
                    total_sales += inv.get("cumulative_sales", 0)

            if all_prices:
                avg_price = sum(all_prices) / len(all_prices)
                if avg_price > 200:
                    purchase_power = "高"
                elif avg_price > 80:
                    purchase_power = "中等"
                else:
                    purchase_power = "低"

            # 类目偏好分布（从爬取表评分分布推断）
            rating_dist = Counter()
            for cv in cross_views:
                cr = cv.get("crawled")
                if cr and cr.get("rating"):
                    band = f"{int(cr['rating'])}-{int(cr['rating']) + 1}分"
                    rating_dist[band] += 1
            if rating_dist:
                category_pref = dict(rating_dist.most_common(5))
    except Exception as e:
        logger.warning("用户画像-交叉数据加载失败: %s", e)

    # ---- LLM 画像总结 ----
    cross_summary_data = {
        "purchase_power": purchase_power,
        "category_preference": category_pref,
    }
    profile_llm_summary = _llm_summarize_profile({
        "price_sensitivity": price_sensitivity,
        "avg_order_price": avg_order,
        "preference_tags": tags,
    }, cross_summary_data)

    # 构建输出
    profile = {
        "price_preference": {
            "most_viewed_price_band": most_viewed_band or "未知",
            "avg_order_price": avg_order,
            "price_sensitivity": price_sensitivity,
        },
        "active_hours": {
            "peak_hours": peak_hours,
            "peak_description": f"晚{peak_hours[0]}-{peak_hours[-1]}点是浏览和下单高峰" if peak_hours else "",
        },
        "behavior_funnel": bf.model_dump(),
        "preference_tags": tags,
        "llm_summary": profile_llm_summary,
    }

    display = (
        f"【{category}】用户画像\n"
        f"共分析 {total_users} 个用户、{total_records} 条行为记录\n"
        f"数据源：{' + '.join(data_sources)}\n"
        f"购买力：{purchase_power} | 价格敏感度：{price_sensitivity}\n"
        f"活跃时段：晚{peak_hours[0]}-{peak_hours[-1]}点\n"
        f"转化漏斗：浏览→加购 {bf.view_to_cart_rate}，加购→购买 {bf.cart_to_purchase_rate}\n"
        f"偏好标签：{', '.join(tags) if tags else '暂无'}"
    )
    if profile_llm_summary:
        display += f"\n\n画像总结：{profile_llm_summary}"

    return ProfileOutput(
        category=category,
        total_users=total_users,
        total_behavior_records=total_records,
        profile=profile,
        purchase_power=purchase_power,
        category_preference=category_pref,
        data_sources_used=data_sources,
        for_downstream={
            "price_sensitivity": price_sensitivity.split("（")[0] if "（" in price_sensitivity else price_sensitivity,
            "avg_order_price": avg_order,
            "peak_hours": peak_hours,
            "preference_tags": tags,
            "purchase_power": purchase_power,
            "category_preference": category_pref,
        },
        for_display=display,
    )