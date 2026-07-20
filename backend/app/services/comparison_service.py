"""对比 Agent 服务 —— ReAct 模式

使用 LLM 工具调用对 2-5 套房源进行深度多维对比分析。
评分由 compare_scoring 确定性计算，LLM 只负责解释和 trade-off 推理。
"""
from __future__ import annotations

import json
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

COMPARISON_SYSTEM_PROMPT = """你是一个租房平台的深度对比分析师。你的任务是对用户选定的几套房源进行多维度系统性对比，帮助用户做出最终决策。

## 工具使用规则

你必须使用工具来获取真实数据，绝不能编造任何房源信息、价格或评分。
典型流程：
1. 先用 get_property_details 获取每套房的基本信息
2. 再用 get_commute_data、get_review_summary、get_safety_scores 获取补充数据
3. 最后用 compute_comparison 获取确定性评分
4. 综合所有数据，给出结构化的对比分析

## 回复要求

- 使用中文回复（用户是中国留学生）
- 引用具体数字（价格、距离、分数）来支撑你的分析
- 重点做 trade-off 分析："A 虽然贵 200/月，但通勤每天省 30 分钟"
- 根据用户指定的优先级给出推荐
- 指出值得实地验证的风险点（如某套房评价数太少）
- 分数由 compute_comparison 工具计算，你绝对不能修改或捏造分数
- 回复结构清晰：总览 → 逐维度分析 → 综合推荐"""

# ── 工具定义 ──────────────────────────────────────────────────────

def _build_tools(property_ids: list[int]) -> list[dict[str, Any]]:
    """构建 OpenAI 兼容的工具定义"""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_property_details",
                "description": f"获取指定房源的全部详细信息：价格、面积、户型、设施、押金、楼层、描述、图片数量等。可用房源 ID：{property_ids}",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "property_id": {
                            "type": "integer",
                            "description": "房源 ID",
                            "enum": property_ids,
                        },
                    },
                    "required": ["property_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_commute_data",
                "description": "获取一批房源的最近交通站点距离（米），用于评估通勤便利度。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "property_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "房源 ID 列表",
                        },
                    },
                    "required": ["property_ids"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_review_summary",
                "description": "获取一批房源的机构评价汇总（均分 + 评价数量）。评价挂靠在管理公司/机构下，不是单套房源的评价。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "property_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "房源 ID 列表",
                        },
                    },
                    "required": ["property_ids"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_safety_scores",
                "description": "获取一批房源所在区域的安全评分（0-100，越高越安全）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "property_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "房源 ID 列表",
                        },
                    },
                    "required": ["property_ids"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_poi_analysis",
                "description": "获取指定房源周边的设施分析（超市、餐厅、医院等）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "property_id": {"type": "integer", "description": "房源 ID"},
                    },
                    "required": ["property_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "compute_comparison",
                "description": f"计算所有房源的确定性加权对比评分（五维度：价格/通勤/空间/评价/安全）。你必须使用此工具的分数，不能自己编造。可选优先级：{list(PRIORITY_LABELS.keys())}",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "property_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "所有参与对比的房源 ID",
                        },
                        "priority": {
                            "type": "string",
                            "enum": list(PRIORITY_LABELS.keys()),
                            "description": f"用户偏好权重：{json.dumps(PRIORITY_LABELS, ensure_ascii=False)}",
                        },
                    },
                    "required": ["property_ids", "priority"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_properties",
                "description": "列出当前对比会话中所有房源的基本信息（ID + 标题 + 区域）。",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]


# ── Service ───────────────────────────────────────────────────────

