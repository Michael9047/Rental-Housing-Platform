"""对比 Agent 服务 —— 单次 LLM 调用

对 2-5 套房源做深度多维对比分析。
评分由 compare_scoring 确定性计算（可复现、可审计），
所有数据一次性批量预加载后内联进提示词，LLM 只负责解释和 trade-off 推理。

历史：原为 ReAct 工具循环（LLM 逐个调工具取数），每轮对比要 5-10 次串行
LLM 往返（30-90s），且工具读的都是已预加载的缓存——纯浪费。
2026-07 改为单次调用：预加载(~0.3s) + 一次 LLM 生成(~10s)。
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property import Property
from app.services.compare_scoring import (
    DIMENSION_LABELS,
    PRIORITY_LABELS,
    compute_scores,
    normalize_priority,
)
from app.services.comparison_data import (
    EnrichedPropertyData,
    gather_comprehensive_metrics,
)
from app.services.llm_service import get_llm_service
from app.services.safety_scoring import SafetyScoringService

logger = logging.getLogger(__name__)

# ── System Prompt ─────────────────────────────────────────────────

COMPARISON_SYSTEM_PROMPT = """你是租房平台的深度对比分析师。系统已备好全部真实数据和确定性评分，你只负责解释分析——禁止编造任何房源信息，禁止修改或捏造分数。

回复结构：
1. 总览（2-3句）：共几套、价格带、按用户优先级的总体结论
2. 逐维度分析（价格/通勤/空间/评价/安全）：引用具体数字做 trade-off 分析，例如"A 虽然贵 200/月，但通勤每天省 30 分钟"；只写有差异的维度，全部持平的维度一句带过
3. 综合推荐：按用户优先级给出明确首选和理由，并指出值得实地验证的风险点（如某套评价数太少）

