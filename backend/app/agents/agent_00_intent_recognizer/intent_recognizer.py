"""意图识别智能体（Intent Recognizer）

职责：接收用户自然语言输入，做语义解析和意图分类，输出结构化任务描述。
这是整个流程的第一步——用户说人话，这个智能体负责翻译成"机器能懂的结构化指令"。

核心逻辑（三步法）：
  步骤1：LLM 从用户消息中提取关键信息（类目、数量、动作等）
          若 LLM 不可用（限流/超时），降级为规则引擎提取
  步骤2：将提取的信息映射到预定义的任务类型枚举
  步骤3：校验输出，确保所有必需字段都已填充

飞书权限：不可检索飞书内容
"""
from __future__ import annotations
import json
import re
import logging
from typing import Optional
from app.schemas.intent import (
    IntentInput, IntentOutput, ParsedIntent, IntentCategory,
)
from app.utils.llm_client import chat_completion

logger = logging.getLogger(__name__)


# ── 可执行的任务类型枚举 ──────────────────────────────────────────
ALL_TASKS = {
    "product_selection": "选品分析",
    "trend_forecast": "趋势预测",
    "user_profile": "用户画像",
    "competitor_analysis": "竞品分析",
    "pricing_strategy": "定价策略",
    "inventory_advice": "补货/清仓建议",
    "marketing_copy": "营销文案",
    "promotion_plan": "活动策划",
}

# 同义词 → 标准任务名映射
TASK_SYNONYMS = {
    "选品": "product_selection", "选品分析": "product_selection",
    "爆款": "product_selection", "推荐商品": "product_selection",
    "趋势": "trend_forecast", "趋势预测": "trend_forecast",
    "销量预测": "trend_forecast", "销量趋势": "trend_forecast",
    "销量走势": "trend_forecast", "走势": "trend_forecast",
    "用户画像": "user_profile", "画像": "user_profile", "用户分析": "user_profile",
    "竞品": "competitor_analysis", "竞品分析": "competitor_analysis",
    "竞争对手": "competitor_analysis", "对比": "competitor_analysis",
    "定价": "pricing_strategy", "定价策略": "pricing_strategy",
    "价格": "pricing_strategy", "报价": "pricing_strategy",
    "补货": "inventory_advice", "清仓": "inventory_advice",
    "库存": "inventory_advice", "备货": "inventory_advice",
    "文案": "marketing_copy", "营销文案": "marketing_copy",
    "广告语": "marketing_copy", "推广": "marketing_copy",
    "活动": "promotion_plan", "促销": "promotion_plan",
    "活动策划": "promotion_plan",
}

# 领域关键词（用于规则降级）
CATEGORY_KEYWORDS = {
    "食品": ["food", "食品", "美食", "零食", "饮料", "吃"],
    "服饰": ["clothing", "服装", "衣服", "服饰", "穿搭", "穿", "clothes"],
    "家居": ["home", "家居", "家具", "家装", "厨房", "日用", "生活"],
    "数码": ["electronics", "电子", "数码", "电脑", "手机", "3c", "科技"],
    "园艺": ["garden", "园艺", "花卉", "绿植", "盆栽", "种植", "花"],
    "宠物用品": ["pet", "宠物", "猫", "狗", "宠物用品", "pets", "萌宠"],
    "文具": ["stationery", "文具", "办公", "笔", "本", "书", "books", "图书", "学习"],
    "箱包": ["bags", "箱包", "包", "背包", "行李箱", "书包", "旅行"],
}

# 意图类别 → 默认任务列表
INTENT_DEFAULT_TASKS = {
    IntentCategory.PRODUCT_ANALYSIS: [
        "product_selection", "trend_forecast", "user_profile",
        "competitor_analysis", "pricing_strategy", "inventory_advice",
        "marketing_copy", "promotion_plan",
    ],
    IntentCategory.TREND_QUERY: ["trend_forecast"],
    IntentCategory.PRICING_ADVICE: ["pricing_strategy", "competitor_analysis"],
    IntentCategory.MARKETING_COPY: ["marketing_copy", "competitor_analysis"],
    IntentCategory.PROMOTION_PLAN: ["promotion_plan", "pricing_strategy"],
    IntentCategory.INVENTORY_ADVICE: ["inventory_advice", "trend_forecast"],
    IntentCategory.GENERAL_QUERY: [],
}


