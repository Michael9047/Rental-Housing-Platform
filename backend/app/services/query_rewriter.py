"""查询改写循环 —— 结果质量不足时用 LLM 改写查询，重新检索。

两阶段改写：
1. 短查询确定性扩展（不用 LLM）："便宜一点的" → 结合 active_filters 推断
2. LLM 改写：将模糊的相对描述转化为精确的搜索条件

循环守卫：最多改写 N 次，每次比对结果是否有提升。
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.score_gap import DEFAULT_GAP_RATIO, detect_score_gap

logger = logging.getLogger(__name__)

MAX_REWRITES = 2
MIN_RESULT_IMPROVEMENT = 3  # 结果数至少增加这么多才算有效改写

REWRITE_SYSTEM_PROMPT = """你是租房搜索查询改写助手。用户在多轮对话中调整需求，你需要把模糊的相对描述转化为精确的搜索条件。

当前筛选条件: {active_filters}
用户原始消息: {query}
当前结果数: {result_count}

用户可能是在：
- 缩小范围："便宜一点的""小一点的"
- 扩大范围："贵一点也行""大一点的"
- 改变条件："换到 B 区""不要合租"

请输出 JSON，只包含需要修改的字段（不需要修改的不要输出）:
{{"district": null 或 "新区域", "price_min": null 或 新最低价(整数), "price_max": null 或 新最高价(整数), "bedrooms": null 或 新卧室数(整数), "property_type": null 或 "apartment/house/studio/shared", "reasoning": "改写理由"}}

重要规则：
- "便宜一点" → price_max 降低约 20%
- "贵一点也行" → price_max 提高约 20%
- "小一点" → bedrooms 减 1
- "大一点" → bedrooms 加 1
- 区域名称直接替换 district
- 不改的字段返回 null，不要重复当前值
- 只输出 JSON"""


class QueryRewriter:
    """查询改写器 —— 将用户的模糊调整转化为精确的筛选条件变更"""

    def __init__(self, max_rewrites: int = MAX_REWRITES) -> None:
        self.max_rewrites = max_rewrites
        self._rewrite_count = 0

    def reset(self) -> None:
        """重置改写计数器（新会话调用）"""
        self._rewrite_count = 0

    def deterministic_expand(
        self,
        query: str,
        active_filters: dict[str, Any],
    ) -> dict[str, Any] | None:
        """确定性短查询扩展（不用 LLM）。

        识别明确的筛选词 → 直接转化为 filter 变更。
        """
        text = query.strip().lower()
        changes: dict[str, Any] = {}

        # 价格方向词
        if any(w in text for w in ["便宜", "低一点", "少一点", "降低", "减少"]):
            current_max = active_filters.get("price_max")
            if current_max is not None:
                changes["price_max"] = int(float(current_max) * 0.8)
                changes["reasoning"] = "用户要求降低预算"

        elif any(w in text for w in ["贵一点", "高一点", "多一点", "提高", "增加", "放宽"]):
            current_max = active_filters.get("price_max")
            if current_max is not None:
                changes["price_max"] = int(float(current_max) * 1.2)
                changes["reasoning"] = "用户允许提高预算"

        # 户型方向词
        if any(w in text for w in ["小一点", "少一", "更小", "减一"]):
            current_bed = active_filters.get("bedrooms")
            if current_bed is not None and current_bed > 0:
                changes["bedrooms"] = current_bed - 1
                changes["reasoning"] = "用户要求减少卧室数"

        elif any(w in text for w in ["大一点", "多一", "更大", "加一"]):
            current_bed = active_filters.get("bedrooms")
            if current_bed is not None:
                changes["bedrooms"] = current_bed + 1
                changes["reasoning"] = "用户要求增加卧室数"

        # 类型转换词
        type_keywords = {
            "合租": "shared",
            "share": "shared",
            "单间": "studio",
            "studio": "studio",
            "公寓": "apartment",
            "apartment": "apartment",
            "别墅": "house",
            "house": "house",
        }
        for kw, pt in type_keywords.items():
            if kw in text:
                changes["property_type"] = pt
                changes["reasoning"] = f"用户指定房源类型为 {kw}"
                break

        return changes if len(changes) > 1 else None  # 至少改了一个字段 + reasoning

    async def llm_rewrite(
        self,
        query: str,
        active_filters: dict[str, Any],
        result_count: int,
        llm,
    ) -> dict[str, Any] | None:
        """LLM 改写查询"""
        from app.services.llm_service import get_llm_service

        if llm is None:
            llm_service = get_llm_service()
            if not llm_service.is_available:
                return None
        else:
            llm_service = llm

        prompt = REWRITE_SYSTEM_PROMPT.format(
            active_filters=active_filters,
            query=query,
            result_count=result_count,
        )

        try:
            result = await llm_service.complete_json(
                prompt,
                query,
                temperature=0.1,
                max_tokens=400,
            )
        except Exception:
            logger.debug("LLM 查询改写失败")
            return None

        if not result or all(
            result.get(k) is None
            for k in ("district", "price_min", "price_max", "bedrooms", "property_type")
        ):
            return None

        return result

    async def rewrite_if_needed(
        self,
        query: str,
        active_filters: dict[str, Any],
        result_count: int,
        top_score: float,
        llm=None,
    ) -> dict[str, Any]:
        """判断是否需要改写，需要则执行改写。

        Returns:
            {rewritten: bool, new_filters: dict, changes: dict, reason: str}
        """
        # 先试确定性扩展
        changes = self.deterministic_expand(query, active_filters)
        if changes is not None:
            self._rewrite_count += 1
            new_filters = {**active_filters}
            for k, v in changes.items():
                if k != "reasoning" and v is not None:
                    new_filters[k] = v
            return {
                "rewritten": True,
                "new_filters": new_filters,
                "changes": changes,
                "method": "deterministic",
                "reason": changes.get("reasoning", "规则扩展"),
            }

        # 如果不需要改写（不是缩小/扩大范围的表述），直接返回
        if not self._needs_rewrite(query, result_count):
            return {"rewritten": False, "new_filters": active_filters, "changes": {}, "reason": ""}

        # 已达最大改写次数
        if self._rewrite_count >= self.max_rewrites:
            return {"rewritten": False, "new_filters": active_filters, "changes": {}, "reason": "已达最大改写次数"}

        # LLM 改写
        changes = await self.llm_rewrite(query, active_filters, result_count, llm)
        if changes is None:
            return {"rewritten": False, "new_filters": active_filters, "changes": {}, "reason": "LLM 改写失败"}

        self._rewrite_count += 1
        new_filters = {**active_filters}
        for k, v in changes.items():
            if k not in ("reasoning", "rewritten") and v is not None:
                new_filters[k] = v

        return {
            "rewritten": True,
            "new_filters": new_filters,
            "changes": changes,
            "method": "llm",
            "reason": changes.get("reasoning", "LLM 改写"),
        }

    @staticmethod
    def _needs_rewrite(query: str, result_count: int) -> bool:
        """判断用户消息是否暗示需要修改搜索条件"""
        text = query.strip()
        # 短消息 + 方向词 → 大概率是调条件
        adjust_words = [
            "便宜", "贵", "少", "多", "大一点", "小一点", "换", "换个",
            "不要", "算了", "改成", "换个区域", "别", "有没有", "能不能",
            "还有", "其他", "另外", "别的", "只要", "只要公寓", "只",
        ]
        return any(w in text for w in adjust_words)