规则：
- 中文口语化，用「你」不用「您」
- 只使用输入中提供的数据和分数
- 500-800字，纯文字段落，不用 Markdown 标题符号"""


# ── Service ───────────────────────────────────────────────────────

class ComparisonService:
    """深度对比：确定性评分 + 单次 LLM 解释。"""

    def __init__(self, session: AsyncSession) -> None:
        self.db = session
        self._llm = get_llm_service()
        self._safety = SafetyScoringService()
        self._cache: dict[int, EnrichedPropertyData] = {}

    async def _ensure_cache(self, property_ids: list[int]) -> None:
        """批量预加载房源的全部对比数据（POI/评价/安全，一次查询）"""
        missing = [pid for pid in property_ids if pid not in self._cache]
        if not missing:
            return
        props = (
            await self.db.execute(
                select(Property).where(Property.id.in_(missing))
            )
        ).scalars().all()
        enriched = await gather_comprehensive_metrics(
            list(props), self.db, self._safety
        )
        self._cache.update(enriched)

    # ── 主入口 ──────────────────────────────────────────────────

    async def analyze(
        self,
        property_ids: list[int],
        user_message: str,
        priority: str = "balanced",
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """运行一次对比分析。

        Args:
            property_ids: 待对比房源 ID 列表（2~5）
            user_message: 用户的消息/问题
            priority: 评分优先级
            conversation_history: 之前的消息（追问时传入）

        Returns:
            {
                "reply": str,          # LLM 分析回复
                "scores": dict,        # {property_id: {total, breakdown}} 权威分数（雷达图用）
                "tool_trail": list,    # 保留字段，恒为空（ReAct 已下线）
                "property_data": dict, # {property_id: dict} 前端渲染数据
            }
        """
        self._cache = {}

        # 预加载所有房源数据（POI/评价/安全各一次批量查询）
        await self._ensure_cache(property_ids)

        priority = normalize_priority(priority)
        metrics = [self._cache[pid].metrics for pid in property_ids if pid in self._cache]
        scores = compute_scores(metrics, priority)

        # 全部数据内联进提示词，一次 LLM 调用出分析
        reply = await self._gen_reply(property_ids, scores, priority, user_message, conversation_history)

        # 构建前端渲染数据
        property_data: dict[int, dict] = {}
        for pid in property_ids:
            if pid in self._cache:
                d = self._cache[pid]
                property_data[pid] = {
                    "property_id": d.property_id,
                    "title": d.title,
                    "district": d.district,
                    "price_monthly": d.price_monthly,
                    "area_sqm": d.area_sqm,
                    "bedrooms": d.bedrooms,
                    "bathrooms": d.bathrooms,
                    "property_type": d.property_type,
                    "amenities": d.amenities,
                    "deposit_amount": d.deposit_amount,
                    "deposit_type": d.deposit_type,
                    "service_fee_rate": d.service_fee_rate,
                    "min_lease_months": d.min_lease_months,
                    "floor": d.floor,
                    "image_count": d.image_count,
                    "transit_display": d.transit_display,
                    "rating": d.rating,
                    "review_count": d.review_count,
                    "safety_score": d.safety_score,
                }

        return {
            "reply": reply,
            "scores": scores,
            "tool_trail": [],
            "property_data": property_data,
        }

    # ── 回复生成 ──────────────────────────────────────────────────

    async def _gen_reply(
        self,
        property_ids: list[int],
        scores: dict[int, dict],
        priority: str,
        user_message: str,
        conversation_history: list[dict[str, Any]] | None,
    ) -> str:
        lines = []
        for i, pid in enumerate(property_ids, 1):
            d = self._cache.get(pid)
            if not d:
                continue
            s = scores.get(pid) or {}
            rating_str = f"{d.rating:.1f}分/{d.review_count}条" if d.rating is not None else "暂无"
            lines.append(
                f"{i}. [property_id={pid}] {d.title} | 区域: {d.district} | "
                f"月租: {d.price_monthly} | 户型: {d.bedrooms}室{d.bathrooms}卫 | "
                f"面积: {d.area_sqm or '未知'}㎡ | 通勤: {d.transit_display or '无数据'} | "
                f"评价: {rating_str} | 安全: {d.safety_score if d.safety_score is not None else '无数据'} | "
                f"设施: {', '.join(d.amenities[:6]) or '无'} | "
                f"简介: {d.description or '无'}\n"
                f"   系统得分（禁止修改）: 综合 {s.get('total')} | "
                + " ".join(f"{DIMENSION_LABELS.get(k, k)} {v}" for k, v in (s.get("breakdown") or {}).items())
            )

        user_prompt = (
            f"用户优先级：{PRIORITY_LABELS.get(priority, '均衡')}\n\n"
            f"待对比房源（真实数据 + 系统评分）：\n" + "\n".join(lines)
        )
        if conversation_history:
            user_prompt += f"\n\n用户追问：{user_message}"
        elif user_message:
            user_prompt += f"\n\n用户补充：{user_message}"

        if self._llm.is_available:
            try:
                reply = (await self._llm.complete_text(
                    messages=[
                        {"role": "system", "content": COMPARISON_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=1500,
                ) or "").strip()
                if len(reply) >= 20:
                    return reply
            except Exception:
                logger.exception("LLM 对比分析失败，降级为规则摘要")

        return self._rule_summary(property_ids, scores, priority)

    def _rule_summary(
        self,
        property_ids: list[int],
        scores: dict[int, dict],
        priority: str,
    ) -> str:
        """LLM 不可用/失败时的规则摘要（分数照常返回，雷达图不受影响）。"""
        valid = [(pid, scores.get(pid, {}).get("total", 0)) for pid in property_ids if pid in self._cache]
        if not valid:
            return "对比数据加载失败，请稍后重试。"
        winner_pid, winner_total = max(valid, key=lambda x: x[1])
        winner = self._cache[winner_pid]
        return (
            f"按「{PRIORITY_LABELS.get(priority, '均衡')}」对比 {len(valid)} 套房源，"
            f"综合得分最高的是「{winner.title}」（{winner_total} 分）。"
            f"各套分项得分见下方图表。（AI 分析暂不可用，以上为系统评分结果）"
        )