class ComparisonService:
    """ReAct 对比 Agent"""

    def __init__(self, session: AsyncSession) -> None:
        self.db = session
        self._llm = get_llm_service()
        self._safety = SafetyScoringService()
        # 单次 ReAct 循环内的数据缓存
        self._cache: dict[int, EnrichedPropertyData] = {}
        self._property_ids: list[int] = []

    # ── 工具执行器 ──────────────────────────────────────────────

    async def _execute_tool(self, tool_name: str, args: dict[str, Any]) -> str:
        """执行一个工具并返回 JSON 字符串结果"""
        logger.debug("ReAct tool: %s(%s)", tool_name, args)
        try:
            if tool_name == "get_property_details":
                result = await self._tool_get_property_details(args)
            elif tool_name == "get_commute_data":
                result = await self._tool_get_commute(args)
            elif tool_name == "get_review_summary":
                result = await self._tool_get_reviews(args)
            elif tool_name == "get_safety_scores":
                result = await self._tool_get_safety(args)
            elif tool_name == "get_poi_analysis":
                result = await self._tool_get_poi(args)
            elif tool_name == "compute_comparison":
                result = await self._tool_compute_comparison(args)
            elif tool_name == "list_properties":
                result = self._tool_list_properties()
            else:
                result = {"error": f"未知工具: {tool_name}"}
        except Exception as exc:
            result = {"error": str(exc)}
        return json.dumps(result, ensure_ascii=False, default=str)

    async def _ensure_cache(self, property_ids: list[int]) -> None:
        """确保缓存中有指定房源的数据"""
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

    async def _tool_get_property_details(self, args: dict) -> dict:
        pid = args["property_id"]
        await self._ensure_cache([pid])
        data = self._cache.get(pid)
        if not data:
            return {"error": f"房源 {pid} 不存在"}
        return {
            "property_id": data.property_id,
            "title": data.title,
            "district": data.district,
            "address": data.address,
            "price_monthly": data.price_monthly,
            "area_sqm": data.area_sqm,
            "bedrooms": data.bedrooms,
            "bathrooms": data.bathrooms,
            "property_type": data.property_type,
            "amenities": data.amenities,
            "deposit_amount": data.deposit_amount,
            "deposit_type": data.deposit_type,
            "service_fee_rate": data.service_fee_rate,
            "min_lease_months": data.min_lease_months,
            "floor": data.floor,
            "room_number": data.room_number,
            "description": data.description,
            "image_count": data.image_count,
        }

    async def _tool_get_commute(self, args: dict) -> dict:
        pids = args["property_ids"]
        await self._ensure_cache(pids)
        return {
            str(pid): {
                "transit_meters": self._cache[pid].transit_meters,
                "display": self._cache[pid].transit_display,
            }
            for pid in pids if pid in self._cache
        }

    async def _tool_get_reviews(self, args: dict) -> dict:
        pids = args["property_ids"]
        await self._ensure_cache(pids)
        return {
            str(pid): {
                "rating": self._cache[pid].rating,
                "review_count": self._cache[pid].review_count,
            }
            for pid in pids if pid in self._cache
        }

    async def _tool_get_safety(self, args: dict) -> dict:
        pids = args["property_ids"]
        await self._ensure_cache(pids)
        return {
            str(pid): {"safety_score": self._cache[pid].safety_score}
            for pid in pids if pid in self._cache
        }

    async def _tool_get_poi(self, args: dict) -> dict:
        pid = args["property_id"]
        from app.models.poi import PropertyPOI

        poi = (
            await self.db.execute(
                select(PropertyPOI).where(PropertyPOI.property_id == pid)
            )
        ).scalar_one_or_none()
        if not poi:
            return {"property_id": pid, "poi_data": None, "content": "暂无周边设施数据"}
        return {
            "property_id": pid,
            "poi_data": poi.poi_data,
            "content": poi.content or "",
        }

    async def _tool_compute_comparison(self, args: dict) -> dict:
        pids = args["property_ids"]
        priority = normalize_priority(args.get("priority", "balanced"))
        await self._ensure_cache(pids)

        metrics = [self._cache[pid].metrics for pid in pids if pid in self._cache]
        scores = compute_scores(metrics, priority)

        # 附加维度标签和权重信息
        from app.services.compare_scoring import PRIORITY_WEIGHTS

        weights = PRIORITY_WEIGHTS.get(priority, {})
        return {
            "scores": {
                str(pid): {
                    "total": s["total"],
                    "breakdown": {
                        DIMENSION_LABELS.get(k, k): v
                        for k, v in s["breakdown"].items()
                    },
                }
                for pid, s in scores.items()
            },
            "priority": priority,
            "priority_label": PRIORITY_LABELS.get(priority, "未知"),
            "weights": {
                DIMENSION_LABELS.get(k, k): w
                for k, w in weights.items()
            },
            "dimensions": list(DIMENSION_LABELS.values()),
        }

    def _tool_list_properties(self) -> dict:
        return {
            "properties": [
                {
                    "property_id": pid,
                    "title": self._cache[pid].title if pid in self._cache else "未知",
                    "district": self._cache[pid].district if pid in self._cache else "未知",
                }
                for pid in self._property_ids
            ]
        }

    # ── 主入口 ──────────────────────────────────────────────────

    async def analyze(
        self,
        property_ids: list[int],
        user_message: str,
        priority: str = "balanced",
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """运行 ReAct 对比循环。

        Args:
            property_ids: 待对比房源 ID 列表（2~5）
            user_message: 用户的消息/问题
            priority: 评分优先级
            conversation_history: 之前的消息（追问时传入）

        Returns:
            {
                "reply": str,          # LLM 最终回复
                "scores": dict,        # {property_id: {total, breakdown}}
                "tool_trail": list,    # 工具调用轨迹
                "property_data": dict, # {property_id: dict} 前端渲染数据
            }
        """
        self._property_ids = property_ids
        self._cache = {}

        # 预加载所有房源数据（后续工具调用直接走缓存）
        await self._ensure_cache(property_ids)

        # 构建对话上下文
        if conversation_history:
            context = f"当前对比房源: {property_ids}。用户偏好: {priority}。"
            full_message = f"{context}\n用户追问: {user_message}"
        else:
            context = f"请对比分析以下房源: {property_ids}。用户偏好: {PRIORITY_LABELS.get(priority, '均衡')}。"
            full_message = f"{context}\n{user_message}" if user_message else f"{context}\n请给出全面的对比分析。"

        tools = _build_tools(property_ids)

        reply, tool_trail = await self._llm.run_react_loop(
            system_prompt=COMPARISON_SYSTEM_PROMPT,
            user_message=full_message,
            tools=tools,
            tool_executor=self._execute_tool,
        )

        # 确定性计算最终评分（前端需要权威分数用于雷达图）
        metrics = [self._cache[pid].metrics for pid in property_ids if pid in self._cache]
        scores = compute_scores(metrics, priority)

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
            "tool_trail": tool_trail,
            "property_data": property_data,
        }
