"""Agent 消息分发器 —— 状态记忆、查询理解、可靠检索与有据回答主链路。"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatMessageRole, ChatSession
from app.services.agent_faq import get_faq, match_faq
from app.services.agentic.agents.cart_agent import CartService
from app.services.agentic.agents.compare_agent import CompareAgent
from app.services.agentic.agents.search_agent import SearchAgent
from app.services.agentic.context import load_packed_history
from app.services.agentic.memory import (
    AgentMemoryService,
    RuntimeMemory,
    build_state_summary,
    is_reset_request,
)
from app.services.agentic.query_understanding import QueryUnderstanding, understand_query
from app.services.agentic.router import classify_message
from app.services.llm_service import get_llm_service


logger = logging.getLogger(__name__)


_VALID_MODES = frozenset({"auto", "default"})
_RELATIVE_SEARCH_PATTERN = re.compile(
    r"(便宜一点|再便宜|贵一点|预算提高|预算降低|换个区域|远一点|近一点|还要|"
    r"不要.*了|不要.{0,8}(独卫|设施|配套|预算|区域|户型|通勤|电梯|泳池)|"
    r"(?:想要|希望|还要|最好).{0,12}(?:自习室|自习空间|学习室|健身房|泳池|电梯|独卫|空调)|"
    r"(?:边上|附近|周边).{0,8}(?:自习室|自习空间|学习室|健身房|泳池|超市|地铁)|"
    r"重新开始|从头开始|清空条件|重置条件)"
)
_REFERENCE_DETAIL_PATTERN = re.compile(
    r"(怎么样|好不好|详情|介绍一下|具体信息|说说|"
    r"有没有|(?:有|带|包含).{0,16}(?:吗|嘛|么|\?|？)|"
    r"健身房|自习室|自习空间|学习室|设施|配套|周边|附近|通勤|多远)"
)
_PLURAL_REFERENCE_PATTERN = re.compile(
    r"(这几套|这些房|刚才(?:推荐|筛选)的|上面几套|推荐的几套)"
)
_SEARCH_PAGE_FILTER_FIELDS = frozenset({
    "country", "district", "price_min", "price_max", "bedrooms", "property_type",
    "amenities", "room_type", "min_lease_months", "max_lease_months",
    "available_from", "institution", "commute_minutes",
})
_SEARCH_LOCATION_FIELDS = ("country", "district", "institution")


class _StepRecorder:
    """记录可验证动作摘要；不记录或暴露模型内部思维链。"""

    _NAMES = {
        "memory": "读取会话记忆",
        "router": "识别用户意图",
        "rewrite": "改写搜索请求",
        "retrieve": "检索并重排房源",
        "ground": "生成有据回答",
        "reference": "解析上下文指代",
        "compare": "对比候选房源",
        "cart": "更新候选清单",
        "faq": "检索平台知识",
    }

    def __init__(self) -> None:
        self._active: dict[str, float] = {}
        self._steps: list[dict[str, Any]] = []

    def start(self, key: str) -> None:
        self._active[key] = time.perf_counter()

    def done(self, key: str, summary: str) -> None:
        started = self._active.pop(key, time.perf_counter())
        self._steps.append({
            "agent_id": key,
            "agent_name": self._NAMES.get(key, key),
            "status": "success",
            "summary": summary[:120],
            "duration_ms": max(0, int((time.perf_counter() - started) * 1000)),
        })

    def fail(self, key: str, summary: str) -> None:
        started = self._active.pop(key, time.perf_counter())
        self._steps.append({
            "agent_id": key,
            "agent_name": self._NAMES.get(key, key),
            "status": "error",
            "summary": summary[:120],
            "duration_ms": max(0, int((time.perf_counter() - started) * 1000)),
        })

    def snapshot(self, running_key: str | None = None) -> list[dict[str, Any]]:
        rows = [dict(step) for step in self._steps]
        for key, started in self._active.items():
            rows.append({
                "agent_id": key,
                "agent_name": self._NAMES.get(key, key),
                "status": "running",
                "summary": "处理中",
                "duration_ms": max(0, int((time.perf_counter() - started) * 1000)),
            })
        if running_key and running_key not in self._active:
            rows.append({
                "agent_id": running_key,
                "agent_name": self._NAMES.get(running_key, running_key),
                "status": "running",
                "summary": "处理中",
                "duration_ms": 0,
            })
        return rows


@dataclass(slots=True)
class _DispatchContext:
    session: AsyncSession
    chat_session: ChatSession
    user_id: int
    message: str
    request_filters: dict[str, Any]
    context_filters: dict[str, Any]
    compare_property_ids: list[int] | None
    mode: str
    memory_service: AgentMemoryService
    runtime: RuntimeMemory
    history: list[dict[str, str]]
    classification: dict[str, Any]
    intent: str
    stage: str
    resolved_ids: list[int]
    steps: _StepRecorder = field(default_factory=_StepRecorder)


def _public_intent(intent: str, sub_intent: str = "") -> str:
    """维持已有前端/API 意图名称，同时保留内部统一分类。"""
    if intent in {"search", "reference_detail"}:
        return "recommend"
    if intent == "manage_cart":
        return {
            "add": "add_to_cart",
            "remove": "remove_from_cart",
            "view": "manage_cart",
        }.get(sub_intent, "manage_cart")
    if intent == "compare":
        return "compare_cart"
    return intent


async def _prepare_context(
    *,
    session: AsyncSession,
    chat_session: ChatSession,
    user_id: int,
    message: str,
    filters: dict[str, Any] | None,
    context_filters: dict[str, Any] | None,
    compare_property_ids: list[int] | None,
    mode: str | None,
) -> _DispatchContext:
    from app.core.config import get_settings

    # StreamingResponse 启动生成器时，路由阶段加载的 ORM 对象可能已经 detached；
    # 重新绑定后，标题、累计筛选和旧库短期状态才能随消息一起提交。
    if sa_inspect(chat_session).detached:
        session.add(chat_session)

    steps = _StepRecorder()
    steps.start("memory")
    settings = get_settings()
    memory_service = AgentMemoryService(
        session,
        chat_session,
        user_id,
        long_term_enabled=bool(settings.agent_memory_enabled),
    )
    runtime = await memory_service.load(message)
    history = await load_packed_history(
        session,
        chat_session.id,
        rolling_summary=runtime.state.rolling_summary,
        char_budget=int(settings.agent_history_char_budget),
    )
    steps.done(
        "memory",
        f"恢复 {len(runtime.state.filters_json or {})} 个会话条件，保留 {len(history)} 条压缩上下文",
    )

    if runtime.reference_resolution.resolved_ids:
        steps.start("reference")
        steps.done(
            "reference",
            f"已解析为候选编号 {runtime.reference_resolution.resolved_ids}",
        )

    steps.start("router")
    classification = await classify_message(message, history)
    intent = str(classification.get("intent", "general"))
    faq_strength, faq_hits = match_faq(message)
    if compare_property_ids and len(compare_property_ids) >= 2:
        intent = "compare"
    elif faq_strength in {"strong", "weak"} and faq_hits:
        # FAQ chips 和明确政策问法必须能在 LLM 不可用时稳定命中。
        intent = "faq"
        classification["sub_intent"] = faq_hits[0].id if len(faq_hits) == 1 else "other"
        classification["faq_topic"] = faq_hits[0].id if len(faq_hits) == 1 else None
        classification["faq_confidence"] = "high" if faq_strength == "strong" else "low"
    elif len(runtime.reference_resolution.resolved_ids) >= 2 and re.search(r"(对比|比较|哪个好)", message):
        intent = "compare"
    elif (
        intent == "general"
        and runtime.state.last_search_json
        and _RELATIVE_SEARCH_PATTERN.search(message)
    ):
        intent = "search"
    if (
        len(runtime.reference_resolution.resolved_ids) == 1
        and _REFERENCE_DETAIL_PATTERN.search(message)
        and intent not in {"manage_cart", "compare"}
    ):
        intent = "reference_detail"
    classification["intent"] = intent
    stage = str(classification.get("stage", runtime.state.stage or "explore"))
    steps.done("router", f"意图={intent}，阶段={stage}")

    resolved_ids = list(runtime.reference_resolution.resolved_ids)
    if re.search(r"(全部|都加|所有)", message):
        resolved_ids = [
            int(value) for value in (runtime.state.last_search_json or {}).get("top_ids", [])
            if isinstance(value, int)
        ]
    elif (
        intent == "compare"
        and not compare_property_ids
        and not resolved_ids
        and _PLURAL_REFERENCE_PATTERN.search(message)
    ):
        # “这几套哪个好”默认指上一轮展示的 Top 候选，不再错误回退到购物车。
        resolved_ids = [
            int(value)
            for value in ((runtime.state.last_search_json or {}).get("top_ids") or [])[:5]
            if isinstance(value, int)
        ]

    context = _DispatchContext(
        session=session,
        chat_session=chat_session,
        user_id=user_id,
        message=message,
        request_filters=dict(filters or {}),
        context_filters=dict(context_filters or {}),
        compare_property_ids=compare_property_ids,
        mode=mode if mode in _VALID_MODES else "auto",
        memory_service=memory_service,
        runtime=runtime,
        history=history,
        classification=classification,
        intent=intent,
        stage=stage,
        resolved_ids=resolved_ids,
        steps=steps,
    )
    return context


async def _prepare_search(ctx: _DispatchContext) -> tuple[QueryUnderstanding, dict[str, Any]]:
    ctx.steps.start("rewrite")
    understanding = await understand_query(
        ctx.message,
        previous_filters={
            **(ctx.runtime.state.filters_json or {}),
            **ctx.context_filters,
        },
        rolling_summary=ctx.runtime.state.rolling_summary,
    )
    effective_filters = ctx.memory_service.merge_filters(
        ctx.runtime,
        message=ctx.message,
        extracted=understanding.extracted_filters,
        request_filters=ctx.request_filters,
        context_filters=ctx.context_filters,
        remove_fields=understanding.remove_fields,
        remove_values=understanding.remove_values,
    )
    summary = understanding.rewritten_query or ctx.message
    ctx.steps.done("rewrite", f"检索表达：{summary[:70]}")
    return understanding, effective_filters


def _base_result(ctx: _DispatchContext) -> dict[str, Any]:
    return {
        "reply": "",
        "intent": _public_intent(
            ctx.intent, str(ctx.classification.get("sub_intent", ""))
        ),
        "raw_intent": ctx.intent,
        "stage": ctx.stage,
        "recommendations": [],
        "top_picks": [],
        "cart_changed": False,
        "ai_available": get_llm_service().is_available,
        "quick_replies": [],
        "links": [],
        "guided_options": [],
        "thinking_steps": [],
        "sources": [],
        "relaxation_trace": [],
        "query_rewrite": None,
        "reference_resolution": {
            "resolved_ids": ctx.resolved_ids,
            "labels": ctx.runtime.reference_resolution.labels,
            "unresolved": ctx.runtime.reference_resolution.unresolved,
        },
        "filter_patch": {},
    }


def _build_filter_patch(
    understanding: QueryUnderstanding,
    effective_filters: dict[str, Any],
    *,
    reset: bool = False,
) -> dict[str, Any]:
    """生成普通搜索页可安全应用的本轮条件变更。"""
    if reset:
        return {field_name: None for field_name in _SEARCH_PAGE_FILTER_FIELDS}

    extracted = understanding.extracted_filters
    soft_fields = {
        str(field_name) for field_name in extracted.get("soft_preferences", [])
    }
    hard_fields = {
        str(field_name) for field_name in extracted.get("hard_filters", [])
    }

    def is_soft(field_name: str) -> bool:
        aliases = {
            "price_min": "price",
            "price_max": "price",
            "commute_minutes": "commute",
        }
        return (
            field_name not in hard_fields
            and (field_name in soft_fields or aliases.get(field_name) in soft_fields)
        )

    patch: dict[str, Any] = {}
    for field_name in _SEARCH_PAGE_FILTER_FIELDS:
        if field_name in extracted and not is_soft(field_name):
            patch[field_name] = effective_filters.get(field_name)

    for field_name in understanding.remove_fields:
        if field_name in _SEARCH_PAGE_FILTER_FIELDS:
            patch[field_name] = None
    for field_name in understanding.remove_values:
        if field_name in _SEARCH_PAGE_FILTER_FIELDS:
            patch[field_name] = effective_filters.get(field_name)
    return patch


def _needs_location_clarification(
    ctx: _DispatchContext,
    understanding: QueryUnderstanding,
) -> bool:
    """首次宽泛找房必须先确认市场，不能拿全库排序结果冒充用户偏好。"""
    if ctx.runtime.state.last_search_json:
        return False
    current_turn_sources = (
        understanding.extracted_filters,
        ctx.request_filters,
        ctx.context_filters,
    )
    return not any(
        source.get(field_name) not in (None, "")
        for source in current_turn_sources
        for field_name in _SEARCH_LOCATION_FIELDS
    )


def _build_location_clarification_result(
    ctx: _DispatchContext,
    understanding: QueryUnderstanding,
    effective_filters: dict[str, Any],
) -> dict[str, Any]:
    """保留已说出的预算/租期等条件，同时只追问缺失地点。"""
    ctx.runtime.state.stage = "explore"
    ctx.runtime.state.filters_json = dict(effective_filters)
    ctx.chat_session.accumulated_filters = dict(effective_filters)
    result = _base_result(ctx)
    result.update({
        "reply": (
            "可以，先告诉我你想在哪个国家、城市，或哪所学校附近找。"
            "也可以一起补充预算、房型和租期；地点确认前，我不会随便推荐某个区域的房源。"
        ),
        "quick_replies": ["新加坡找房", "英国找房", "美国找房"],
        "query_rewrite": {
            "original": ctx.message,
            "rewritten": understanding.rewritten_query or ctx.message,
            "kind": understanding.query_kind,
            "used_llm": understanding.used_llm,
        },
        "state_summary": build_state_summary("explore", effective_filters),
        "filter_patch": _build_filter_patch(
            understanding,
            effective_filters,
            reset=is_reset_request(ctx.message),
        ),
        "thinking_steps": ctx.steps.snapshot(),
    })
    return result


def _text_stream_chunks(text: str, chunk_size: int = 14) -> list[str]:
    """把确定性工作流文案拆成连续 SSE 文本块，并保持拼接后内容完全一致。"""
    if not text:
        return []
    size = max(1, int(chunk_size))
    return [text[index:index + size] for index in range(0, len(text), size)]


async def _paced_text_stream(text: str, chunk_size: int = 14):
    """将确定性回复分帧发送，确保浏览器能逐段绘制而不是同一帧整段出现。"""
    chunks = _text_stream_chunks(text, chunk_size)
    for index, chunk in enumerate(chunks):
        yield chunk
        if index < len(chunks) - 1:
            await asyncio.sleep(0.018)


_FOLLOWUP_AMENITY_ALIASES: dict[str, tuple[str, ...]] = {
    "健身房": ("健身房", "健身", "gym", "fitness"),
    "自习室": ("自习室", "自习空间", "学习室", "study room"),
    "泳池": ("泳池", "游泳池", "pool"),
    "独立卫浴": ("独立卫浴", "独卫", "ensuite"),
    "空调": ("空调", "air conditioning", "aircon"),
    "电梯": ("电梯", "lift", "elevator"),
    "洗衣机": ("洗衣机", "washer", "washing machine"),
    "WiFi": ("wifi", "wi-fi", "无线网"),
}


def _amenity_values(value: Any) -> list[str]:
    """兼容数组、JSON 文本和逗号文本三种设施存储。"""
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    return [
        part.strip()
        for part in value.replace("，", ",").split(",")
        if part.strip()
    ]


def _requested_amenities(message: str) -> list[str]:
    """识别设施追问中的全部标准设施名。"""
    lowered = message.lower()
    return [
        canonical
        for canonical, aliases in _FOLLOWUP_AMENITY_ALIASES.items()
        if any(alias.lower() in lowered for alias in aliases)
    ]


def _requested_amenity(message: str) -> str | None:
    """向后兼容：返回设施追问中识别到的第一项。"""
    values = _requested_amenities(message)
    return values[0] if values else None


def _listed_amenities(*raw_sources: Any) -> list[str]:
    """合并并去重房源、户型和公寓三层设施清单。"""
    values = [item for raw in raw_sources for item in _amenity_values(raw)]
    return list(dict.fromkeys(values))


def _set_reference_focus(ctx: _DispatchContext, property_id: int) -> None:
    """把本轮实际查看的房源设为后续“它/这个”的焦点。"""
    reference_map = dict(ctx.runtime.state.reference_map_json or {})
    semantic_refs = dict(reference_map.get("semantic_refs") or {})
    semantic_refs["last_focus"] = property_id
    reference_map["semantic_refs"] = semantic_refs
    reference_map["last_focus_id"] = property_id
    ctx.runtime.state.reference_map_json = reference_map


def build_amenity_followup_answer(
    *,
    property_name: str,
    requested_amenity: str,
    unit_amenities: Any,
    institute_amenities: Any,
    legacy_amenities: Any,
) -> tuple[str, bool]:
    """仅依据房源、公寓设施字段回答设施追问，返回文本和数据是否已知。"""
    raw_sources = (unit_amenities, institute_amenities, legacy_amenities)
    data_known = any(value is not None for value in raw_sources)
    listed = {
        item.strip().lower()
        for raw in raw_sources
        for item in _amenity_values(raw)
        if item.strip()
    }
    aliases = {
        alias.lower()
        for alias in _FOLLOWUP_AMENITY_ALIASES.get(
            requested_amenity, (requested_amenity,)
        )
    }
    if listed.intersection(aliases):
        return (
            f"有。{property_name}的房源或公寓配套清单明确列有{requested_amenity}。"
            "如果你问的是楼外附近的独立场所，当前周边数据还不能据此确认。",
            True,
        )
    if data_known:
        return (
            f"当前楼内/公寓设施清单没有列出{requested_amenity}。"
            f"这不等于{property_name}周边一定没有独立场所，预订前可以再向公寓确认。",
            True,
        )
    return (
        f"暂时无法确认。{property_name}的楼内设施和周边场所数据还没有录入，"
        f"不能据此判断是否有{requested_amenity}，建议向公寓确认。",
        False,
    )


def _nearby_amenity_scope_note(message: str) -> str | None:
    """为“附近有设施”的搜索补充楼内与楼外事实边界。"""
    if not re.search(r"(附近|边上|周边|旁边)", message):
        return None
    amenities = _requested_amenities(message)
    if not amenities:
        return None
    joined = "、".join(amenities)
    return (
        f"范围说明：本次把“{joined}”按楼内/公寓配套清单进行匹配。"
        "楼外附近的独立场所需要可核实的 POI 与距离数据；"
        "当前结果没有这类周边数据，因此不能据此确认楼外附近一定有。"
    )


def _infer_compare_priority(ctx: _DispatchContext) -> str:
    """结合本轮原话和已记住条件选择可解释的对比重点。"""
    if re.search(r"(预算|价格|便宜|省钱|性价比)", ctx.message):
        return "budget"
    if re.search(r"(通勤|学校|大学|地铁|公交|距离|附近|离.+近)", ctx.message):
        return "commute"
    if re.search(r"(面积|空间|宽敞|更大)", ctx.message):
        return "space"

    filters = ctx.runtime.state.filters_json or {}
    if filters.get("commute_minutes") is not None or filters.get("institution"):
        return "commute"
    if filters.get("price_min") is not None or filters.get("price_max") is not None:
        return "budget"
    if filters.get("area_min") is not None or filters.get("area_max") is not None:
        return "space"
    return "balanced"


def _remember_compare_references(
    ctx: _DispatchContext,
    compare_items: list[dict[str, Any]],
) -> None:
    """记住本轮对比顺序和最高分候选，供后续「第 2 套/它」解析。"""
    compared_ids = [
        int(item["property_id"])
        for item in compare_items
        if isinstance(item.get("property_id"), int)
    ]
    if not compared_ids:
        return
    best_id = compared_ids[0]
    ctx.runtime.state.reference_map_json = {
        "ordinal_refs": {
            str(index): property_id
            for index, property_id in enumerate(compared_ids, 1)
        },
        "semantic_refs": {
            "best_overall": best_id,
            "last_focus": best_id,
        },
        "last_focus_id": best_id,
    }


async def _execute_search(ctx: _DispatchContext) -> dict[str, Any]:
    understanding, filters = await _prepare_search(ctx)
    if _needs_location_clarification(ctx, understanding):
        return _build_location_clarification_result(ctx, understanding, filters)
    ctx.steps.start("retrieve")
    search_result = await SearchAgent(session=ctx.session).search(
        message=ctx.message,
        filters=filters,
        understanding=understanding,
        stage=ctx.stage,
    )
    ctx.steps.done(
        "retrieve",
        f"召回并重排 {len(search_result.get('recommendations', []))} 套候选",
    )
    ctx.steps.start("ground")
    explicit_filters = {
        **understanding.extracted_filters,
        **ctx.request_filters,
    }
    await ctx.memory_service.save_search(
        ctx.runtime,
        stage=ctx.stage,
        effective_filters=search_result.get("effective_filters") or filters,
        explicit_filters=explicit_filters,
        candidates=search_result.get("unit_results") or [],
        original_query=ctx.message,
        rewritten_query=understanding.rewritten_query or None,
        relaxation_trace=search_result.get("relaxation_trace") or [],
        source_manifest=search_result.get("source_manifest") or {},
        latency_ms=int(search_result.get("latency_ms", 0) or 0),
        remove_fields=understanding.remove_fields,
        remove_values=understanding.remove_values,
        reset_memory=is_reset_request(ctx.message),
    )
    ctx.steps.done("ground", "回复只使用已标注来源的候选事实")

    result = _base_result(ctx)
    result.update({
        "reply": search_result.get("reply", ""),
        "recommendations": search_result.get("recommendations", []),
        "top_picks": search_result.get("top_picks", []),
        "guided_options": search_result.get("guided_options", []),
        "sources": search_result.get("sources", []),
        "relaxation_trace": search_result.get("relaxation_trace", []),
        "query_rewrite": {
            "original": ctx.message,
            "rewritten": understanding.rewritten_query or ctx.message,
            "kind": understanding.query_kind,
            "used_llm": understanding.used_llm,
        },
        "relaxation_level": search_result.get("relaxation_level", 0),
        "candidate_snapshot": search_result.get("candidate_snapshot", []),
        "source_info": search_result.get("source_info", ""),
        "state_summary": build_state_summary(
            ctx.stage,
            search_result.get("effective_filters") or filters,
        ),
        "filter_patch": _build_filter_patch(
            understanding,
            search_result.get("effective_filters") or filters,
            reset=is_reset_request(ctx.message),
        ),
    })
    nearby_scope_note = _nearby_amenity_scope_note(ctx.message)
    if nearby_scope_note:
        reply = str(result.get("reply") or "").rstrip()
        result["reply"] = f"{reply}\n\n{nearby_scope_note}" if reply else nearby_scope_note
        result["sources"] = [
            *result.get("sources", []),
            {"label": "楼外周边 POI", "status": "missing"},
        ]
    result["thinking_steps"] = ctx.steps.snapshot()
    return result


async def _execute_non_search(ctx: _DispatchContext) -> dict[str, Any]:
    result = _base_result(ctx)
    if ctx.intent == "reference_detail":
        ctx.steps.start("reference")
        from sqlalchemy import select
        from app.models.institute import Institute
        from app.models.property import Property
        from app.models.unit_type import UnitType
        from sqlalchemy.orm.attributes import set_committed_value

        property_id = ctx.resolved_ids[0]
        from app.services.property_service import PropertyService

        prop = await PropertyService(ctx.session).get(property_id)
        unit_type = None
        institute = None
        if prop is not None and prop.unit_type_id is not None:
            row = (
                await ctx.session.execute(
                    select(UnitType, Institute)
                    .join(Institute, UnitType.institute_id == Institute.id)
                    .where(UnitType.id == prop.unit_type_id)
                )
            ).first()
            if row:
                unit_type, institute = row
                set_committed_value(unit_type, "institute", institute)
        elif prop is not None and prop.institute_id is not None:
            institute = await ctx.session.get(Institute, prop.institute_id)

        if prop is not None:
            display_property = unit_type or prop
            name = (
                f"{institute.name} 的 {unit_type.name}"
                if unit_type is not None and institute is not None
                else str(prop.title or f"房源 {prop.id}")
            )
            price = (
                prop.price_monthly
                if prop.price_monthly is not None
                else getattr(unit_type, "base_rent", None)
            )
            currency = prop.currency or getattr(unit_type, "currency", None) or ""
            bedrooms = prop.bedrooms if prop.bedrooms is not None else getattr(unit_type, "bedrooms", 0)
            bathrooms = prop.bathrooms if prop.bathrooms is not None else getattr(unit_type, "bathrooms", 0)
            area = prop.area_sqm if prop.area_sqm is not None else getattr(unit_type, "area_sqm", None)
            description = prop.description or getattr(unit_type, "description", None)
            missing: list[str] = []
            if area is None:
                missing.append("面积")
            if not description:
                missing.append("详细描述")
            facts = [
                name,
                f"月租 {currency}{float(price):.0f}" if price is not None else "月租待确认",
                f"{int(bedrooms or 0)}室{int(bathrooms or 0)}卫",
            ]
            if area is not None:
                facts.append(f"约 {float(area):g}㎡")
            requested_amenities = _requested_amenities(ctx.message)
            asks_amenity_overview = bool(
                re.search(r"(有哪些|有什么|列一下|介绍).{0,6}(设施|配套)|设施.{0,3}(有哪些|有什么)", ctx.message)
            )
            facility_data_known = True
            raw_amenity_sources = (
                getattr(unit_type, "amenities", None),
                getattr(institute, "amenities", None),
                getattr(prop, "institute_amenities", None),
            )
            if requested_amenities:
                answers: list[str] = []
                known_flags: list[bool] = []
                for requested_amenity in requested_amenities:
                    answer, known = build_amenity_followup_answer(
                        property_name=name,
                        requested_amenity=requested_amenity,
                        unit_amenities=raw_amenity_sources[0],
                        institute_amenities=raw_amenity_sources[1],
                        legacy_amenities=raw_amenity_sources[2],
                    )
                    answers.append(answer)
                    known_flags.append(known)
                result["reply"] = "\n".join(answers)
                facility_data_known = all(known_flags)
                if not facility_data_known:
                    missing.append("设施")
            elif asks_amenity_overview:
                listed_amenities = _listed_amenities(*raw_amenity_sources)
                facility_data_known = any(value is not None for value in raw_amenity_sources)
                if listed_amenities:
                    result["reply"] = (
                        f"{name}当前明确列出的楼内/公寓设施有："
                        f"{'、'.join(listed_amenities)}。楼外周边场所需以周边数据另行确认。"
                    )
                elif facility_data_known:
                    result["reply"] = f"{name}当前设施清单为空，建议预订前向公寓确认。"
                else:
                    result["reply"] = f"{name}暂未录入设施清单，建议向公寓确认。"
                    missing.append("设施")
            else:
                result["reply"] = "，".join(facts) + "。"
                if missing:
                    result["reply"] += f"目前{'、'.join(missing)}数据暂缺，建议向公寓确认。"
            result["recommendations"] = [{
                "property_id": int(prop.id),
                "rank": 1,
                "match_reason": "来自上一轮候选",
                "pros": [],
                "cons": [f"{name}待确认" for name in missing],
                "property": display_property,
                "poi_distances": {},
                "source_metadata": {
                    "property": "unit_types" if unit_type is not None else "properties",
                    "institute": "institutes" if institute is not None else "properties.flattened",
                    "inventory": "properties.status",
                    "amenities": (
                        "unit_types/institutes/properties"
                        if facility_data_known else "missing"
                    ),
                    "missing_fields": list(dict.fromkeys(missing)),
                },
            }]
            result["top_picks"] = list(result["recommendations"])
            result["sources"] = [
                {"label": "房源基础信息", "status": "verified"},
                {"label": "实时库存", "status": "verified"},
            ]
            if requested_amenities or asks_amenity_overview:
                result["sources"].append({
                    "label": "设施清单",
                    "status": "verified" if facility_data_known else "missing",
                })
            _set_reference_focus(ctx, int(prop.id))
            ctx.steps.done("reference", f"已读取上一轮房源 {property_id} 的真实字段")
        else:
            result["reply"] = "这套房源目前查不到了，可能已经下架。要不要回到上一轮结果重新选？"
            ctx.steps.fail("reference", "候选已不存在")

    elif ctx.intent == "compare":
        ctx.steps.start("compare")
        property_ids = ctx.compare_property_ids or ctx.resolved_ids or None
        try:
            compare_result = await CompareAgent(session=ctx.session).compare(
                user_id=ctx.user_id,
                property_ids=property_ids,
                priority=_infer_compare_priority(ctx),
                cart_agent=CartService(session=ctx.session),
            )
            result["reply"] = (
                compare_result.get("dimension_analysis", "")
                or compare_result.get("summary", "")
            )
            compare_items = compare_result.get("items", [])
            result["recommendations"] = compare_items
            _remember_compare_references(ctx, compare_items)
            ctx.steps.done("compare", f"完成 {len(compare_items)} 套对比")
        except ValueError as exc:
            result["reply"] = str(exc)
            ctx.steps.fail("compare", str(exc))

    elif ctx.intent == "manage_cart":
        ctx.steps.start("cart")
        sub_intent = str(ctx.classification.get("sub_intent", "view"))
        cart_service = CartService(session=ctx.session)
        ids = _extract_explicit_ids(ctx.message) or ctx.resolved_ids
        if sub_intent == "add":
            if ids:
                for property_id in ids:
                    try:
                        await cart_service.add_to_cart(ctx.user_id, property_id)
                    except ValueError:
                        continue
                result["reply"] = "已把你指的房源加入候选清单。"
                result["cart_changed"] = True
            else:
                result["reply"] = "我还不能确定你指的是哪套，请说“第 1 套”或点卡片上的加入按钮。"
        elif sub_intent == "remove":
            if ids:
                for property_id in ids:
                    await cart_service.remove_from_cart(ctx.user_id, property_id)
                result["reply"] = "已从候选清单移除。"
                result["cart_changed"] = True
            else:
                result["reply"] = "请告诉我要移除第几套。"
        else:
            _cart, items = await cart_service.get_cart_items(ctx.user_id)
            result["reply"] = f"候选清单里现在有 {len(items)} 套。" if items else "候选清单还是空的。"
        ctx.steps.done("cart", result["reply"])

    elif ctx.intent == "faq":
        ctx.steps.start("faq")
        strength, hits = match_faq(ctx.message)
        if strength == "strong" and hits:
            entry = hits[0]
            result["reply"] = entry.answer
            result["quick_replies"] = list(entry.next_chips or [])
            result["links"] = [
                {"label": link.label, "to": link.to} for link in entry.links
            ]
        elif strength == "weak" and hits:
            result["reply"] = f"你想了解的是 {' / '.join(entry.chip for entry in hits[:5])} 中的哪个？"
            result["quick_replies"] = [entry.chip for entry in hits[:5]]
        else:
            topic = str(
                ctx.classification.get("faq_topic")
                or ctx.classification.get("sub_intent")
                or ""
            )
            entry = get_faq(topic)
            if entry:
                result["reply"] = entry.answer
                result["quick_replies"] = list(entry.next_chips or [])
                result["links"] = [
                    {"label": link.label, "to": link.to} for link in entry.links
                ]
            else:
                result["reply"] = "这个问题暂时没有可靠的平台资料，建议联系人工客服确认。"
        ctx.steps.done("faq", "已从平台 FAQ 中匹配答案")

    else:
        llm = get_llm_service()
        if llm.is_available:
            messages = [{
                "role": "system",
                "content": "你是留学生租房顾问，用自然中文简洁回答。不得编造具体房源、政策或费用；缺少来源时明确建议确认。",
            }]
            messages.extend(ctx.history)
            messages.append({"role": "user", "content": ctx.message})
            result["reply"] = await llm.complete_text(
                messages,
                temperature=0.6,
                max_tokens=500,
            )
        else:
            result["reply"] = "我是租房推荐助手。告诉我学校、预算和户型，我可以接着帮你找。"

    ctx.runtime.state.stage = ctx.stage
    result["state_summary"] = build_state_summary(
        ctx.stage, ctx.runtime.state.filters_json or {}
    )
    result["thinking_steps"] = ctx.steps.snapshot()
    return result


async def _execute_compare_stream(ctx: _DispatchContext):
    """对比结构由确定性评分生成，用户可见说明透传模型增量。"""
    result = _base_result(ctx)
    ctx.steps.start("compare")
    property_ids = ctx.compare_property_ids or ctx.resolved_ids or None
    try:
        stream_meta: dict[str, Any] = {}
        async for event in CompareAgent(session=ctx.session).compare_stream(
            user_id=ctx.user_id,
            property_ids=property_ids,
            priority=_infer_compare_priority(ctx),
            cart_agent=CartService(session=ctx.session),
        ):
            if event.get("type") == "token":
                token = str(event.get("text") or "")
                if token:
                    if len(token) > 28:
                        async for chunk in _paced_text_stream(token):
                            yield chunk, None
                    else:
                        yield token, None
            elif event.get("type") == "meta":
                stream_meta = event

        compare_items = list(stream_meta.get("items") or [])
        recommendations = [
            {
                **item,
                "rank": index,
                "match_reason": str(item.get("best_for") or "对比候选"),
                "source_metadata": {
                    "property": "properties",
                    "ranking": "deterministic_compare_ranking",
                },
            }
            for index, item in enumerate(compare_items, 1)
        ]
        result.update({
            "reply": str(stream_meta.get("reply") or ""),
            "recommendations": recommendations,
            "ai_available": bool(stream_meta.get("ai_available", False)),
        })
        _remember_compare_references(ctx, compare_items)
        ctx.steps.done("compare", f"完成 {len(compare_items)} 套对比")
    except ValueError as exc:
        result["reply"] = str(exc)
        ctx.steps.fail("compare", str(exc))
        yield result["reply"], None

    ctx.runtime.state.stage = ctx.stage
    result["state_summary"] = build_state_summary(
        ctx.stage, ctx.runtime.state.filters_json or {}
    )
    result["thinking_steps"] = ctx.steps.snapshot()
    yield None, result


async def _execute_general_stream(ctx: _DispatchContext):
    """闲聊分支直接透传上游 LLM 增量，避免先等完整补全再整段返回。"""
    result = _base_result(ctx)
    llm = get_llm_service()
    reply = ""
    stream_failed = False
    if llm.is_available:
        messages = [{
            "role": "system",
            "content": "你是留学生租房顾问，用自然中文简洁回答。不得编造具体房源、政策或费用；缺少来源时明确建议确认。",
        }]
        messages.extend(ctx.history)
        messages.append({"role": "user", "content": ctx.message})
        try:
            async for token in llm.complete_text_stream(
                messages,
                temperature=0.6,
                max_tokens=500,
            ):
                if not token:
                    continue
                reply += token
                yield token, None
        except Exception:
            stream_failed = True
            result["ai_available"] = False
            logger.exception("通用 Agent 上游流式回复中断")

    if not reply or stream_failed:
        fallback = "我是租房推荐助手。告诉我学校、预算和户型，我可以接着帮你找。"
        continuation = f"\n\n{fallback}" if reply else fallback
        reply += continuation
        async for chunk in _paced_text_stream(continuation):
            yield chunk, None

    result["reply"] = reply
    ctx.runtime.state.stage = ctx.stage
    result["state_summary"] = build_state_summary(
        ctx.stage, ctx.runtime.state.filters_json or {}
    )
    result["thinking_steps"] = ctx.steps.snapshot()
    yield None, result


async def _persist_messages(ctx: _DispatchContext, result: dict[str, Any]) -> None:
    await ctx.memory_service.sync_legacy_state(ctx.runtime)
    recommendations = result.get("recommendations") or []
    user_message = ChatMessage(
        session_id=ctx.chat_session.id,
        role=ChatMessageRole.user,
        content=ctx.message,
        metadata_={
            "filters": ctx.request_filters,
            "resolved_ids": ctx.resolved_ids,
            "mode": ctx.mode,
        },
    )
    assistant_message = ChatMessage(
        session_id=ctx.chat_session.id,
        role=ChatMessageRole.assistant,
        content=result.get("reply", ""),
        metadata_={
            "intent": result.get("intent"),
            "raw_intent": result.get("raw_intent"),
            "stage": result.get("stage"),
            "query_rewrite": result.get("query_rewrite"),
            "sources": result.get("sources", []),
            "quick_replies": result.get("quick_replies", []),
            "guided_options": result.get("guided_options", []),
            "state_summary": result.get("state_summary"),
            "recommendations": [
                {
                    "property_id": item.get("property_id", item.get("id", 0)),
                    "match_reason": item.get("match_reason", ""),
                }
                for item in recommendations
            ],
        },
    )
    # 对话记录按最近消息排序；首轮用真实问题生成可辨识标题。
    ctx.chat_session.updated_at = datetime.now(timezone.utc)
    if not ctx.history and ctx.chat_session.title in {None, "租房推荐 Agent"}:
        ctx.chat_session.title = ctx.message.strip().replace("\n", " ")[:60]
    ctx.session.add_all([user_message, assistant_message])
    await ctx.session.commit()


async def dispatch(
    session: AsyncSession,
    chat_session: ChatSession,
    user_id: int,
    message: str,
    filters: dict[str, Any] | None = None,
    context_filters: dict[str, Any] | None = None,
    compare_property_ids: list[int] | None = None,
    mode: str | None = None,
) -> dict[str, Any]:
    """主入口：恢复记忆 → 分类 → 执行 → 原子持久化。"""
    ctx = await _prepare_context(
        session=session,
        chat_session=chat_session,
        user_id=user_id,
        message=message,
        filters=filters,
        context_filters=context_filters,
        compare_property_ids=compare_property_ids,
        mode=mode,
    )
    result = await _execute_search(ctx) if ctx.intent == "search" else await _execute_non_search(ctx)
    await _persist_messages(ctx, result)
    return result


async def dispatch_stream(
    session: AsyncSession,
    chat_session: ChatSession,
    user_id: int,
    message: str,
    filters: dict[str, Any] | None = None,
    context_filters: dict[str, Any] | None = None,
    compare_property_ids: list[int] | None = None,
    mode: str | None = None,
):
    """流式分发；先发执行状态，再逐 token 发有据回答，最后发卡片元数据。"""
    ctx = await _prepare_context(
        session=session,
        chat_session=chat_session,
        user_id=user_id,
        message=message,
        filters=filters,
        context_filters=context_filters,
        compare_property_ids=compare_property_ids,
        mode=mode,
    )
    yield None, {
        "event": "status",
        "intent": _public_intent(ctx.intent, str(ctx.classification.get("sub_intent", ""))),
        "thinking_steps": ctx.steps.snapshot("rewrite" if ctx.intent == "search" else None),
    }

    if ctx.intent != "search":
        if ctx.intent in {"compare", "general"}:
            result: dict[str, Any] | None = None
            result_stream = (
                _execute_compare_stream(ctx)
                if ctx.intent == "compare"
                else _execute_general_stream(ctx)
            )
            async for token, completed_result in result_stream:
                if token:
                    yield token, None
                if completed_result is not None:
                    result = completed_result
            if result is None:
                raise RuntimeError(f"{ctx.intent} Agent 流未返回最终结果")
        else:
            result = await _execute_non_search(ctx)
            reply = str(result.get("reply") or "")
            async for chunk in _paced_text_stream(reply):
                yield chunk, None
        yield None, {"event": "result", **_stream_safe_result(result)}
        await _persist_messages(ctx, result)
        return

    understanding, effective_filters = await _prepare_search(ctx)
    yield None, {
        "event": "status",
        "intent": "recommend",
        "thinking_steps": ctx.steps.snapshot("retrieve"),
        "query_rewrite": {
            "original": ctx.message,
            "rewritten": understanding.rewritten_query or ctx.message,
            "kind": understanding.query_kind,
            "used_llm": understanding.used_llm,
        },
    }

    if _needs_location_clarification(ctx, understanding):
        result = _build_location_clarification_result(
            ctx,
            understanding,
            effective_filters,
        )
        async for chunk in _paced_text_stream(str(result.get("reply") or "")):
            yield chunk, None
        yield None, {"event": "result", **_stream_safe_result(result)}
        await _persist_messages(ctx, result)
        return

    ctx.steps.start("retrieve")
    full_reply = ""
    search_meta: dict[str, Any] = {}
    async for event in SearchAgent(session=ctx.session).search_stream(
        message=ctx.message,
        filters=effective_filters,
        understanding=understanding,
        stage=ctx.stage,
    ):
        if event["type"] == "token":
            full_reply += event["text"]
            yield event["text"], None
        elif event["type"] == "meta":
            search_meta = event

    ctx.steps.done(
        "retrieve",
        f"召回并重排 {len(search_meta.get('recommendations', []))} 套候选",
    )
    ctx.steps.start("ground")
    explicit_filters = {**understanding.extracted_filters, **ctx.request_filters}
    await ctx.memory_service.save_search(
        ctx.runtime,
        stage=ctx.stage,
        effective_filters=search_meta.get("effective_filters") or effective_filters,
        explicit_filters=explicit_filters,
        candidates=search_meta.get("unit_results") or [],
        original_query=ctx.message,
        rewritten_query=understanding.rewritten_query or None,
        relaxation_trace=search_meta.get("relaxation_trace") or [],
        source_manifest=search_meta.get("source_manifest") or {},
        latency_ms=int(search_meta.get("latency_ms", 0) or 0),
        remove_fields=understanding.remove_fields,
        remove_values=understanding.remove_values,
        reset_memory=is_reset_request(ctx.message),
    )
    ctx.steps.done("ground", "回复只使用已标注来源的候选事实")

    result = _base_result(ctx)
    result.update({
        "reply": search_meta.get("reply") or full_reply,
        "recommendations": search_meta.get("recommendations", []),
        "top_picks": search_meta.get("top_picks", []),
        "ai_available": bool(search_meta.get("ai_available", result["ai_available"])),
        "guided_options": search_meta.get("guided_options", []),
        "sources": search_meta.get("sources", []),
        "relaxation_trace": search_meta.get("relaxation_trace", []),
        "relaxation_level": search_meta.get("relaxation_level", 0),
        "candidate_snapshot": search_meta.get("candidate_snapshot", []),
        "query_rewrite": {
            "original": ctx.message,
            "rewritten": understanding.rewritten_query or ctx.message,
            "kind": understanding.query_kind,
            "used_llm": understanding.used_llm,
        },
        "state_summary": build_state_summary(
            ctx.stage,
            search_meta.get("effective_filters") or effective_filters,
        ),
        "filter_patch": _build_filter_patch(
            understanding,
            search_meta.get("effective_filters") or effective_filters,
            reset=is_reset_request(ctx.message),
        ),
        "thinking_steps": ctx.steps.snapshot(),
    })
    nearby_scope_note = _nearby_amenity_scope_note(ctx.message)
    if nearby_scope_note:
        reply = str(result.get("reply") or "").rstrip()
        note_text = f"\n\n{nearby_scope_note}"
        result["reply"] = f"{reply}{note_text}" if reply else nearby_scope_note
        # 搜索流已经把正文 token 发出，需要把事实边界作为最后一段继续推给前端。
        yield note_text if reply else nearby_scope_note, None
        result["sources"] = [
            *result.get("sources", []),
            {"label": "楼外周边 POI", "status": "missing"},
        ]
    yield None, {"event": "result", **_stream_safe_result(result)}
    await _persist_messages(ctx, result)


def _stream_safe_result(result: dict[str, Any]) -> dict[str, Any]:
    """剔除 ORM/内部字段，只留下 SSE 可序列化响应数据。"""
    allowed = {
        "intent", "raw_intent", "stage", "recommendations", "top_picks",
        "cart_changed", "ai_available", "quick_replies", "links",
        "guided_options", "thinking_steps", "sources", "relaxation_trace",
        "query_rewrite", "reference_resolution", "state_summary",
        "relaxation_level", "candidate_snapshot", "filter_patch",
    }
    return {key: value for key, value in result.items() if key in allowed}


def _extract_explicit_ids(message: str) -> list[int]:
    """只提取明确写成“房源 123”的真实 ID；序号由 Memory 引用表解析。"""
    return list(dict.fromkeys(
        int(match.group(1))
        for match in re.finditer(r"房源\s*#?\s*(\d+)", message)
    ))
