"""Agent 记忆服务 —— 对话状态、跨会话偏好、指代解析与检索审计。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.agent_intelligence import (
    AgentSearchCandidate,
    AgentSearchRun,
    AgentSessionState,
    AgentUserMemory,
)
from app.models.chat import ChatSession


FILTER_FIELDS = frozenset({
    "country", "district", "price_min", "price_max", "bedrooms",
    "property_type", "amenities", "room_type", "bathrooms", "area_min",
    "area_max", "min_lease_months", "max_lease_months", "available_from",
    "poi_requirements", "commute_mode", "commute_minutes", "institution",
    "female_only", "hard_filters", "soft_preferences", "currency",
})
LIST_FILTER_FIELDS = frozenset({"amenities", "poi_requirements", "hard_filters", "soft_preferences"})

# 单次会话结束后仍较稳定的字段，第一次明确表达即可作为长期偏好使用。
STABLE_MEMORY_FIELDS = frozenset({
    "country", "institution", "property_type", "room_type", "commute_mode",
    "female_only",
})
MEMORY_APPLY_THRESHOLD = 0.75
LEGACY_STATE_KEY = "__agent_state__"

_RESET_ALL = re.compile(r"(重新开始|从头开始|清空条件|清掉.*条件|不要之前的|重置条件)")
_REMOVE_FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    "district": re.compile(r"(区域|地区|位置).{0,5}(不限|取消|无所谓)|不限区域"),
    "price_min": re.compile(r"(最低预算|价格下限).{0,5}(不限|取消)"),
    "price_max": re.compile(r"(预算|价格上限).{0,5}(不限|取消|无所谓)|不限制预算"),
    "bedrooms": re.compile(r"(户型|卧室|几室).{0,5}(不限|取消|无所谓)"),
    "property_type": re.compile(r"(房源类型|公寓类型|类型).{0,5}(不限|取消|无所谓)"),
    "amenities": re.compile(r"(设施|配套).{0,5}(不限|取消|无所谓)"),
    "institution": re.compile(r"(学校|大学).{0,5}(不限|取消|无所谓)"),
    "commute_minutes": re.compile(r"(通勤|距离).{0,5}(不限|取消|无所谓)"),
}

_CN_NUM = {
    "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}


@dataclass(slots=True)
class ReferenceResolution:
    """一次用户指代解析结果。"""

    resolved_ids: list[int] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RuntimeMemory:
    """当前请求可直接使用的会话状态快照。"""

    state: AgentSessionState
    user_memory: AgentUserMemory
    memory_filters: dict[str, Any]
    reference_resolution: ReferenceResolution


def _is_present(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _dedupe_list(values: list[Any]) -> list[Any]:
    """按 JSON 值去重，兼容 POI 的字典列表。"""
    result: list[Any] = []
    seen: set[str] = set()
    for value in values:
        marker = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        if marker not in seen:
            result.append(value)
            seen.add(marker)
    return result


def detect_removed_fields(message: str, explicit_remove_fields: list[str] | None = None) -> list[str]:
    """结合 LLM 输出与确定性规则识别本轮要清除的筛选字段。"""
    removed = [f for f in (explicit_remove_fields or []) if f in FILTER_FIELDS]
    for field_name, pattern in _REMOVE_FIELD_PATTERNS.items():
        if pattern.search(message):
            removed.append(field_name)
            if field_name == "commute_minutes":
                removed.append("commute_mode")
    return list(dict.fromkeys(removed))


def is_reset_request(message: str) -> bool:
    """用户是否明确要求清空当前条件及对应长期偏好。"""
    return bool(_RESET_ALL.search(message))


def merge_dialogue_filters(
    *,
    message: str,
    previous: dict[str, Any] | None,
    memory_filters: dict[str, Any] | None,
    extracted: dict[str, Any] | None,
    request_filters: dict[str, Any] | None,
    remove_fields: list[str] | None = None,
    remove_values: dict[str, list[Any]] | None = None,
) -> dict[str, Any]:
    """按「长期记忆 < 会话状态 < 本轮理解 < 前端显式值」合并筛选条件。

    列表字段默认增量合并；用户明确说取消/不要时才删除，避免多轮对话里
    一句话把前面已经确认的独卫、通勤等条件静默覆盖掉。
    """
    merged: dict[str, Any] = {}
    if not _RESET_ALL.search(message):
        for source in (memory_filters or {}, previous or {}):
            for key, value in source.items():
                if key in FILTER_FIELDS and _is_present(value):
                    merged[key] = value

    for key in detect_removed_fields(message, remove_fields):
        merged.pop(key, None)

    for source in (extracted or {}, request_filters or {}):
        for key, value in source.items():
            if key not in FILTER_FIELDS or not _is_present(value):
                continue
            if key in LIST_FILTER_FIELDS and isinstance(value, list):
                existing = merged.get(key)
                prior = existing if isinstance(existing, list) else []
                merged[key] = _dedupe_list([*prior, *value])
            else:
                merged[key] = value

    for key, values in (remove_values or {}).items():
        if key not in LIST_FILTER_FIELDS or not isinstance(values, list):
            continue
        existing = merged.get(key)
        if not isinstance(existing, list):
            continue
        # 直接用字符串比较，避免 JSON 序列化中文不一致
        remove_set = {str(v).strip() for v in values}
        merged[key] = [v for v in existing if str(v).strip() not in remove_set]
        if not merged[key]:
            merged.pop(key, None)

    # 防止上一轮元数据引用了已经被清掉的字段。
    for meta_key in ("hard_filters", "soft_preferences"):
        values = merged.get(meta_key)
        if isinstance(values, list):
            merged[meta_key] = [v for v in values if v in merged or v not in FILTER_FIELDS]

    return merged


def memory_to_filters(preferences: dict[str, Any] | None) -> dict[str, Any]:
    """只取达到置信阈值的长期记忆，避免一次临时搜索永久污染偏好。"""
    result: dict[str, Any] = {}
    for field_name, record in (preferences or {}).items():
        if field_name not in FILTER_FIELDS or not isinstance(record, dict):
            continue
        confidence = float(record.get("confidence", 0.0) or 0.0)
        value = record.get("value")
        if confidence >= MEMORY_APPLY_THRESHOLD and _is_present(value):
            result[field_name] = value
    return result


async def get_user_memory(
    session: AsyncSession,
    user_id: int,
) -> AgentUserMemory | None:
    """读取当前用户长期记忆；不存在时不隐式创建。"""
    if not await _has_table(session, "agent_user_memories"):
        return None
    return await session.scalar(
        select(AgentUserMemory).where(AgentUserMemory.user_id == user_id)
    )


async def save_user_memory(
    session: AsyncSession,
    user_id: int,
    preferences: dict[str, Any],
    *,
    replace: bool = False,
) -> AgentUserMemory:
    """显式保存用户确认的偏好，置信度固定为 1，供后续会话直接使用。"""
    persistent = await _has_table(session, "agent_user_memories")
    memory = await get_user_memory(session, user_id)
    if memory is None:
        memory = AgentUserMemory(
            user_id=user_id,
            preferences_json={},
            profile_summary=None,
        )
        if persistent:
            session.add(memory)
            await session.flush()

    records = {} if replace else dict(memory.preferences_json or {})
    for field_name, value in preferences.items():
        if field_name not in FILTER_FIELDS or field_name in {
            "hard_filters", "soft_preferences",
        }:
            continue
        if not _is_present(value):
            records.pop(field_name, None)
            continue
        previous = records.get(field_name)
        evidence_count = (
            int(previous.get("evidence_count", 0) or 0) + 1
            if isinstance(previous, dict) and previous.get("value") == value
            else 1
        )
        records[field_name] = {
            "value": value,
            "confidence": 1.0,
            "evidence_count": evidence_count,
            "source": "user_saved",
        }

    memory.preferences_json = records
    visible = memory_to_filters(records)
    memory.profile_summary = build_rolling_summary("long_term", visible, {})
    if persistent:
        await session.commit()
        await session.refresh(memory)
    else:
        # 旧库未部署长期记忆表时只在本次请求内返回确认结果。
        memory.updated_at = datetime.now(timezone.utc)
    return memory


async def clear_user_memory(session: AsyncSession, user_id: int) -> None:
    """清空跨会话长期偏好，不删除任何会话或消息。"""
    memory = await get_user_memory(session, user_id)
    if memory is not None:
        await session.delete(memory)
        await session.commit()


async def _has_table(session: AsyncSession, table_name: str) -> bool:
    """只读检测可选表，供未迁移旧库安全降级。"""
    connection = await session.connection()
    return bool(await connection.run_sync(
        lambda sync_connection: inspect(sync_connection).has_table(table_name)
    ))


def resolve_references(message: str, reference_map: dict[str, Any] | None) -> ReferenceResolution:
    """解析「第二套、最便宜的、刚才那个」等跨轮指代。"""
    reference_map = reference_map or {}
    ordinal_map = reference_map.get("ordinal_refs") or {}
    semantic_map = reference_map.get("semantic_refs") or {}
    result = ReferenceResolution()

    for match in re.finditer(r"第\s*(\d+|[一二两三四五六七八九十])\s*[个套间]", message):
        token = match.group(1)
        rank = int(token) if token.isdigit() else _CN_NUM.get(token, 0)
        property_id = ordinal_map.get(str(rank))
        label = f"第{rank}套"
        if isinstance(property_id, int):
            result.resolved_ids.append(property_id)
            result.labels.append(label)
        else:
            result.unresolved.append(label)

    semantic_patterns = {
        "cheapest": r"(最便宜|价格最低|最低价)",
        "closest": r"(最近的|通勤最近|离学校最近|距离最近)",
        "largest": r"(最大的|面积最大|空间最大)",
        "best_overall": r"(最好那套|综合最好|最推荐|第一名)",
        "last_focus": (
            r"(刚才那套|刚刚那个|上一个|那一套|"
            r"你(?:刚才)?推荐的(?:这个|这套|那套)|"
            r"(?:这个|这套|那套)(?:房|房子|房源|公寓)?|"
            r"(?:它|他)(?=有|带|包含|附近|周边|离))"
        ),
    }
    for key, pattern in semantic_patterns.items():
        if not re.search(pattern, message):
            continue
        property_id = semantic_map.get(key)
        if not isinstance(property_id, int) and key == "last_focus":
            property_id = reference_map.get("last_focus_id")
        label = key
        if isinstance(property_id, int):
            result.resolved_ids.append(property_id)
            result.labels.append(label)
        else:
            result.unresolved.append(label)

    result.resolved_ids = list(dict.fromkeys(result.resolved_ids))
    result.labels = list(dict.fromkeys(result.labels))
    result.unresolved = list(dict.fromkeys(result.unresolved))
    return result


def build_reference_map(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """基于本轮重排结果生成序号与语义指代映射。"""
    if not candidates:
        return {}
    normalized: list[dict[str, Any]] = []
    for item in candidates:
        unit_type = item.get("unit_type")
        if unit_type is None:
            continue
        property_id = item.get("_property_id")
        if not isinstance(property_id, int):
            property_id = int(unit_type.id)
        normalized.append({
            "id": property_id,
            "price": float(unit_type.base_rent),
            "area": float(unit_type.area_sqm) if unit_type.area_sqm is not None else None,
            "commute": item.get("_commute_minutes"),
            "score": float(item.get("_final_score", 0.0)),
        })
    if not normalized:
        return {}

    valid_commute = [x for x in normalized if isinstance(x.get("commute"), (int, float))]
    valid_area = [x for x in normalized if isinstance(x.get("area"), (int, float))]
    semantic_refs = {
        "cheapest": min(normalized, key=lambda x: x["price"])["id"],
        "best_overall": max(normalized, key=lambda x: x["score"])["id"],
        "last_focus": normalized[0]["id"],
    }
    if valid_commute:
        semantic_refs["closest"] = min(valid_commute, key=lambda x: x["commute"])["id"]
    if valid_area:
        semantic_refs["largest"] = max(valid_area, key=lambda x: x["area"])["id"]
    return {
        "ordinal_refs": {str(i): item["id"] for i, item in enumerate(normalized, 1)},
        "semantic_refs": semantic_refs,
        "last_focus_id": normalized[0]["id"],
    }


def build_state_summary(stage: str, filters: dict[str, Any]) -> dict[str, Any]:
    """构建前端可展示的当前需求摘要与 chips。"""
    label_map = {
        "institution": "学校", "district": "区域", "price_max": "预算≤",
        "price_min": "预算≥", "bedrooms": "卧室", "property_type": "类型",
        "room_type": "房型", "bathrooms": "卫浴", "amenities": "设施",
        "commute_minutes": "通勤≤", "available_from": "入住",
        "min_lease_months": "租期≥", "max_lease_months": "租期≤",
    }
    currency = str(filters.get("currency") or "").upper()
    currency_symbol = {
        "CNY": "¥", "GBP": "£", "SGD": "S$", "USD": "$", "HKD": "HK$",
    }.get(currency, f"{currency} " if currency else "")
    chips: list[dict[str, str]] = []
    for key in (
        "institution", "district", "price_max", "price_min", "bedrooms",
        "property_type", "room_type", "bathrooms", "amenities",
        "commute_minutes", "available_from", "min_lease_months",
        "max_lease_months",
    ):
        value = filters.get(key)
        if not _is_present(value):
            continue
        if isinstance(value, list):
            value_text = "、".join(str(v) for v in value[:4])
        elif key in {"price_max", "price_min"}:
            value_text = f"{currency_symbol}{int(float(value))}"
        elif key == "commute_minutes":
            value_text = f"{value}分钟"
        elif key in {"min_lease_months", "max_lease_months"}:
            value_text = f"{value}个月"
        elif key in {"bedrooms", "bathrooms"}:
            value_text = f"{value}"
        else:
            value_text = str(value)
        chips.append({"key": key, "label": f"{label_map.get(key, key)}{value_text}"})
    return {"stage": stage, "filters": filters, "chips": chips}


def build_rolling_summary(stage: str, filters: dict[str, Any], last_search: dict[str, Any]) -> str:
    """用确定性事实压缩旧对话，不让 LLM 自己总结出不存在的偏好。"""
    summary = build_state_summary(stage, filters)
    chip_text = "、".join(c["label"] for c in summary["chips"]) or "尚未确认筛选条件"
    count = int(last_search.get("candidate_count", 0) or 0)
    top_ids = last_search.get("top_ids") or []
    top_text = f"；上轮候选 {count} 套，前三编号 {top_ids[:3]}" if count or top_ids else ""
    return f"当前阶段：{stage}；已确认需求：{chip_text}{top_text}。"


class AgentMemoryService:
    """数据库侧 Agent Memory 门面。"""

    def __init__(
        self,
        session: AsyncSession,
        chat_session: ChatSession,
        user_id: int,
        *,
        long_term_enabled: bool = True,
    ) -> None:
        self.session = session
        self.chat_session = chat_session
        self.user_id = user_id
        self.long_term_enabled = long_term_enabled
        self._persistent_available: bool | None = None

    async def _supports_persistence(self) -> bool:
        """判断 Agent 新表是否齐全；结果在单次请求内缓存。"""
        if self._persistent_available is None:
            required = (
                "agent_session_states",
                "agent_user_memories",
                "agent_search_runs",
                "agent_search_candidates",
            )
            self._persistent_available = all(
                [await _has_table(self.session, table_name) for table_name in required]
            )
        return self._persistent_available

    async def load(self, message: str) -> RuntimeMemory:
        persistent = await self._supports_persistence()
        state = None
        if persistent:
            state = await self.session.scalar(
                select(AgentSessionState).where(
                    AgentSessionState.session_id == self.chat_session.id
                )
            )
        if state is None:
            accumulated = dict(self.chat_session.accumulated_filters or {})
            legacy_state = accumulated.pop(LEGACY_STATE_KEY, {})
            if not isinstance(legacy_state, dict):
                legacy_state = {}
            state = AgentSessionState(
                session_id=self.chat_session.id,
                user_id=self.user_id,
                stage=str(legacy_state.get("stage") or "explore"),
                filters_json=accumulated,
                reference_map_json=dict(legacy_state.get("reference_map") or {}),
                last_search_json=dict(legacy_state.get("last_search") or {}),
                rolling_summary=legacy_state.get("rolling_summary"),
                context_version=int(legacy_state.get("context_version") or 1),
            )
            if persistent:
                self.session.add(state)
                await self.session.flush()

        user_memory = None
        if self.long_term_enabled and persistent:
            user_memory = await self.session.scalar(
                select(AgentUserMemory).where(AgentUserMemory.user_id == self.user_id)
            )
        if user_memory is None:
            user_memory = AgentUserMemory(
                user_id=self.user_id,
                preferences_json={},
                profile_summary=None,
            )
            if self.long_term_enabled and persistent:
                self.session.add(user_memory)
                await self.session.flush()

        return RuntimeMemory(
            state=state,
            user_memory=user_memory,
            memory_filters=(
                memory_to_filters(user_memory.preferences_json)
                if self.long_term_enabled and persistent else {}
            ),
            reference_resolution=resolve_references(message, state.reference_map_json),
        )

    def merge_filters(
        self,
        runtime: RuntimeMemory,
        *,
        message: str,
        extracted: dict[str, Any] | None,
        request_filters: dict[str, Any] | None,
        context_filters: dict[str, Any] | None = None,
        remove_fields: list[str] | None = None,
        remove_values: dict[str, list[Any]] | None = None,
    ) -> dict[str, Any]:
        previous = {
            **(runtime.state.filters_json or {}),
            **(context_filters or {}),
        }
        return merge_dialogue_filters(
            message=message,
            previous=previous,
            memory_filters=runtime.memory_filters,
            extracted=extracted,
            request_filters=request_filters,
            remove_fields=remove_fields,
            remove_values=remove_values,
        )

    async def sync_legacy_state(self, runtime: RuntimeMemory) -> None:
        """把旧库短期状态写回 chat_sessions.accumulated_filters。"""
        if await self._supports_persistence():
            return
        payload = dict(runtime.state.filters_json or {})
        payload[LEGACY_STATE_KEY] = {
            "stage": runtime.state.stage,
            "reference_map": dict(runtime.state.reference_map_json or {}),
            "last_search": dict(runtime.state.last_search_json or {}),
            "rolling_summary": runtime.state.rolling_summary,
            "context_version": int(runtime.state.context_version or 1),
        }
        self.chat_session.accumulated_filters = payload
        flag_modified(self.chat_session, "accumulated_filters")

    def _update_long_term_memory(
        self,
        memory: AgentUserMemory,
        explicit_filters: dict[str, Any],
        session_id: int,
        *,
        remove_fields: list[str] | None = None,
        remove_values: dict[str, list[Any]] | None = None,
        reset_all: bool = False,
    ) -> None:
        preferences = {} if reset_all else dict(memory.preferences_json or {})
        for field_name in remove_fields or []:
            if field_name in FILTER_FIELDS:
                preferences.pop(field_name, None)
        for field_name, values in (remove_values or {}).items():
            record = preferences.get(field_name)
            if not isinstance(record, dict) or not isinstance(record.get("value"), list):
                continue
            remove_markers = {
                json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
                for value in values
            }
            kept = [
                value for value in record["value"]
                if json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
                not in remove_markers
            ]
            if kept:
                preferences[field_name] = {**record, "value": kept}
            else:
                preferences.pop(field_name, None)

        for field_name, value in explicit_filters.items():
            if field_name not in FILTER_FIELDS or field_name in {"hard_filters", "soft_preferences"}:
                continue
            if not _is_present(value):
                continue
            previous = preferences.get(field_name)
            same_value = isinstance(previous, dict) and previous.get("value") == value
            same_session = same_value and int(previous.get("last_session_id", 0) or 0) == session_id
            if same_value:
                evidence_count = int(previous.get("evidence_count", 0) or 0)
                if not same_session:
                    evidence_count += 1
            else:
                evidence_count = 1
            if field_name in STABLE_MEMORY_FIELDS:
                confidence = min(1.0, 0.78 + (evidence_count - 1) * 0.08)
            else:
                confidence = min(0.95, 0.55 + (evidence_count - 1) * 0.15)
            preferences[field_name] = {
                "value": value,
                "confidence": round(confidence, 2),
                "evidence_count": evidence_count,
                "source": "explicit_search_filter",
                "last_session_id": session_id,
            }
        memory.preferences_json = preferences
        stable = memory_to_filters(preferences)
        memory.profile_summary = build_rolling_summary("long_term", stable, {})

    async def save_search(
        self,
        runtime: RuntimeMemory,
        *,
        stage: str,
        effective_filters: dict[str, Any],
        explicit_filters: dict[str, Any],
        candidates: list[dict[str, Any]],
        original_query: str,
        rewritten_query: str | None,
        relaxation_trace: list[dict[str, Any]],
        source_manifest: dict[str, Any],
        latency_ms: int,
        remove_fields: list[str] | None = None,
        remove_values: dict[str, list[Any]] | None = None,
        reset_memory: bool = False,
    ) -> AgentSearchRun:
        """原子更新短期/长期记忆，并记录可复现的搜索 run。"""
        reference_map = build_reference_map(candidates)
        top_ids = [
            int(item.get("_property_id", item["unit_type"].id))
            for item in candidates[:3] if item.get("unit_type") is not None
        ]
        last_search = {
            "candidate_count": len(candidates),
            "candidate_ids": [
                int(item.get("_property_id", item["unit_type"].id))
                for item in candidates if item.get("unit_type") is not None
            ],
            "top_ids": top_ids,
            "relaxation_trace": relaxation_trace,
        }

        runtime.state.stage = stage
        runtime.state.filters_json = dict(effective_filters)
        runtime.state.reference_map_json = reference_map
        runtime.state.last_search_json = last_search
        runtime.state.context_version = int(runtime.state.context_version or 0) + 1
        runtime.state.rolling_summary = build_rolling_summary(stage, effective_filters, last_search)
        persistent = await self._supports_persistence()
        legacy_payload = dict(effective_filters)
        legacy_payload[LEGACY_STATE_KEY] = {
            "stage": stage,
            "reference_map": reference_map,
            "last_search": last_search,
            "rolling_summary": runtime.state.rolling_summary,
            "context_version": runtime.state.context_version,
        }
        self.chat_session.accumulated_filters = legacy_payload
        if not persistent:
            flag_modified(self.chat_session, "accumulated_filters")
        if self.long_term_enabled and persistent:
            self._update_long_term_memory(
                runtime.user_memory,
                explicit_filters,
                self.chat_session.id,
                remove_fields=remove_fields,
                remove_values=remove_values,
                reset_all=reset_memory,
            )

        run = AgentSearchRun(
            session_id=self.chat_session.id,
            user_id=self.user_id,
            original_query=original_query,
            rewritten_query=rewritten_query,
            effective_filters_json=dict(effective_filters),
            relaxation_trace_json=relaxation_trace,
            source_manifest_json=source_manifest,
            candidate_count=len(candidates),
            selected_count=min(5 if stage in {"compare", "decide"} else 3, len(candidates)),
            latency_ms=max(0, int(latency_ms)),
        )
        if not persistent:
            # 旧库仍可完成搜索与多轮会话，只跳过新表中的检索审计记录。
            return run
        self.session.add(run)
        await self.session.flush()

        for rank, item in enumerate(candidates, 1):
            unit_type = item.get("unit_type")
            if unit_type is None:
                continue
            self.session.add(AgentSearchCandidate(
                search_run_id=run.id,
                unit_type_id=(
                    int(item["_unit_type_id"])
                    if isinstance(item.get("_unit_type_id"), int) else None
                ),
                property_id=(
                    int(item["_property_id"])
                    if isinstance(item.get("_property_id"), int) else None
                ),
                rank=rank,
                final_score=float(item.get("_final_score", 0.0)),
                score_breakdown_json=dict(item.get("_score_breakdown") or {}),
                source_metadata_json=dict(item.get("_source_metadata") or {}),
            ))
        return run
