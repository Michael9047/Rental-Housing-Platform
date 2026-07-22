"""货币服务 —— 汇率换算 + 币种检测

设计原则：
- 数据库存原始币种金额（GBP/SGD/CNY等）
- 用户未指定币种 → 默认当地币种，不做换算
- 用户指定了不同币种 → 自动换算为房源币种
"""
from __future__ import annotations

import re
from typing import Any

# ── 汇率表（以 CNY 为基准，每月更新一次） ──
# 格式：1 单位外币 = X CNY
RATES_TO_CNY: dict[str, float] = {
    "CNY": 1.0,
    "GBP": 9.30,   # 1 GBP = 9.30 CNY
    "SGD": 5.40,   # 1 SGD = 5.40 CNY
    "USD": 7.25,   # 1 USD = 7.25 CNY
    "HKD": 0.93,   # 1 HKD = 0.93 CNY
}

# ── 币种符号映射 ──
CURRENCY_SYMBOLS: dict[str, str] = {
    "CNY": "¥",
    "GBP": "£",
    "SGD": "S$",
    "USD": "$",
    "HKD": "HK$",
}

# ── 币种检测正则（用户消息中的币种关键词） ──
# 重要：顺序从具体到模糊，避免 "元/块/$" 等通用字符误匹配
# 先匹配具体币种（GBP/SGD/USD/HKD），最后才匹配 CNY
CURRENCY_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("GBP", re.compile(r"英镑|镑|GBP|£", re.IGNORECASE)),
    ("SGD", re.compile(r"新币|新加坡元|新元|坡币|SGD|S\$", re.IGNORECASE)),
    ("USD", re.compile(r"美元|美金|美刀|USD|[0-9]刀", re.IGNORECASE)),
    ("HKD", re.compile(r"港币|港元|港纸|HKD|HK\$", re.IGNORECASE)),
    ("CNY", re.compile(r"人民币|RMB|CNY|¥|元|块", re.IGNORECASE)),
    # $ 单独处理：如果前面没被 USD/SGD/HKD 匹配到，且消息中有数字+$，默认为 USD
    ("USD", re.compile(r"\$[0-9]|[0-9]\s*\$")),
]


def convert(amount: float, from_currency: str, to_currency: str) -> float:
    """货币换算。from → CNY → to。"""
    if from_currency == to_currency:
        return amount
    if from_currency not in RATES_TO_CNY or to_currency not in RATES_TO_CNY:
        return amount  # 未知币种，不换算
    cny = amount * RATES_TO_CNY[from_currency]
    return round(cny / RATES_TO_CNY[to_currency])


def detect_currency(message: str) -> str | None:
    """从用户消息中检测币种意图。返回币种代码或 None。"""
    for currency, pattern in CURRENCY_PATTERNS:
        if pattern.search(message):
            return currency
    return None


def get_symbol(currency: str) -> str:
    """获取币种符号，默认 ¥。"""
    return CURRENCY_SYMBOLS.get(currency, "¥")


def resolve_search_price(
    user_message: str,
    price_value: float | None,
    property_currency: str | None,
) -> float | None:
    """解析搜索价格：根据用户币种意图换算。

    流程：
    1. 检测用户消息中的币种
    2. 如果用户指定了币种且与房源币种不同 → 换算
    3. 如果用户未指定 → 原样返回（默认当地币种）

    返回换算后的价格（以 property_currency 为单位），或 None。
    """
    if price_value is None:
        return None
    if not property_currency:
        return price_value

    user_currency = detect_currency(user_message)
    if user_currency and user_currency != property_currency:
        return convert(price_value, user_currency, property_currency)

    return price_value
