"""安全兜底拦截 —— 检索质量不足时跳过 LLM 生成，用模板回复。

防止 LLM 在信息不足时编造房源信息（幻觉）。

触发条件：
1. 候选房源数为 0
2. 最高检索分数低于阈值
3. 所有放宽级别后仍无结果
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# 阈值配置
MIN_CONFIDENCE = 0.3  # 最高检索分低于此值 → 兜底
MIN_RESULT_COUNT = 1  # 结果数为 0 → 兜底

# 放宽级别的中文描述
RELAXATION_LABELS: dict[int, str] = {
    0: "未放宽",
    1: "已放宽房源类型",
    2: "已放宽户型和类型",
    3: "预算上限已扩大 20%",
}

# 筛选字段的中文标签
FILTER_LABELS: dict[str, str] = {
    "district": "区域",
    "price_min": "最低预算",
    "price_max": "最高预算",
    "bedrooms": "户型（卧室数）",
    "property_type": "房源类型",
}

# 房源类型中文映射
TYPE_LABELS: dict[str, str] = {
    "studio": "单间", "1-bed": "一室", "2-bed": "两室+", "shared": "合租", "house": "别墅",
    "house": "别墅",
    "studio": "单间",
    "shared": "合租",
}


class SafeFallback:
    """LLM 安全兜底检查与模板生成"""

    def should_fallback(
        self,
        documents: list[Any],
        top_score: float,
        relaxation_level: int,
    ) -> bool:
        """判断是否应该跳过 LLM，直接返回兜底模板。

        Args:
            documents: 检索到的文档/房源列表
            top_score: 最高检索分数
            relaxation_level: 当前放宽级别
        """
        if not documents:
            logger.info("安全兜底：无搜索结果，relaxation_level=%d", relaxation_level)
            return True

        if top_score < MIN_CONFIDENCE and relaxation_level >= 2:
            # 放宽两轮后仍然分数很低 → 数据确实不够
            logger.info(
                "安全兜底：检索质量不足，top_score=%.4f, relaxation_level=%d",
                top_score,
                relaxation_level,
            )
            return True

        return False

    def build_fallback_response(
        self,
        query: str,
        active_filters: dict[str, Any],
        relaxation_level: int,
    ) -> str:
        """生成兜底回复，包含当前条件和具体建议。

        Args:
            query: 用户原始输入
            active_filters: 当前生效的筛选条件
            relaxation_level: 已尝试的放宽级别
        """
        lines = ["抱歉，在当前条件下没有找到匹配的房源。\n"]

        # 当前条件
        if active_filters:
            lines.append("**当前条件：**")
            for key, label in FILTER_LABELS.items():
                value = active_filters.get(key)
                if value is not None and value != "":
                    if key == "property_type":
                        value = TYPE_LABELS.get(str(value), str(value))
                    elif key in ("price_min", "price_max"):
                        value = f"¥{int(value):,}"
                    lines.append(f"  · {label}: {value}")

        # 放宽情况
        if relaxation_level > 0:
            status = RELAXATION_LABELS.get(
                relaxation_level, f"已尝试 {relaxation_level} 级放宽"
            )
            lines.append(f"\n已尝试放宽: {status}")

        # 建议
        lines.append("\n**建议：**")
        suggestions = self._build_suggestions(active_filters, relaxation_level)
        for i, s in enumerate(suggestions, 1):
            lines.append(f"  {i}. {s}")

        lines.append("\n您想尝试哪种调整？")

        return "\n".join(lines)

    def _build_suggestions(
        self,
        filters: dict[str, Any],
        relaxation_level: int,
    ) -> list[str]:
        """根据当前条件生成具体的放宽建议"""
        suggestions: list[str] = []

        has_price_max = filters.get("price_max") is not None and relaxation_level < 3
        has_bedrooms = filters.get("bedrooms") is not None
        has_property_type = filters.get("property_type") is not None
        has_district = filters.get("district") is not None

        if has_price_max:
            current = float(filters["price_max"])
            expanded = int(current * 1.2)
            suggestions.append(f"将预算上限提高到 ¥{expanded:,}（当前放宽 20%）")

        if has_district and not suggestions:
            suggestions.append("扩大搜索区域范围（如邻近区域）")

        if has_bedrooms:
            current_bed = filters["bedrooms"]
            if current_bed and current_bed > 0:
                suggestions.append(f"放宽户型要求（当前限定 {current_bed} 室）")

        if has_property_type:
            suggestions.append("考虑其他房源类型（合租、单间等）")

        if not suggestions:
            suggestions.append("扩大搜索区域范围")
            suggestions.append("放宽预算和户型条件")

        return suggestions[:4]  # 最多 4 条建议


def build_fallback_response(
    query: str,
    active_filters: dict[str, Any],
    relaxation_level: int,
) -> str:
    """便捷函数：生成兜底回复"""
    return SafeFallback().build_fallback_response(query, active_filters, relaxation_level)
