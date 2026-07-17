"""用户画像智能体（User Profile）

职责：基于用户行为数据，分析类目用户的偏好特征。
包括：价格偏好、活跃时段、转化漏斗、偏好标签。

飞书权限：可调飞书数据  依赖 LLM：部分（标签提取）
"""
from __future__ import annotations
from app.utils.llm_client import chat_completion
import statistics
from collections import Counter, defaultdict
from app.schemas.profile import ProfileInput, ProfileOutput, PricePreference, BehaviorFunnel
from app.services.data_generator import get_demo_products, generate_user_behavior
from app.services.feishu_data import get_feishu_products, get_feishu_user_behavior


TAG_KEYWORDS = {
    "存储设备": ["hard drive", "ssd", "storage", "external", "drive", "硬盘", "存储"],
    "电脑配件": ["monitor", "keyboard", "mouse", "cable", "adapter", "显示器", "键盘"],
    "服装": ["shirt", "jacket", "coat", "pant", "dress", "shoes", "服装", "衣服", "鞋"],
    "珠宝首饰": ["ring", "necklace", "bracelet", "earring", "gold", "silver", "珠宝", "首饰"],
    "户外运动": ["jacket", "snowboard", "rain", "outdoor", "sport", "运动", "户外"],
    "性价比": ["casual", "slim", "basic", "cotton", "经典", "基础"],
    "品牌商品": ["brand", "premium", "designer", "luxury", "品牌", "奢侈"],
    "数码产品": ["electronic", "digital", "wireless", "bluetooth", "充电", "无线"],
}


def _llm_extract_tags(titles: list[str]) -> list[str]:
    """用 LLM 提取偏好标签，失败时降级到关键词匹配"""
    from app.utils.llm_client import chat_completion
    try:
        prompt = f"从以下商品标题中提取用户偏好标签，只返回JSON数组，最多5个，不要编造数据：{titles}"
        result = chat_completion(
            "你是一个电商用户画像分析助手。只从提供的数据中提取标签，不要编造。",
            prompt, temperature=0.1, max_tokens=300
        )
        import re
        arr = re.search(r'\[.*?\]', result, re.DOTALL)
        if arr:
            tags = json.loads(arr.group())
            return [t for t in tags if isinstance(t, str)][:5]
    except Exception:
        pass
    return []


def _extract_tags(titles: list[str]) -> list[str]:
    """从商品标题中提取偏好标签"""
    found = set()
    for title in titles:
        lower = title.lower()
        for tag, keywords in TAG_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in lower:
                    found.add(tag)
                    break
    return list(found)[:5]


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


def analyze_profile(input_data: ProfileInput) -> ProfileOutput:
    """用户画像主入口"""
    category = input_data.category

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

    # 热门商品
    view_counts = Counter(b["product_idx"] for b in views)
    top3 = view_counts.most_common(3)
    top_products = []
    for idx, count in top3:
        if idx < len(products):
            top_products.append({
                "product_id": products[idx]["product_id"],
                "title": products[idx]["title"],
                "view_count": count,
            })

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
        "top_viewed_products": top_products,
    }

    # 展示文本
    display = (
        f"【{category}】用户画像\n"
        f"共分析 {total_users} 个用户、{total_records} 条行为记录\n"
        f"价格偏好：{most_viewed_band or '未知'} 元区间最受欢迎，敏感度{price_sensitivity}\n"
        f"活跃时段：晚{peak_hours[0]}-{peak_hours[-1]}点\n"
        f"转化漏斗：浏览→加购 {bf.view_to_cart_rate}，加购→购买 {bf.cart_to_purchase_rate}\n"
        f"偏好标签：{'、'.join(tags) if tags else '暂无'}"
    )

    return ProfileOutput(
        category=category,
        total_users=total_users,
        total_behavior_records=total_records,
        profile=profile,
        for_downstream={
            "price_sensitivity": price_sensitivity,
            "avg_order_price": avg_order,
            "peak_hours": peak_hours,
            "preference_tags": tags,
        },
        for_display=display,
    )
