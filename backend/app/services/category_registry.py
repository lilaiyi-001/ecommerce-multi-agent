"""类目注册中心 — 统一管理类目名中英文映射

职责：
- 定义标准中文类目名（对齐飞书 Bitable 实际字段值）
- 保留英文别名映射，兼容历史 API 输入
- 所有模块通过此模块获取类目名，避免硬编码
"""
from __future__ import annotations

# 标准中文类目 → 英文别名列表（对齐飞书 Bitable 实际类目）
CATEGORY_MAP: dict[str, list[str]] = {
    "食品": ["food", "食品", "美食", "零食", "饮料"],
    "服饰": ["clothing", "服装", "衣服", "服饰", "穿搭", "clothes"],
    "家居": ["home", "家居", "家具", "家装", "厨房", "日用"],
    "数码": ["electronics", "电子", "数码", "电脑", "手机", "3c", "电子产品"],
    "园艺": ["garden", "园艺", "花卉", "绿植", "盆栽", "种植"],
    "宠物用品": ["pet", "宠物", "猫", "狗", "宠物用品", "pets"],
    "文具": ["stationery", "文具", "办公", "笔", "本", "书", "books", "图书"],
    "箱包": ["bags", "箱包", "包", "背包", "行李箱", "书包", "旅行"],
    # 新增：来自库存/爬取数据表格的类目
    "美妆": ["beauty", "美妆", "化妆品", "护肤", "彩妆", "化妆", "美容"],
    "运动": ["sports", "运动", "健身", "户外", "体育", "跑步", "瑜伽"],
    "玩具": ["toys", "玩具", "积木", "乐高", "娃娃", "模型", "遥控", "拼图"],
}

# 反向映射：任意别名 → 标准中文类目名
_ALIAS_TO_CATEGORY: dict[str, str] = {}
for _cat, _aliases in CATEGORY_MAP.items():
    _ALIAS_TO_CATEGORY[_cat] = _cat
    for _a in _aliases:
        _ALIAS_TO_CATEGORY[_a.lower()] = _cat


def normalize_category(raw: str) -> str:
    """将任意类目名转换为标准中文类目名"""
    if not raw:
        return ""
    cleaned = raw.strip()
    return _ALIAS_TO_CATEGORY.get(cleaned.lower(), cleaned)


def get_standard_categories() -> list[str]:
    """获取所有标准中文类目名列表"""
    return list(CATEGORY_MAP.keys())


def get_aliases(category: str) -> list[str]:
    """获取某个标准类目的所有别名"""
    std = normalize_category(category)
    return CATEGORY_MAP.get(std, [category])
