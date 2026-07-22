"""租房偏好状态服务 —— 确定性维护硬约束、软偏好及多轮增删改操作。"""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any


STATE_VERSION = 1

SCALAR_FIELDS = frozenset({
    "country",
    "district",
    "price_min",
    "price_max",
    "bedrooms",
    "property_type",
    "room_type",
    "bathrooms",
    "area_min",
    "area_max",
    "min_lease_months",
    "max_lease_months",
    "available_from",
    "institution",
    "distance_km",
    "commute_mode",
    "commute_minutes",
})
LIST_FIELDS = frozenset({"amenities", "poi_requirements"})
ALLOWED_FIELDS = SCALAR_FIELDS | LIST_FIELDS

_FIELD_GROUPS: dict[str, set[str]] = {
    "price": {"price_min", "price_max"},
    "area": {"area_min", "area_max"},
    "commute": {"commute_mode", "commute_minutes"},
}

_POI_TYPE_ALIASES = {
    "超市": "supermarket",
    "便利店": "supermarket",
    "supermarket": "supermarket",
    "健身房": "gym",
    "健身": "gym",
    "gym": "gym",
    "医院": "medical",
    "诊所": "medical",
    "药店": "medical",
    "医疗": "medical",
    "medical": "medical",
    "地铁": "transit",
    "地铁站": "transit",
    "公交": "transit",
    "公交站": "transit",
    "交通": "transit",
    "transit": "transit",
}


@dataclass(frozen=True)
class PreferenceViews:
    """搜索使用的三种视图：全部条件、硬筛选值、软偏好条目。"""

    all_values: dict[str, Any]
    hard_values: dict[str, Any]
    soft_constraints: list[dict[str, Any]]
    constraints: list[dict[str, Any]]


def empty_preference_state() -> dict[str, Any]:
    """创建空偏好状态。"""
    return {"version": STATE_VERSION, "filters": {}, "constraints": []}


def _expanded_markers(markers: Any) -> set[str]:
    expanded: set[str] = set()
    if not isinstance(markers, list):
        return expanded
    for marker in markers:
        if not isinstance(marker, str):
            continue
        expanded.add(marker)
        expanded.update(_FIELD_GROUPS.get(marker, set()))
    return expanded


def _normalize_strength(value: Any, default: str = "hard") -> str:
    return value if value in {"hard", "soft"} else default


def _normalize_weight(value: Any, strength: str) -> float:
    default = 1.0 if strength == "hard" else 0.6
    try:
        return round(max(0.0, min(1.0, float(value))), 2)
    except (TypeError, ValueError):
        return default


def canonical_poi_type(value: Any) -> str | None:
    """把中英文 POI 类型统一成内部分类。"""
    if value is None:
        return None
    text = str(value).strip().lower()
    return _POI_TYPE_ALIASES.get(text, text or None)


def _normalize_poi_requirement(value: Any) -> dict[str, Any] | None:
    if isinstance(value, str):
        value = {"type": value}
    if not isinstance(value, dict):
        return None

    poi_type = canonical_poi_type(value.get("type") or value.get("category"))
    if not poi_type:
        return None

    normalized: dict[str, Any] = {"type": poi_type}
    target = value.get("target_m", value.get("max_distance_m"))
    acceptable = value.get("acceptable_m")
    try:
        if target is not None:
            normalized["target_m"] = max(0, int(float(target)))
    except (TypeError, ValueError):
        pass
    try:
        if acceptable is not None:
            normalized["acceptable_m"] = max(0, int(float(acceptable)))
    except (TypeError, ValueError):
        pass

    if "target_m" in normalized and "acceptable_m" not in normalized:
        normalized["acceptable_m"] = max(normalized["target_m"], normalized["target_m"] * 2)
    if (
        "target_m" in normalized
        and "acceptable_m" in normalized
        and normalized["acceptable_m"] < normalized["target_m"]
    ):
        normalized["acceptable_m"] = normalized["target_m"]
    return normalized


def _normalize_scalar(field: str, value: Any) -> Any:
    if value is None:
        return None
    if field in {"price_min", "price_max", "area_min", "area_max", "distance_km"}:
        try:
            number = float(value)
            return number if number >= 0 else None
        except (TypeError, ValueError):
            return None
    if field in {"bedrooms", "bathrooms", "min_lease_months", "max_lease_months", "commute_minutes"}:
        try:
            number = int(value)
            minimum = 1 if field in {"min_lease_months", "max_lease_months", "commute_minutes"} else 0
            return number if number >= minimum else None
        except (TypeError, ValueError):
            return None
    if field == "commute_mode":
        text = str(value).strip().lower()
        return text if text in {"walking", "bicycling", "driving", "transit"} else None
    if field == "property_type":
        text = str(value).strip().lower()
        return text if text in {"apartment", "house", "studio", "shared"} else None
    text = str(value).strip()
    return text or None


