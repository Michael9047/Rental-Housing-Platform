"""工具注册表 —— 集中管理 Agent 可用的所有工具。

参考 EstateWise 的 ToolExecutor 接口。
每个工具 = name + description + OpenAI function schema + async handler。

使用 contextvars 传递请求级 DB session，确保 handler 在异步环境下安全。
"""
from __future__ import annotations

import contextvars
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

# 请求级 DB session（线程安全 + asyncio 安全）
_current_session: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "tool_session", default=None
)
_current_user_id: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "tool_user_id", default=None
)


@dataclass
class ToolDef:
    """单个工具定义。"""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for the tool's input
    handler: Callable[..., Any] | None = None  # async callable
    agent_names: list[str] = field(default_factory=list)  # 哪些 Agent 可用此工具

    def to_openai_schema(self) -> dict[str, Any]:
        """转为 OpenAI function calling 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """中央工具注册表。

    使用方式：
        registry = ToolRegistry.get_instance()
        registry.register(ToolDef(name="property_search", ...))

        # 获取某 Agent 的可用工具 schemas
        schemas = registry.get_schemas_for("search_agent")

        # 执行工具
        result = await registry.execute("property_search", {"district": "伦敦"})
    """

    _instance: ToolRegistry | None = None

    def __init__(self) -> None:
        self._tools: dict[str, ToolDef] = {}

    @classmethod
    def get_instance(cls) -> ToolRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    # ── CRUD ────────────────────────────────────────────────────────────

    def register(self, tool: ToolDef) -> None:
        self._tools[tool.name] = tool

    def deregister(self, name: str) -> bool:
        return self._tools.pop(name, None) is not None

    def get(self, name: str) -> ToolDef | None:
        return self._tools.get(name)

    def list_all(self) -> list[ToolDef]:
        return list(self._tools.values())

    # ── Schema 生成 ─────────────────────────────────────────────────────

    def get_schemas_for(self, agent_name: str) -> list[dict[str, Any]]:
        """获取指定 Agent 可用的工具 schemas（OpenAI 格式）。"""
        schemas: list[dict[str, Any]] = []
        for tool in self._tools.values():
            if not tool.agent_names or agent_name in tool.agent_names:
                schemas.append(tool.to_openai_schema())
        return schemas

    def get_all_schemas(self) -> list[dict[str, Any]]:
        return [t.to_openai_schema() for t in self._tools.values()]

    # ── 执行 ────────────────────────────────────────────────────────────

    async def execute(self, name: str, args: dict[str, Any]) -> str:
        """执行指定工具，返回 JSON 字符串结果。"""
        tool = self._tools.get(name)
        if tool is None:
            return json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)

        if tool.handler is None:
            return json.dumps({"error": f"工具 {name} 未绑定 handler"}, ensure_ascii=False)

        try:
            result = await tool.handler(**args)
            if isinstance(result, str):
                return result
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as exc:
            logger.warning("工具 %s 执行失败: %s", name, exc)
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

    async def execute_raw(self, name: str, args: dict[str, Any]) -> Any:
        """执行工具，返回原始 Python 对象（不转 JSON）。"""
        tool = self._tools.get(name)
        if tool is None or tool.handler is None:
            return None
        return await tool.handler(**args)


# ═══════════════════════════════════════════════════════════════════════════════
# 预定义工具注册
# ═══════════════════════════════════════════════════════════════════════════════

def register_default_tools(
    registry: ToolRegistry,
    property_service: Any = None,
    llm_service: Any = None,
) -> None:
    """注册所有默认工具（绑定到现有 service 层）。

    在应用启动时调用一次。handler 可以后续绑定（延迟绑定模式）。
    """
    # ── 房源搜索工具 ──
    registry.register(ToolDef(
        name="property_search",
        description="搜索房源。支持自然语言 query + 结构化筛选条件（district/price_min/price_max/bedrooms/property_type）。自动渐进放宽条件。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "自然语言搜索词"},
                "district": {"type": "string", "description": "城市或区域"},
                "price_min": {"type": "number", "description": "最低月租"},
                "price_max": {"type": "number", "description": "最高月租"},
                "bedrooms": {"type": "integer", "description": "卧室数"},
                "property_type": {"type": "string", "enum": ["apartment", "house", "studio", "shared"]},
                "limit": {"type": "integer", "default": 100},
            },
            "required": [],
        },
        agent_names=["search_agent", "filter_agent"],
    ))

    registry.register(ToolDef(
        name="extract_filters",
        description="从自然语言中提取结构化筛选条件（district/price_min/price_max/bedrooms/property_type）。",
        parameters={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "用户自然语言消息"},
            },
            "required": ["message"],
        },
        agent_names=["search_agent", "filter_agent"],
    ))

    registry.register(ToolDef(
        name="score_properties",
        description="对候选房源进行确定性质量评分（价格匹配度40% + 空间匹配度20% + 设施完整度20% + 基础分20%），返回 top 3 附带亮点理由。",
        parameters={
            "type": "object",
            "properties": {
                "candidate_ids": {"type": "array", "items": {"type": "integer"}, "description": "候选房源 ID 列表"},
                "price_min": {"type": "number"},
                "price_max": {"type": "number"},
            },
            "required": ["candidate_ids"],
        },
        agent_names=["search_agent"],
    ))

    # ── 对比工具 ──
    registry.register(ToolDef(
        name="compare_dimensions",
        description="多维度对比房源：价格/通勤/空间/评价四个维度加权评分。返回每套房的综合得分和分项得分。",
        parameters={
            "type": "object",
            "properties": {
                "property_ids": {"type": "array", "items": {"type": "integer"}},
                "priority": {"type": "string", "enum": ["balanced", "budget", "commute", "space"], "default": "balanced"},
            },
            "required": ["property_ids"],
        },
        agent_names=["compare_agent", "search_agent"],
    ))

    # ── POI / 通勤工具 ──
    registry.register(ToolDef(
        name="poi_lookup",
        description="查询房源周边的 POI（超市/餐馆/地铁/公交/健身房等）。",
        parameters={
            "type": "object",
            "properties": {
                "property_id": {"type": "integer"},
                "poi_types": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["property_id"],
        },
        agent_names=["search_agent"],
    ))

    registry.register(ToolDef(
        name="commute_calc",
        description="计算房源到指定地点的通勤距离和时间（支持步行/公交/驾车）。",
        parameters={
            "type": "object",
            "properties": {
                "property_id": {"type": "integer"},
                "destination": {"type": "string", "description": "目的地地址或 POI 名称"},
                "mode": {"type": "string", "enum": ["walking", "transit", "driving"], "default": "transit"},
            },
            "required": ["property_id", "destination"],
        },
        agent_names=["search_agent"],
    ))

    # ── 市场分析工具 ──
    registry.register(ToolDef(
        name="market_stats",
        description="获取市场统计数据：价格分布、户型分布、区域房源数量。",
        parameters={
            "type": "object",
            "properties": {
                "district": {"type": "string", "description": "城市或区域"},
                "property_type": {"type": "string"},
            },
            "required": [],
        },
        agent_names=["search_agent"],
    ))

    # ── 购物车工具 ──
    registry.register(ToolDef(
        name="cart_view",
        description="查看当前用户的候选清单（购物车）。",
        parameters={"type": "object", "properties": {}, "required": []},
        agent_names=["cart_agent", "compare_agent"],
    ))

    registry.register(ToolDef(
        name="cart_add",
        description="将房源加入候选清单。",
        parameters={
            "type": "object",
            "properties": {
                "property_id": {"type": "integer"},
                "reason": {"type": "string", "description": "添加理由"},
            },
            "required": ["property_id"],
        },
        agent_names=["cart_agent"],
    ))

    registry.register(ToolDef(
        name="cart_remove",
        description="从候选清单移除房源。",
        parameters={
            "type": "object",
            "properties": {"property_id": {"type": "integer"}},
            "required": ["property_id"],
        },
        agent_names=["cart_agent"],
    ))

    # ── FAQ 工具 ──
    registry.register(ToolDef(
        name="faq_match",
        description="匹配 FAQ 知识库：押金/合同/预订流程/费用等政策问题。返回匹配结果和置信度。",
        parameters={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
        agent_names=["faq_agent"],
    ))

    # ── 质量 / 安全工具 ──
    registry.register(ToolDef(
        name="gap_detect",
        description="检测搜索结果分数断层，判断是否应果断推荐前N名、触发查询改写或安全兜底。",
        parameters={
            "type": "object",
            "properties": {
                "scores": {"type": "array", "items": {"type": "number"}},
            },
            "required": ["scores"],
        },
        agent_names=["search_agent"],
    ))

    registry.register(ToolDef(
        name="safe_fallback_check",
        description="检查检索质量是否足够，不足时跳过 LLM 生成，返回兜底模板。",
        parameters={
            "type": "object",
            "properties": {
                "document_count": {"type": "integer"},
                "top_score": {"type": "number"},
                "relaxation_level": {"type": "integer"},
            },
            "required": ["document_count", "top_score", "relaxation_level"],
        },
        agent_names=["search_agent", "synthesizer_agent"],
    ))

    registry.register(ToolDef(
        name="build_fallback_reply",
        description="生成安全兜底回复（检索无结果或质量不足时使用）。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "active_filters": {"type": "object"},
                "relaxation_level": {"type": "integer"},
            },
            "required": ["query", "active_filters", "relaxation_level"],
        },
        agent_names=["synthesizer_agent"],
    ))

    # ── 查询改写 ──
    registry.register(ToolDef(
        name="query_rewrite",
        description="改写模糊的相对描述为精确的搜索条件（如'便宜一点'→price_max降低20%）。先尝试确定性规则，再调用 LLM。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "active_filters": {"type": "object"},
                "result_count": {"type": "integer"},
            },
            "required": ["query", "active_filters", "result_count"],
        },
        agent_names=["search_agent", "filter_agent"],
    ))

    # ── Embedding ──
    registry.register(ToolDef(
        name="generate_embedding",
        description="生成文本向量嵌入，用于语义搜索。",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        agent_names=["search_agent"],
    ))


# ═══════════════════════════════════════════════════════════════════════════════
# Handler 绑定（按请求绑定真实 service 方法）
# ═══════════════════════════════════════════════════════════════════════════════

def bind_tool_handlers(
    registry: ToolRegistry,
    session: Any = None,
    user_id: int | None = None,
) -> None:
    """为工具注册表绑定真实的 handler（连接到现有 service 层）。

    在每个 HTTP 请求中调用，确保 handler 闭包持有当前请求的 session。
    首次调用时自动注册默认工具定义（幂等）。

    用法：
        _current_session.set(session)
        _current_user_id.set(user_id)
        bind_tool_handlers(tool_registry, session, user_id)
    """
    # 每次请求重新注册工具定义和绑定 handler（幂等——重复注册会覆盖）
    try:
        register_default_tools(registry)
    except Exception:
        logger.exception("register_default_tools 执行失败")
        return

    if session is not None:
        _current_session.set(session)
    if user_id is not None:
        _current_user_id.set(user_id)

    # ── property_search ──
    async def _property_search(
        query: str | None = None,
        district: str | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
        bedrooms: int | None = None,
        property_type: str | None = None,
        limit: int = 100,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """搜索房源：先用 PropertyService 做结构化搜索，再交给 AgentService 做渐进放宽。"""
        from decimal import Decimal
        from app.services.property_service import PropertyService
        from app.services.agent_service import AgentService

        sess = _current_session.get()
        if sess is None:
            return {"error": "数据库会话不可用", "rows": []}

        try:
            prop_svc = PropertyService(sess)
            rows = await prop_svc.search(
                query=query,
                district=district,
                price_min=Decimal(str(price_min)) if price_min is not None else None,
                price_max=Decimal(str(price_max)) if price_max is not None else None,
                bedrooms=bedrooms,
                property_type=property_type,
                limit=limit,
            )
            results = []
            for prop, sim in rows:
                results.append({
                    "id": prop.id,
                    "title": prop.title,
                    "district": prop.district,
                    "price_monthly": float(prop.price_monthly),
                    "bedrooms": prop.bedrooms,
                    "property_type": prop.property_type,
                    "area_sqm": float(prop.area_sqm) if prop.area_sqm else None,
                    "address": prop.address,
                    "similarity": round(sim, 4) if sim else None,
                })
            return {"count": len(results), "rows": results}
        except Exception as exc:
            logger.exception("property_search 失败")
            # 降级：使用 AgentService 的渐进放宽搜索
            try:
                agent_svc = AgentService(sess)
                filters = {
                    "district": district,
                    "price_min": price_min,
                    "price_max": price_max,
                    "bedrooms": bedrooms,
                    "property_type": property_type,
                }
                filters = {k: v for k, v in filters.items() if v is not None}
                relax_result = await agent_svc._search_with_relaxation(
                    query=query, filters=filters, limit=limit
                )
                rows_list = relax_result.get("rows", [])
                results = []
                for prop, sim in rows_list:
                    results.append({
                        "id": prop.id,
                        "title": prop.title,
                        "district": prop.district,
                        "price_monthly": float(prop.price_monthly),
                        "bedrooms": prop.bedrooms,
                        "property_type": prop.property_type,
                        "area_sqm": float(prop.area_sqm) if prop.area_sqm else None,
                        "address": prop.address,
                        "similarity": round(sim, 4) if sim else None,
                    })
                return {
                    "count": len(results),
                    "rows": results,
                    "relaxation_level": relax_result.get("relaxation_level", 0),
                    "relaxed_fields": relax_result.get("relaxed_fields", []),
                }
            except Exception as exc2:
                logger.exception("property_search 降级也失败")
                return {"error": str(exc2), "rows": []}

    tool = registry.get("property_search")
    if tool is None:
        logger.critical("FATAL: property_search 工具未注册！register_default_tools 可能未执行或失败")
        return
    tool.handler = _property_search

    # ── extract_filters ──
    async def _extract_filters(message: str, **kwargs: Any) -> dict[str, Any]:
        """使用 LLM 从自然语言中提取结构化筛选条件。"""
        from app.services.llm_service import get_llm_service

        llm = get_llm_service()
        if not llm.is_available:
            return {}

        try:
            result = await llm.complete_json(
                """从用户的租房需求中提取结构化筛选条件。