# ── 提示词模板 ──────────────────────────────────────────────────
SYSTEM_PROMPT = """你是一个电商选品运营系统的意图识别助手。
请从用户的输入中提取关键信息，并以 JSON 格式返回。

可提取的字段：
- category: 用户提到的类目名称（如 electronics、clothing），如果没提到则为 null
- top_n: 用户希望推荐的商品数量（数字），如果没提到则为 null
- time_range: 时间范围描述（如"近30天"），如果没提到则为 null
- mentioned_tasks: 用户明确提到的任务关键词列表，从以下列表中匹配：
  ["选品","选品分析","爆款","推荐商品","趋势","趋势预测","销量预测",
   "用户画像","画像","用户分析","竞品","竞品分析","竞争对手",
   "定价","定价策略","价格","补货","清仓","库存",
   "文案","营销文案","广告语","活动","促销","活动策划"]
- action: 用户的主要动作意图（如"分析"、"推荐"、"写"、"策划"等）

重要原则：
1. 只提取用户明确提到的信息，不要编造
2. 如果用户没提到某个字段，就返回 null
3. 对于 category，如果用户说的是中文类目名（如"电子产品"），直接使用中文
4. 用户说的所有内容都必须保留，不要遗漏

请只返回 JSON，不要加其他文字。"""


def _rule_based_extract(user_message: str) -> dict:
    """降级方案：基于关键词和正则的规则引擎提取"""
    text = user_message.lower()
    result = {
        "category": None,
        "top_n": None,
        "time_range": None,
        "mentioned_tasks": [],
        "action": None,
    }

    # 1. 提取类目
    for eng_name, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                # 用原始输入中的匹配文本来保留用户原文
                idx = user_message.lower().find(kw)
                if idx >= 0:
                    end = idx + len(kw)
                    result["category"] = user_message[idx:end]
                else:
                    result["category"] = eng_name
                break
        if result["category"]:
            break

    # 2. 提取推荐数量（如"3个"、"5个"、"推荐3个"）
    top_n_match = re.search(r"[推荐]?(\d+)\s*个", user_message)
    if top_n_match:
        result["top_n"] = int(top_n_match.group(1))

    # 3. 提取时间范围
    time_match = re.search(r"[近最]?(\d+)\s*(天|周|月|年)", user_message)
    if time_match:
        result["time_range"] = time_match.group(0)

    # 4. 提取提及的任务
    for kw, std_task in TASK_SYNONYMS.items():
        if kw in user_message and std_task not in result["mentioned_tasks"]:
            result["mentioned_tasks"].append(kw)

    # 5. 提取动作
    action_keywords = {
        "分析": "分析", "推荐": "推荐", "写": "写", "策划": "策划",
        "制定": "制定", "预测": "预测", "预估": "预测", "比较": "比较",
        "对比": "比较", "看看": "看看", "找": "推荐", "搜索": "推荐",
    }
    for kw, action in action_keywords.items():
        if kw in user_message:
            result["action"] = action
            break

    return result


def _llm_extract(user_message: str, history: str = "") -> dict:
    """步骤1：优先 LLM 提取，失败则降级到规则引擎"""
    try:
        full_message = user_message
        if history:
            full_message = f"对话历史：{history}\n\n当前消息：{user_message}"
        result = chat_completion(SYSTEM_PROMPT, full_message, temperature=0.1)
        try:
            start = result.index("{")
            end = result.rindex("}")
            return json.loads(result[start:end+1])
        except (ValueError, json.JSONDecodeError):
            logger.warning("LLM 返回非 JSON 格式，降级到规则引擎")
            return _rule_based_extract(user_message)
    except Exception as e:
        logger.warning(f"LLM 调用失败 ({type(e).__name__})，降级到规则引擎: {e}")
        return _rule_based_extract(user_message)


def _determine_intent_category(extracted: dict) -> tuple[IntentCategory, float]:
    """步骤2：确定意图类别和置信度"""
    mentioned = extracted.get("mentioned_tasks") or []
    action = extracted.get("action", "")

    task_set = set()
    for kw in mentioned:
        std = TASK_SYNONYMS.get(kw)
        if std:
            task_set.add(std)

    total_mentioned = len(task_set)

    # 优先级1: 提到2个以上任务 → 全链路产品分析
    if total_mentioned >= 2:
        return IntentCategory.PRODUCT_ANALYSIS, 0.85
    # 优先级2: 提到选品/爆款 → 产品分析
    if "product_selection" in task_set:
        return IntentCategory.PRODUCT_ANALYSIS, 0.80
    if "user_profile" in task_set:
        return IntentCategory.PRODUCT_ANALYSIS, 0.75
    # 优先级3: 动作是"分析/推荐"但没有明确任务 → 产品分析
    if action in ("分析", "推荐") and not task_set:
        return IntentCategory.PRODUCT_ANALYSIS, 0.70
    # 优先级4: 单个明确任务
    if "trend_forecast" in task_set:
        return IntentCategory.TREND_QUERY, 0.85
    if "pricing_strategy" in task_set:
        return IntentCategory.PRICING_ADVICE, 0.85
    if "marketing_copy" in task_set:
        return IntentCategory.MARKETING_COPY, 0.85
    if "promotion_plan" in task_set:
        return IntentCategory.PROMOTION_PLAN, 0.85
    if "inventory_advice" in task_set:
        return IntentCategory.INVENTORY_ADVICE, 0.85
    # 优先级5: 模糊查询
    if action in ("看看", "查查", "有什么"):
        return IntentCategory.GENERAL_QUERY, 0.50

    return IntentCategory.GENERAL_QUERY, 0.30