def _normalize_list(field: str, value: Any) -> list[Any]:
    values = value if isinstance(value, list) else [value]
    normalized: list[Any] = []
    for item in values:
        if field == "amenities":
            item = str(item).strip() if item is not None else ""
            if not item:
                continue
        else:
            item = _normalize_poi_requirement(item)
            if item is None:
                continue
        key = _item_key(field, item)
        if all(_item_key(field, existing) != key for existing in normalized):
            normalized.append(item)
    return normalized


def _item_key(field: str, value: Any) -> str:
    if field == "amenities":
        return str(value).strip().casefold()
    if field == "poi_requirements":
        if isinstance(value, dict):
            return canonical_poi_type(value.get("type") or value.get("category")) or ""
        return canonical_poi_type(value) or ""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _constraint_id(field: str, value: Any = None) -> str:
    if field in LIST_FIELDS:
        return f"{field}:{_item_key(field, value)}"
    return field


def _make_constraint(
    field: str,
    value: Any,
    strength: str,
    weight: Any = None,
) -> dict[str, Any]:
    normalized_strength = _normalize_strength(strength)
    return {
        "id": _constraint_id(field, value),
        "field": field,
        "value": deepcopy(value),
        "strength": normalized_strength,
        "weight": _normalize_weight(weight, normalized_strength),
    }


def _infer_constraints(filters: dict[str, Any], raw: dict[str, Any]) -> list[dict[str, Any]]:
    hard_markers = _expanded_markers(raw.get("hard_filters"))
    soft_markers = _expanded_markers(raw.get("soft_preferences"))
    constraints: list[dict[str, Any]] = []
    for field, value in filters.items():
        default_strength = "soft" if field == "poi_requirements" else "hard"
        strength = "hard" if field in hard_markers else "soft" if field in soft_markers else default_strength
        if field in LIST_FIELDS:
            for item in value:
                constraints.append(_make_constraint(field, item, strength))
        else:
            constraints.append(_make_constraint(field, value, strength))
    return constraints


def normalize_preference_state(raw: dict[str, Any] | None) -> dict[str, Any]:
    """兼容结构化状态、扁平 payload 和历史 flat accumulated_filters。"""
    if not isinstance(raw, dict):
        return empty_preference_state()

    source_filters = raw.get("filters") if isinstance(raw.get("filters"), dict) else raw
    filters: dict[str, Any] = {}
    for field in ALLOWED_FIELDS:
        if field not in source_filters or source_filters[field] is None:
            continue
        if field in LIST_FIELDS:
            value = _normalize_list(field, source_filters[field])
            if value:
                filters[field] = value
        else:
            value = _normalize_scalar(field, source_filters[field])
            if value is not None:
                filters[field] = value

    raw_constraints = raw.get("constraints") or raw.get("preference_constraints")
    constraints: list[dict[str, Any]] = []
    if isinstance(raw_constraints, list):
        for item in raw_constraints:
            if not isinstance(item, dict):
                continue
            field = item.get("field")
            if field not in filters:
                continue
            strength = _normalize_strength(item.get("strength"))
            if field in LIST_FIELDS:
                value = item.get("value")
                key = _item_key(field, value)
                actual = next((v for v in filters[field] if _item_key(field, v) == key), None)
                if actual is None:
                    continue
                constraints.append(_make_constraint(field, actual, strength, item.get("weight")))
            else:
                constraints.append(_make_constraint(field, filters[field], strength, item.get("weight")))

    if not constraints:
        constraints = _infer_constraints(filters, raw)

    # 补齐没有元数据的值，避免历史脏数据在 flatten 时丢失。
    constraint_ids = {item["id"] for item in constraints}
    for field, value in filters.items():
        values = value if field in LIST_FIELDS else [value]
        for entry in values:
            cid = _constraint_id(field, entry)
            if cid not in constraint_ids:
                constraints.append(_make_constraint(field, entry, "hard"))
                constraint_ids.add(cid)

    return {"version": STATE_VERSION, "filters": filters, "constraints": constraints}


def _remove_field(state: dict[str, Any], field: str) -> None:
    state["filters"].pop(field, None)
    state["constraints"] = [c for c in state["constraints"] if c.get("field") != field]


def _upsert_constraint(state: dict[str, Any], constraint: dict[str, Any]) -> None:
    state["constraints"] = [c for c in state["constraints"] if c.get("id") != constraint["id"]]
    state["constraints"].append(constraint)


