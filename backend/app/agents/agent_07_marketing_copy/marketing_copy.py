"""营销文案智能体（Marketing Copy）

职责：基于商品信息和定价策略，生成推广文案。
核心依赖模板生成 + 质量校验，LLM 增强为可选路径。

飞书权限：不可检索飞书  依赖 LLM：否（模板生成 + 质量校验）
"""
from __future__ import annotations
from app.utils.llm_client import chat_completion
import json
import re
from app.schemas.copy import CopyInput, CopyOutput


# -- 文案模板 ----------------------------------------------------
TEMPLATES = {
    "electronics": """🎯 **爆款推荐｜{title}**
💥 限时特惠，最低仅{price}元！
⭐ {rating}分 · {reviews}条评价 · 日均{sales}件

🏆 **为什么值得买？**
• 高评分{rating}分，品质有保障
• {reviews}位用户真实评价，口碑之选
• 日均销量{sales}件，热卖爆款

📊 **价格优势**
定价策略：{strategy_text}
原价{original_price}元，性价比出众
竞品均价{competitor_price}元

🔥 **立即行动**
限时优惠中，错过等一年！
点击购买，立即拥有！""",

    "clothing": """👗 **时尚推荐｜{title}**
✨ 限时特价仅{price}元
⭐ {rating}分 · {reviews}人已购

🎨 **产品亮点**
• 时尚百搭，品质面料
• 好评率{rating}分，深受喜爱
• {reviews}位顾客的选择

💡 **搭配建议**
{strategy_text}
原价{original_price}元，性价比之选

🛒 **立即抢购**
时尚不等人，马上入手！""",

    "jewelry": """💎 **精致之选｜{title}**
💰 特惠价仅{price}元
⭐ {rating}分 · {reviews}位顾客信赖

✨ **产品亮点**
• 精湛工艺，优雅设计
• {rating}分好评，品质认证
• {reviews}条真实评价

📦 **购买理由**
{strategy_text}
原价{original_price}元

🎁 **限时特惠**
精致生活，从这一刻开始。""",

    "default": """🎯 **推荐｜{title}**
💥 仅售{price}元
⭐ {rating}分 · {reviews}条评价

🏆 **产品亮点**
• {rating}分好评，品质保障
• {reviews}位用户推荐
• 热卖中

💡 **推荐理由**
{strategy_text}
原价{original_price}元

🔥 **立即购买**
机会有限，立即行动！""",
}

CATEGORY_MAP = {
    "electronics": "electronics", "电子": "electronics", "数码": "electronics",
    "clothing": "clothing", "服装": "clothing", "衣服": "clothing",
    "jewelry": "jewelry", "珠宝": "jewelry", "首饰": "jewelry",
}


def _get_template(category: str) -> str:
    for key in TEMPLATES:
        if key == "default":
            continue
        if category and (category.lower() == key or category.lower() in CATEGORY_MAP):
            return TEMPLATES[key]
    return TEMPLATES["default"]


def _make_highlights(product: dict, pricing: dict, profile: dict) -> list[str]:
    """提取卖点列表"""
    highlights = []
    price = product.get("current_price", 0)
    rating = product.get("rating_rate", 0)
    reviews = product.get("rating_count", 0)
    sales = product.get("avg_daily_sales", 0)

    if rating >= 4.0:
        highlights.append(f"{rating}星好评")
    if reviews > 500:
        highlights.append(f"{reviews}条评价")
    if sales > 20:
        highlights.append(f"日均{sales:.0f}件销量")
    strategy = pricing.get("strategy_summary", "")
    if "性价比" in strategy:
        highlights.append("性价比突出，价格有优势")
    elif "溢价" in strategy:
        highlights.append("品质之选，物有所值")
    tags = profile.get("preference_tags", [])
    if tags:
        highlights.append(f"适合{tags[0]}偏好用户")

    return highlights[:5]


def _quality_check(copy_text: str, input_data: dict) -> dict:
    """质量检查：校验文案中的数字是否在输入数据中出现过"""
    numbers = re.findall(r"\d+\.?\d*", copy_text)
    input_str = str(input_data)
    ignore = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "100"}
    issues = []
    for num in numbers:
        if num in ignore:
            continue
        if num not in input_str:
            issues.append(f"数字{num}未在输入数据中找到")
    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "numbers_found": len([n for n in numbers if n not in ignore]),
    }


def _get_strategy_text(pricing_info: dict) -> str:
    strategy = pricing_info.get("strategy_summary", "") or pricing_info.get("strategy", "")
    if strategy:
        strategy = strategy.split("，")[0] if "，" in strategy else strategy
        if "溢价" in strategy:
            return f"{strategy}，目标用户对品质有要求"
        elif "性价比" in strategy:
            return f"{strategy}，适合追求性价比的用户"
        elif "跟随" in strategy:
            return f"{strategy}，市场竞争力均衡"
        else:
            return strategy
    return "价格合理，性价比高"


def _llm_generate_copy(product: dict, pricing: dict, competitor: dict, profile: dict) -> str:
    """用 LLM 生成营销文案，失败时用模板"""
    from app.utils.llm_client import chat_completion
    try:
        data = f"商品：{product}\n定价：{pricing}\n竞品：{competitor}\n用户：{profile}"
        result = chat_completion(
            "你是一个电商营销文案专家。基于提供的数据生成推广文案，只使用提供的信息，不要编造数据。",
            data, temperature=0.7, max_tokens=600
        )
        return result.strip()
    except Exception:
        return ""


def generate_copy(input_data: CopyInput) -> CopyOutput:
    """营销文案主入口"""
    product = input_data.product
    pricing_info = input_data.pricing_info
    comp_info = input_data.competitor_info
    profile = input_data.user_profile

    title = product.get("title", f"商品{input_data.product_id}")
    category = product.get("category", "")
    price = product.get("current_price", 0)
    rating = product.get("rating_rate", 0)
    reviews = product.get("rating_count", 0)
    sales = product.get("avg_daily_sales", 0)
    original_price = price
    best_price = pricing_info.get("best_price", "") or pricing_info.get("suggested_best", "")
    competitor_price = comp_info.get("competitor_avg_price", "")

    title_short = title[:20]
    strategy_text = _get_strategy_text(pricing_info)

    # 选择模板
    template = _get_template(category)

    # 生成文案（LLM 优先，失败时用模板）
    llm_copy = _llm_generate_copy(product, pricing_info, comp_info, profile)
    if llm_copy:
        copy = llm_copy
    else:
        copy = template.format(
            title=title_short,
            price=price,
            rating=rating,
            reviews=reviews,
            sales=sales,
            original_price=original_price,
            best_price=best_price,
            competitor_price=competitor_price,
            strategy_text=strategy_text,
        )

    # 卖点
    highlights = _make_highlights(product, pricing_info, profile)

    # 质量检查
    qc = _quality_check(copy, {
        "product": product, "pricing_info": pricing_info,
        "competitor_info": comp_info, "user_profile": profile,
    })
    if not qc["passed"] and len(qc["issues"]) > 2:
        copy += "\n\n⚠️ 注意事项：文案中部分数据需人工核实。"

    return CopyOutput(
        product_id=input_data.product_id,
        copy_text=copy,
        highlights=highlights,
        quality_check=qc,
        for_downstream={"copy_text": copy, "highlights": highlights},
        for_display=f"📝 营销文案\n\n{copy}\n\n💡 卖点：{'、'.join(highlights)}",
    )
