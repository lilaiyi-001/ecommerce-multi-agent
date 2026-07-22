"""营销文案智能体（Marketing Copy）v0.4

职责：基于商品交叉对比数据 + 定价策略 + 竞品分析，生成专业营销文案。
v0.4：删除硬编码模板，完全 LLM 驱动，按类目定制文案风格。
"""
from __future__ import annotations
import json, re, logging
from app.schemas.copy import CopyInput, CopyOutput
from app.utils.llm_client import chat_completion
logger = logging.getLogger(__name__)

CATEGORY_STYLE = {
    "数码": "参数党风格：突出技术参数、性能对比、性价比",
    "服饰": "场景感风格：突出穿搭场景、面料质感、时尚元素",
    "食品": "味觉描述风格：突出口感、食材、健康理念",
    "美妆": "成分党风格：突出成分、功效、肤质适配",
    "家居": "生活美学风格：突出设计感、实用性、生活品质",
    "运动": "功能导向风格：突出运动性能、材质科技、使用场景",
    "文具": "效率风格：突出实用性、设计巧思、办公学习场景",
    "玩具": "趣味风格：突出可玩性、益智元素、亲子互动",
    "箱包": "格调风格：突出材质工艺、出行场景、收纳设计",
    "宠物用品": "暖心风格：突出宠物健康、安全材质、萌宠场景",
    "园艺": "自然风格：突出绿植养护、家居美化、空气净化",
}
DEFAULT_STYLE = "专业电商风格：突出产品核心卖点、数据支撑、行动号召"


def _quality_check(copy_text, input_context):
    numbers = re.findall(r"\d+\.?\d*", copy_text)
    ignore = {"0","1","2","3","4","5","6","7","8","9","10","100"}
    issues = []
    for num in numbers:
        if num in ignore: continue
        if num not in input_context:
            issues.append("数字" + num + "未在输入数据中找到")
    return {"passed": len(issues)==0, "issues": issues, "numbers_found": len([n for n in numbers if n not in ignore])}


def generate_copy(input_data: CopyInput) -> CopyOutput:
    product = input_data.product
    pricing_info = input_data.pricing_info
    comp_info = input_data.competitor_info
    profile = input_data.user_profile
    title = product.get("title", "商品")
    price = product.get("current_price", product.get("price", 0))
    rating = product.get("rating_rate", 0)
    reviews = product.get("rating_count", 0)
    sales = product.get("avg_daily_sales", 0)
    category = product.get("category", "")
    style = CATEGORY_STYLE.get(category, DEFAULT_STYLE)

    cross_context = ""
    try:
        from app.services.cross_table import get_product_cross_view
        cv = get_product_cross_view(product)
        d = cv.get("derived", {})
        if d:
            pvm = d.get("price_vs_market")
            margin = d.get("margin_pct")
            stock = d.get("stock_health", "?")
            if pvm is not None:
                direction = "低于" if pvm < 0 else "高于"
                cross_context = f"市场对比：{direction}市场均价{abs(pvm):.0f}元 | 毛利率{margin}% | 库存{stock}"
    except Exception:
        pass

    pricing_strategy = pricing_info.get("strategy_summary", "") if isinstance(pricing_info, dict) else ""
    comp_avg = comp_info.get("competitor_avg_price", "") if isinstance(comp_info, dict) else ""
    sensitivity = profile.get("price_sensitivity", "") if isinstance(profile, dict) else ""

    prompt_parts = [
        "请为以下商品撰写专业营销文案。",
        "",
        "商品：" + title,
        "售价：" + str(price) + "元 | 评分：" + str(rating) + "/5 | 评论：" + str(reviews) + " | 日均销量：" + str(sales) + "件",
        "类目：" + category,
    ]
    if cross_context:
        prompt_parts.append(cross_context)
    prompt_parts.extend([
        "定价策略：" + pricing_strategy,
        "竞品均价：" + str(comp_avg) + "元",
        "用户敏感度：" + sensitivity,
        "",
        "文案风格：" + style,
        "",
        "要求：1.痛点引入 2.产品卖点(引用数据) 3.行动号召。禁止编造数字，150字内。",
    ])
    prompt = chr(10).join(prompt_parts)

    copy_text = ""
    try:
        result = chat_completion(
            "你是电商营销文案专家，擅长" + style + "。只使用提供的真实数据。",
            prompt, temperature=0.7, max_tokens=500)
        copy_text = result.strip() if result else ""
    except Exception as e:
        logger.warning("LLM文案失败: %s", e)

    if not copy_text or len(copy_text) < 20:
        copy_text = "【" + title + "】售价仅" + str(price) + "元，" + str(rating) + "分好评，立即下单！"

    input_ctx = str([product, pricing_info, comp_info, profile, cross_context])
    qc = _quality_check(copy_text, input_ctx)

    highlights = []
    if rating >= 4.0: highlights.append(str(rating) + "分好评")
    if reviews > 500: highlights.append(str(reviews) + "条评价")
    if "低于" in cross_context: highlights.append("价格低于市场均价")

    display = "营销文案\n\n" + copy_text + "\n\n卖点：" + "、".join(highlights)

    return CopyOutput(
        product_id=input_data.product_id,
        copy_text=copy_text,
        highlights=highlights,
        quality_check=qc,
        for_downstream={"copy_text": copy_text, "highlights": highlights},
        for_display=display,
    )