def apply_preference_operations(
    previous_state: dict[str, Any] | None,
    operations: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """按顺序确定性应用 set/update/add/remove/clear 操作。"""
    state = normalize_preference_state(previous_state)
    for operation in operations or []:
        if not isinstance(operation, dict):
            continue
        op = str(operation.get("op") or "").strip().lower()
        field = operation.get("field")

        if op == "clear" and field is None:
            state = empty_preference_state()
            continue
        if field not in ALLOWED_FIELDS or op not in {"set", "update", "add", "remove", "clear"}:
            continue
        if op == "clear":
            _remove_field(state, field)
            continue

        raw_value = operation.get("value")
        strength = _normalize_strength(operation.get("strength"), "hard")
        weight = operation.get("weight")

        if field in SCALAR_FIELDS:
            if op == "remove" or raw_value is None:
                _remove_field(state, field)
                continue
            value = _normalize_scalar(field, raw_value)
            if value is None:
                continue
            state["filters"][field] = value
            _upsert_constraint(state, _make_constraint(field, value, strength, weight))
            continue

        # list 字段
        if op in {"set"}:
            _remove_field(state, field)
            values = _normalize_list(field, raw_value)
            if values:
                state["filters"][field] = values
                for value in values:
                    _upsert_constraint(state, _make_constraint(field, value, strength, weight))
            continue

        if op == "remove":
            if raw_value is None:
                _remove_field(state, field)
                continue
            remove_values = _normalize_list(field, raw_value)
            remove_keys = {_item_key(field, value) for value in remove_values}
            current = [
                value for value in state["filters"].get(field, [])
                if _item_key(field, value) not in remove_keys
            ]
            if current:
                state["filters"][field] = current
            else:
                state["filters"].pop(field, None)
            state["constraints"] = [
                c for c in state["constraints"]
                if not (c.get("field") == field and _item_key(field, c.get("value")) in remove_keys)
            ]
            continue

        # add/update：按 item key 幂等追加；POI update 会替换同类型距离。
        values = _normalize_list(field, raw_value)
        current = list(state["filters"].get(field, []))
        for value in values:
            key = _item_key(field, value)
            current = [item for item in current if _item_key(field, item) != key]
            current.append(value)
            _upsert_constraint(state, _make_constraint(field, value, strength, weight))
        if current:
            state["filters"][field] = current

    return normalize_preference_state(state)


def apply_explicit_filters(
    state: dict[str, Any] | None,
    explicit_filters: dict[str, Any] | None,
) -> dict[str, Any]:
    """把前端 Filter Bar 的显式值作为硬约束覆盖到会话状态。"""
    operations = [
        {"op": "set", "field": field, "value": value, "strength": "hard", "weight": 1.0}
        for field, value in (explicit_filters or {}).items()
        if field in ALLOWED_FIELDS and value is not None and value != [] and value != ""
    ]
    return apply_preference_operations(state, operations)


def flatten_preference_state(state: dict[str, Any] | None) -> dict[str, Any]:
    """生成给搜索服务使用且兼容旧字段的扁平 payload。"""
    normalized = normalize_preference_state(state)
    hard_fields: list[str] = []
    soft_fields: list[str] = []
    for constraint in normalized["constraints"]:
        target = hard_fields if constraint["strength"] == "hard" else soft_fields
        field = constraint["field"]
        if field not in target:
            target.append(field)
    return {
        **deepcopy(normalized["filters"]),
        "hard_filters": hard_fields,
        "soft_preferences": soft_fields,
        "preference_constraints": deepcopy(normalized["constraints"]),
        "preference_version": STATE_VERSION,
    }


def build_preference_views(
    payload: dict[str, Any] | None,
    explicit_filters: dict[str, Any] | None = None,
) -> PreferenceViews:
    """把提取结果拆成硬筛选和软评分视图；显式前端筛选始终为硬约束。"""
    state = apply_explicit_filters(normalize_preference_state(payload), explicit_filters)
    hard_values: dict[str, Any] = {}
    soft_constraints: list[dict[str, Any]] = []
    for constraint in state["constraints"]:
        field = constraint["field"]
        if constraint["strength"] == "soft":
            soft_constraints.append(deepcopy(constraint))
            continue
        if field in LIST_FIELDS:
            hard_values.setdefault(field, []).append(deepcopy(constraint["value"]))
        else:
            hard_values[field] = deepcopy(constraint["value"])
    return PreferenceViews(
        all_values=deepcopy(state["filters"]),
        hard_values=hard_values,
        soft_constraints=soft_constraints,
        constraints=deepcopy(state["constraints"]),
    )