返回 JSON 格式：
{"district": "城市或区域名(中文)", "price_min": 最低月租数字或null, "price_max": 最高月租数字或null, "bedrooms": 卧室数整数或null, "property_type": "apartment|house|studio|shared|null"}
只提取用户明确提到的条件，没有提到的字段设为 null。""",
                message,
                temperature=0.0,
                max_tokens=300,
            )
            return result if isinstance(result, dict) else {}
        except Exception:
            logger.debug("LLM 筛选条件提取失败")
            return {}

    registry.get("extract_filters").handler = _extract_filters

    # ── score_properties ──
    async def _score_properties_handler(
        candidate_ids: list[int],
        price_min: float | None = None,
        price_max: float | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """对候选房源进行确定性质量评分。"""
        from app.services.agent_service import _score_properties as score_fn
        from app.models.property import Property
        from sqlalchemy import select

        sess = _current_session.get()
        if sess is None:
            return {"error": "数据库会话不可用", "top3": []}

        try:
            stmt = select(Property).where(Property.id.in_(candidate_ids))
            result = await sess.execute(stmt)
            candidates = list(result.scalars().all())

            filters = {}
            if price_min is not None:
                filters["price_min"] = price_min
            if price_max is not None:
                filters["price_max"] = price_max

            scored = score_fn(candidates, filters, {})
            return {"top3": scored[:3], "total": len(scored)}
        except Exception as exc:
            logger.exception("score_properties 失败")
            return {"error": str(exc), "top3": []}

    registry.get("score_properties").handler = _score_properties_handler

    # ── compare_dimensions ──
    async def _compare_dimensions(
        property_ids: list[int],
        priority: str = "balanced",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """多维度对比房源。"""
        from app.services.agent_service import AgentService

        sess = _current_session.get()
        if sess is None:
            return {"error": "数据库会话不可用"}

        user_id = _current_user_id.get()
        try:
            agent_svc = AgentService(sess)
            result = await agent_svc.compare_cart(
                user_id=user_id or 0,
                property_ids=property_ids,
                priority=priority,
            )
            return result
        except Exception as exc:
            logger.exception("compare_dimensions 失败")
            return {"error": str(exc)}

    registry.get("compare_dimensions").handler = _compare_dimensions

    # ── poi_lookup ──
    async def _poi_lookup(
        property_id: int,
        poi_types: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """查询房源周边的 POI。"""
        from app.services.poi_service import POIService

        sess = _current_session.get()
        if sess is None:
            return {"error": "数据库会话不可用"}

        try:
            poi_svc = POIService(sess)
            poi = await poi_svc.get_poi(property_id)
            if poi is None:
                return {"property_id": property_id, "pois": [], "message": "暂无周边设施数据"}

            # 反序列化 POI JSON 数据
            import json as _json
            poi_data = {}
            if isinstance(poi.poi_data, str):
                poi_data = _json.loads(poi.poi_data)
            elif isinstance(poi.poi_data, dict):
                poi_data = poi.poi_data

            # 如果指定了类型，过滤
            if poi_types:
                filtered = {k: v for k, v in poi_data.items() if k in poi_types}
                return {"property_id": property_id, "pois": filtered}

            return {"property_id": property_id, "pois": poi_data}
        except Exception as exc:
            logger.exception("poi_lookup 失败")
            return {"error": str(exc), "property_id": property_id}

    registry.get("poi_lookup").handler = _poi_lookup

    # ── commute_calc ──
    async def _commute_calc(
        property_id: int,
        destination: str,
        mode: str = "transit",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """计算房源到指定地点的通勤时间和距离。"""
        from app.services.commute_service import (
            calculate_commute_batch,
            CommuteDestination,
        )
        from app.models.property import Property
        from sqlalchemy import select

        sess = _current_session.get()
        if sess is None:
            return {"error": "数据库会话不可用"}

        try:
            # 获取房源坐标
            stmt = select(Property).where(Property.id == property_id)
            result = await sess.execute(stmt)
            prop = result.scalar_one_or_none()
            if prop is None:
                return {"error": f"房源 {property_id} 不存在"}
            if prop.latitude is None or prop.longitude is None:
                return {"error": f"房源 {property_id} 缺少坐标信息"}

            # 先用 destination 当作坐标解析（如果是学校名或地址）
            # 简单处理：destination 作为标签，用默认起点（如学校坐标）
            dest = CommuteDestination(
                property_id=property_id,
                lat=float(prop.latitude),
                lng=float(prop.longitude),
                label=destination,
            )
            batch_result = await calculate_commute_batch(
                origin_lat=float(prop.latitude),
                origin_lng=float(prop.longitude),
                destinations=[dest],
                city=getattr(prop, "district", None),
            )
            if batch_result.results:
                r = batch_result.results[0]
                return {
                    "property_id": property_id,
                    "destination": destination,
                    "mode": mode,
                    "duration_minutes": r.duration_minutes,
                    "distance_km": r.distance_km,
                    "mode_used": getattr(r, "mode", mode),
                    "source": batch_result.source,
                }
            return {"property_id": property_id, "destination": destination, "error": "无法计算通勤"}
        except Exception as exc:
            logger.exception("commute_calc 失败")
            return {"error": str(exc), "property_id": property_id}

    registry.get("commute_calc").handler = _commute_calc

    # ── market_stats ──
    async def _market_stats(
        district: str | None = None,
        property_type: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """获取市场统计数据。"""
        from app.services.property_service import PropertyService
        from decimal import Decimal

        sess = _current_session.get()
        if sess is None:
            return {"error": "数据库会话不可用"}

        try:
            prop_svc = PropertyService(sess)
            rows = await prop_svc.search(
                district=district,
                property_type=property_type,
                limit=200,
            )
            if not rows:
                return {"count": 0, "message": "该区域暂无房源数据"}

            props = [p for p, _ in rows]
            prices = [float(p.price_monthly) for p in props]
            areas = [float(p.area_sqm) for p in props if p.area_sqm]

            # 户型分布
            br_dist: dict[int, int] = {}
            for p in props:
                br = p.bedrooms or 0
                br_dist[br] = br_dist.get(br, 0) + 1

            return {
                "count": len(props),
                "district": district,
                "price_stats": {
                    "min": min(prices) if prices else 0,
                    "max": max(prices) if prices else 0,
                    "avg": round(sum(prices) / len(prices), 2) if prices else 0,
                    "median": round(sorted(prices)[len(prices) // 2], 2) if prices else 0,
                },
                "area_stats": {
                    "min": min(areas) if areas else 0,
                    "max": max(areas) if areas else 0,
                    "avg": round(sum(areas) / len(areas), 2) if areas else 0,
                } if areas else None,
                "bedroom_distribution": br_dist,
            }
        except Exception as exc:
            logger.exception("market_stats 失败")
            return {"error": str(exc)}

    registry.get("market_stats").handler = _market_stats

    # ── cart_view ──
    async def _cart_view(**kwargs: Any) -> dict[str, Any]:
        """查看当前用户的候选清单。"""
        from app.services.agent_service import AgentService

        sess = _current_session.get()
        user_id = _current_user_id.get()
        if sess is None or user_id is None:
            return {"error": "会话不可用", "items": []}

        try:
            agent_svc = AgentService(sess)
            cart, items = await agent_svc.get_cart_items(user_id)
            return {
                "cart_id": cart.id,
                "count": len(items),
                "items": [
                    {
                        "property_id": it.property_id,
                        "title": it.property.title if it.property else "未知",
                        "reason": it.reason,
                    }
                    for it in items
                ],
            }
        except Exception as exc:
            logger.exception("cart_view 失败")
            return {"error": str(exc), "items": []}

    registry.get("cart_view").handler = _cart_view

    # ── cart_add ──
    async def _cart_add(property_id: int, reason: str | None = None, **kwargs: Any) -> dict[str, Any]:
        """将房源加入候选清单。"""
        from app.services.agent_service import AgentService

        sess = _current_session.get()
        user_id = _current_user_id.get()
        if sess is None or user_id is None:
            return {"error": "请先登录"}

        try:
            agent_svc = AgentService(sess)
            item = await agent_svc.add_to_cart(user_id, property_id, reason or "")
            return {
                "success": True,
                "property_id": property_id,
                "message": f"已添加房源 #{property_id} 到候选清单",
            }
        except ValueError as exc:
            return {"error": str(exc), "success": False}
        except Exception as exc:
            logger.exception("cart_add 失败")
            return {"error": str(exc), "success": False}

    registry.get("cart_add").handler = _cart_add

    # ── cart_remove ──
    async def _cart_remove(property_id: int, **kwargs: Any) -> dict[str, Any]:
        """从候选清单移除房源。"""
        from app.services.agent_service import AgentService

        sess = _current_session.get()
        user_id = _current_user_id.get()
        if sess is None or user_id is None:
            return {"error": "请先登录"}

        try:
            agent_svc = AgentService(sess)
            removed = await agent_svc.remove_from_cart(user_id, property_id)
            return {
                "success": removed,
                "property_id": property_id,
                "message": f"已移除房源 #{property_id}" if removed else "购物车中没有该房源",
            }
        except Exception as exc:
            logger.exception("cart_remove 失败")
            return {"error": str(exc), "success": False}

    registry.get("cart_remove").handler = _cart_remove

    # ── faq_match ──
    async def _faq_match(message: str, **kwargs: Any) -> dict[str, Any]:
        """匹配 FAQ 知识库。"""
        from app.services.agent_faq import match_faq

        try:
            strength, hits = match_faq(message)
            if strength == "strong" and hits:
                return {
                    "matched": True,
                    "strength": "strong",
                    "answer": hits[0].answer,
                    "faq_id": hits[0].id,
                }
            elif strength == "weak" and hits:
                return {
                    "matched": True,
                    "strength": "weak",
                    "chips": [h.chip for h in hits[:5]],
                }
            return {"matched": False, "strength": "none"}
        except Exception as exc:
            logger.exception("faq_match 失败")
            return {"error": str(exc), "matched": False}

    registry.get("faq_match").handler = _faq_match

    # ── gap_detect ──
    async def _gap_detect(scores: list[float], **kwargs: Any) -> dict[str, Any]:
        """检测分数断层。"""
        if not scores or len(scores) < 2:
            return {"has_gap": False, "gap_threshold": None, "top_n": len(scores)}

        sorted_scores = sorted(scores, reverse=True)
        gaps = [
            sorted_scores[i] - sorted_scores[i + 1]
            for i in range(len(sorted_scores) - 1)
        ]
        if not gaps:
            return {"has_gap": False, "top_n": len(scores)}

        max_gap = max(gaps)
        avg_gap = sum(gaps) / len(gaps)
        # 最大 gap > 2x 平均 → 显著断层
        significant = max_gap > avg_gap * 2 and max_gap > 10

        top_n = 1
        if significant:
            for i, g in enumerate(gaps):
                if g == max_gap:
                    top_n = i + 1
                    break

        return {
            "has_gap": significant,
            "max_gap": round(max_gap, 2),
            "avg_gap": round(avg_gap, 2),
            "top_n": top_n,
            "total": len(scores),
        }

    registry.get("gap_detect").handler = _gap_detect

    # ── safe_fallback_check ──
    async def _safe_fallback_check(
        document_count: int,
        top_score: float,
        relaxation_level: int,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """检查检索质量是否足够。"""
        needs_fallback = (
            document_count == 0
            or (top_score < 30 and relaxation_level >= 2)
        )
        return {
            "needs_fallback": needs_fallback,
            "reason": (
                "无搜索结果" if document_count == 0
                else f"最高分{top_score}过低且已放宽{relaxation_level}级" if needs_fallback
                else "质量合格"
            ),
            "document_count": document_count,
            "top_score": top_score,
            "relaxation_level": relaxation_level,
        }

    registry.get("safe_fallback_check").handler = _safe_fallback_check

    # ── build_fallback_reply ──
    async def _build_fallback_reply(
        query: str,
        active_filters: dict[str, Any] | None = None,
        relaxation_level: int = 0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """生成安全兜底回复。"""
        from app.services.safe_fallback import build_fallback_response

        try:
            reply = build_fallback_response(
                query=query,
                active_filters=active_filters or {},
                relaxation_level=relaxation_level,
            )
            return {"reply": reply}
        except Exception as exc:
            logger.exception("build_fallback_reply 失败")
            return {"reply": "抱歉，暂时无法找到匹配的房源。请尝试修改搜索条件。"}

    registry.get("build_fallback_reply").handler = _build_fallback_reply

    # ── query_rewrite ──
    async def _query_rewrite(
        query: str,
        active_filters: dict[str, Any] | None = None,
        result_count: int = 0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """改写模糊的相对描述为精确搜索条件。"""
        from app.services.llm_service import get_llm_service

        filters = active_filters or {}

        # 先用确定性规则处理常见模式
        rewritten_filters: dict[str, Any] = {}
        lower = query.lower().strip()

        # 价格调整
        if any(w in lower for w in ["便宜", "便宜一点", "便宜些", "更低"]):
            if filters.get("price_max"):
                rewritten_filters["price_max"] = float(filters["price_max"]) * 0.8
            rewritten_filters["price_hint"] = "降低预算"
        elif any(w in lower for w in ["贵", "贵一点", "好一点", "高端", "豪华"]):
            if filters.get("price_min"):
                rewritten_filters["price_min"] = float(filters["price_min"]) * 1.2
            rewritten_filters["price_hint"] = "提高预算"

        # 区域调整
        if any(w in lower for w in ["近一点", "近些", "交通方便"]):
            rewritten_filters["commute_priority"] = True

        # 如果确定性规则没覆盖，用 LLM
        if not rewritten_filters or "price_hint" not in rewritten_filters:
            llm = get_llm_service()
            if llm.is_available:
                try:
                    llm_result = await llm.complete_json(
                        f"""用户说"{query}"。当前筛选条件：{json.dumps(filters, ensure_ascii=False)}。
