"""阶段识别器 —— 已合并到 AgentService.classify_message() 统一分类器中。

保留此文件仅用于：
1. 向后兼容（旧代码可能直接 import StageClassifier）
2. 内部委托给 AgentService 的统一分类方法

新架构参考 EstateWise：意图 + 阶段 + 路由信号 → 一次 LLM 调用完成。
"""
from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

# 保留原 prompt 作为参考文档（不再直接使用）
STAGE_SYSTEM_PROMPT = """你是租房对话的阶段识别器。根据用户消息和对话历史，判断当前处于哪个阶段。

阶段定义：
- explore: 用户模糊描述需求，探索市场，"想了解一下"、"大概什么价位"、"附近有哪些"
- calibrate: 用户在调整预算/要求，"便宜一点的"、"那1万以内呢"、"有没有更大的"、"还有更便宜的吗"
- narrow: 用户在比较区域或关注特定配套，"A区和B区哪个好"、"附近超市多的"、"有健身房吗"、"到学校多远"
- compare: 用户在对比具体房源，"这两套帮我看看"、"哪套更划算"、"这个比那个好在哪"
- decide: 用户已选定或准备下一步，"就这套"、"怎么看房"、"能约吗"、"怎么预订"
- general: 闲聊、平台使用问题、FAQ

只输出 JSON: {"stage": "...", "confidence": 0.0-1.0, "reasoning": "简短理由"}"""


class StageClassifier:
    """漏斗阶段识别器（已废弃，委托给 AgentService 的统一分类器）。

    保留此类仅用于向后兼容——所有新代码应使用
    AgentService.classify_message()，它一次调用同时返回意图 + 阶段 + 路由。
    """

    async def classify(
        self,
        message: str,
        history: list[dict],
        llm: "LLMService | None" = None,
    ) -> dict[str, Any]:
        """识别用户当前所处的漏斗阶段（委托给 AgentService）。

        如果 AgentService 不可用，降级为本地规则判断。
        """
        try:
            from app.services.agent_service import AgentService
            agent_svc = AgentService()
            result = await agent_svc.classify_message(message, history)
            return {
                "stage": result["stage"],
                "confidence": result["confidence"],
                "reasoning": result.get("reasoning", ""),
            }
        except Exception:
            logger.debug("统一分类不可用，使用规则兜底", exc_info=True)
            return self._fallback_classify(message)

    @staticmethod
    def _fallback_classify(message: str) -> dict[str, Any]:
        """规则兜底（LLM 不可用时）"""
        text = message.strip().lower()

        if any(w in text for w in ["就这", "定了", "怎么看房", "约", "预订", "联系", "签约"]):
            return {"stage": "decide", "confidence": 0.7, "reasoning": "规则：决策信号"}

        if any(w in text for w in ["对比", "比较", "哪个好", "哪套好", "vs", "pk"]):
            return {"stage": "compare", "confidence": 0.7, "reasoning": "规则：对比信号"}

        if any(w in text for w in ["附近", "周边", "配套", "超市", "餐馆", "地铁", "公交",
                                     "健身房", "到", "距离", "多远", "区", "居民区"]):
            return {"stage": "narrow", "confidence": 0.5, "reasoning": "规则：区域/配套信号"}

        adjust_words = ["便宜", "贵", "少一点", "多一点", "大一点", "小一点",
                       "以内", "以下", "不超过", "至少", "左右", "大概"]
        if any(w in text for w in adjust_words):
            return {"stage": "calibrate", "confidence": 0.5, "reasoning": "规则：预算/户型调整信号"}

        return {"stage": "explore", "confidence": 0.4, "reasoning": "规则：默认探索阶段"}