def _map_tasks(intent: IntentCategory, extracted: dict) -> list[str]:
    """根据意图和提取的信息确定需要执行的任务列表

    策略：
    - 用户明确提到具体任务（如"推荐爆款""写文案"）→ 轻量模式：仅该任务+直接依赖
    - 用户模糊说"帮我分析"无具体任务 → 完整模式：意图默认任务全量
    """
    mentioned = extracted.get("mentioned_tasks") or []
    defaults = INTENT_DEFAULT_TASKS.get(intent, [])

    tasks = set()
    for kw in mentioned:
        std = TASK_SYNONYMS.get(kw)
        if std:
            tasks.add(std)

    # 轻量模式：用户明确提了具体任务，只跑这些+直接依赖，不补默认任务
    if tasks and len(tasks) <= 2:
        import logging
        logging.getLogger(__name__).info(
            "轻量模式：用户提到 %s，仅执行 %s + 直接依赖",
            mentioned, list(tasks),
        )
        return list(tasks)

    # 完整模式：用户没说具体任务，跑意图默认全量
    for t in defaults:
        tasks.add(t)

    return list(tasks)


def _validate(intent: ParsedIntent) -> str:
    """步骤3：校验，返回给用户的提示或空字符串"""
    if intent.confidence < 0.4:
        return ("您的需求不够具体，请告诉我：\n"
                "① 要分析哪个类目？\n"
                "② 需要推荐几个商品？\n"
                "③ 需要哪些服务（如定价、文案、促销等）？")
    if not intent.extracted_params.get("category") and intent.confidence < 0.7:
        return ("请告诉我要分析哪个类目（如 electronics、clothing 等），"
                "这样我才能帮您做更精准的分析。")
    return ""


def recognize_intent(input_data: IntentInput) -> IntentOutput:
    """意图识别主入口"""
    history_text = ""
    if input_data.conversation_history:
        recent = input_data.conversation_history[-4:]
        history_text = " | ".join(
            f"{h.get('role','?')}: {h.get('content','')}" for h in recent
        )

    # 步骤1：LLM 提取（带降级）
    extracted = _llm_extract(input_data.user_message, history_text)

    # 步骤2：确定意图
    intent_cat, confidence = _determine_intent_category(extracted)
    required_tasks = _map_tasks(intent_cat, extracted)

    params = {}
    if extracted.get("category"):
        params["category"] = extracted["category"]
    if extracted.get("top_n"):
        params["top_n"] = extracted["top_n"]
    if extracted.get("time_range"):
        params["time_range"] = extracted["time_range"]

    parsed = ParsedIntent(
        intent_category=intent_cat,
        confidence=confidence,
        extracted_params=params,
        required_tasks=required_tasks,
        task_description=(
            f"分析 {params.get('category','?')} 类目"
            f"{'，推荐' + str(params['top_n']) + '个' if params.get('top_n') else ''}"
            f"，执行任务: {', '.join(ALL_TASKS.get(t, t) for t in required_tasks)}"
        ),
    )

    # 步骤3：校验
    hint = _validate(parsed)

    if hint:
        display = hint
    else:
        cat = params.get("category", "指定")
        top = params.get("top_n", "")
        tasks_str = "、".join(ALL_TASKS.get(t, t) for t in required_tasks)
        display = (
            f"已理解您的需求：分析 {cat} 类目"
            f"{'，推荐' + str(top) + '个商品' if top else ''}"
            f"{'，执行' + tasks_str if tasks_str else ''}。"
        )

    return IntentOutput(
        agent_name="intent_recognizer",
        session_id=input_data.session_id,
        turn_number=input_data.turn_number,
        parsed_result=parsed,
        for_downstream={
            "category": params.get("category"),
            "top_n": params.get("top_n"),
            "required_tasks": required_tasks,
            "task_description": parsed.task_description,
        },
        for_display=display,
    )