分析用户的意图是扩大还是缩小搜索范围，返回调整后的筛选条件（只返回需要修改的字段）：
{{"action": "expand|narrow|refine", "price_min": null, "price_max": null, "district": null, "bedrooms": null, "explanation": "..."}}
- expand: 放宽条件扩大结果
- narrow: 缩小范围精确匹配
- refine: 保持范围但调整偏好""",
                        query,
                        temperature=0.1,
                        max_tokens=300,
                    )
                    if isinstance(llm_result, dict):
                        rewritten_filters.update(llm_result)
                except Exception:
                    logger.debug("LLM 查询改写失败")

        rewritten_filters["original_query"] = query
        rewritten_filters["original_result_count"] = result_count
        return rewritten_filters

    registry.get("query_rewrite").handler = _query_rewrite

    # ── generate_embedding ──
    async def _generate_embedding(text: str, **kwargs: Any) -> dict[str, Any]:
        """生成文本向量嵌入。"""
        from app.services.embedding_service import EmbeddingService

        try:
            emb_svc = EmbeddingService()
            vector = await emb_svc.generate_embedding(text)
            return {
                "dimensions": len(vector),
                "embedding": vector[:10] + ["..."] if len(vector) > 10 else vector,
                "note": "完整向量未展示(太长)，仅显示前10维",
            }
        except Exception as exc:
            logger.exception("generate_embedding 失败")
            return {"error": str(exc)}

    registry.get("generate_embedding").handler = _generate_embedding
