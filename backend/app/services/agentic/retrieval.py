"""混合检索与重排 —— 结构化约束、语义、词面、地理和业务质量融合。"""
from __future__ import annotations

import math
import re
from copy import deepcopy
from datetime import date
from typing import Any


FILTER_LABELS: dict[str, str] = {
    "country": "国家",
    "currency": "币种",
    "district": "区域",
    "price_min": "最低预算",
    "price_max": "预算上限",
    "bedrooms": "卧室数",
    "property_type": "房源类型",
    "room_type": "房型",
    "bathrooms": "卫浴数",
    "area_min": "最小面积",
    "area_max": "最大面积",
    "amenities": "设施要求",
    "min_lease_months": "租期",
    "max_lease_months": "最长租期",
    "available_from": "入住时间",
    "commute_minutes": "通勤时长",
    "poi_requirements": "周边设施距离",
}

_CITY_ALIASES: dict[str, tuple[str, ...]] = {
    "新加坡": ("新加坡", "singapore", "sg"),
    "伦敦": ("伦敦", "london"),
    "香港": ("香港", "hong kong", "hk"),
    "洛杉矶": ("洛杉矶", "los angeles", "la"),
    "旧金山": ("旧金山", "san francisco", "sf"),
    "苏州": ("苏州", "suzhou"),
}


def _text(value: Any) -> str:
    return str(value or "").strip().lower()


def _combined_location(item: dict[str, Any]) -> str:
    inst = item["institute"]
    return " ".join(_text(v) for v in (
        inst.district, inst.city, inst.country, inst.address, inst.name, inst.name_cn
    ))


def _location_matches(value: str, item: dict[str, Any]) -> bool:
    needle = _text(value)
    haystack = _combined_location(item)
    if not needle:
        return True
    aliases = _CITY_ALIASES.get(value, (needle,))
    return any(_text(alias) in haystack for alias in aliases)


# 中文→英文 amenity 反向映射，用于松弛匹配
_AMENITY_ALIASES_REVERSE: dict[str, tuple[str, ...]] = {
    "健身房": ("gym", "健身房"),
    "泳池": ("pool", "swimming pool", "泳池"),
    "空调": ("air conditioning", "ac", "空调"),
    "独立卫浴": ("ensuite", "private bathroom", "独立卫浴"),
    "WiFi": ("wifi", "WiFi"),
    "自习室": ("study room", "自习室"),
    "洗衣机": ("laundry", "washing machine", "洗衣机"),
    "阳台": ("balcony", "阳台"),
    "电梯": ("elevator", "电梯"),
    "停车位": ("parking", "停车位"),
    "门禁": ("security", "24h security", "门禁"),
    "快递代收": ("parcel", "package", "快递代收"),
    "家具齐全": ("furnished", "家具齐全"),
    "宠物友好": ("pet friendly", "宠物友好"),
    "独立厨房": ("private kitchen", "独立厨房"),
    "冰箱": ("fridge", "冰箱"),
    "微波炉": ("microwave", "微波炉"),
}


def _expand_amenity(value: str) -> set[str]:
    """将 amenity 筛选值展开为中英文同义词集合，用于松弛匹配。"""
    v = _text(value)
    aliases = _AMENITY_ALIASES_REVERSE.get(v, (v,))
    return {_text(a) for a in aliases}


def _candidate_amenities(item: dict[str, Any]) -> set[str]:
    unit_type = item["unit_type"]
    institute = item["institute"]
    values = [*(unit_type.amenities or []), *(institute.amenities or [])]
    return {_text(v) for v in values if _text(v)}


def _room_type_matches(requested: str, item: dict[str, Any]) -> bool:
    unit_type = item["unit_type"]
    requested = _text(requested).replace("_", "-")
    legacy_type = _text(item.get("_legacy_property_type")).replace("_", "-")
    if legacy_type and requested == legacy_type:
        return True
    name = _text(unit_type.name)
    bedrooms = int(unit_type.bedrooms or 0)
    if requested in {"studio", "单间", "开间"}:
        return bedrooms == 0 or any(x in name for x in ("studio", "单间", "开间"))
    if requested in {"ensuite", "独卫"}:
        return (
            "ensuite" in name
            or "独卫" in name
            or "独立卫浴".lower() in _candidate_amenities(item)
        )
    if requested in {"1bed", "1-bed", "one-bed"}:
        return bedrooms == 1
    if requested in {"2bed", "2-bed", "two-bed"}:
        return bedrooms == 2
    if requested in {"3bed+", "3-bed+", "three-bed-plus"}:
        return bedrooms >= 3
    if requested in {"shared", "合租"}:
        return any(x in name for x in ("shared", "合租", "bedspace", "床位"))
    if requested == "house":
        return any(x in name for x in ("house", "别墅", "整租"))
    return requested in name


def candidate_matches_filters(
    item: dict[str, Any],
    filters: dict[str, Any],
    *,
    ignore_fields: set[str] | None = None,
) -> bool:
    """在召回池上执行完整结构化约束，供严格检索与消融复用。"""
    ignored = ignore_fields or set()
    unit_type = item["unit_type"]
    institute = item["institute"]

    if "district" not in ignored and filters.get("district"):
        if not _location_matches(str(filters["district"]), item):
            return False
    if "country" not in ignored and filters.get("country"):
        if not _location_matches(str(filters["country"]), item):
            return False
    if "currency" not in ignored and filters.get("currency"):
        if _text(unit_type.currency) != _text(filters["currency"]):
            return False
    price = float(unit_type.base_rent)
    if "price_min" not in ignored and filters.get("price_min") is not None:
        if price < float(filters["price_min"]):
            return False
    if "price_max" not in ignored and filters.get("price_max") is not None:
        if price > float(filters["price_max"]):
            return False
    if "bedrooms" not in ignored and filters.get("bedrooms") is not None:
        if int(unit_type.bedrooms or 0) != int(filters["bedrooms"]):
            return False
    for key in ("property_type", "room_type"):
        if key not in ignored and filters.get(key):
            if not _room_type_matches(str(filters[key]), item):
                return False
    if "bathrooms" not in ignored and filters.get("bathrooms") is not None:
        if int(unit_type.bathrooms or 0) < int(filters["bathrooms"]):
            return False
    if "area_min" not in ignored and filters.get("area_min") is not None:
        if unit_type.area_sqm is None or float(unit_type.area_sqm) < float(filters["area_min"]):
            return False
    if "area_max" not in ignored and filters.get("area_max") is not None:
        if unit_type.area_sqm is None or float(unit_type.area_sqm) > float(filters["area_max"]):
            return False
    if "amenities" not in ignored and filters.get("amenities"):
        available = _candidate_amenities(item)
        # 用同义词集合松弛匹配，保证中文筛选词能命中英文数据
        if any(
            not (_expand_amenity(required) & available)
            for required in filters["amenities"]
        ):
            return False
    if "min_lease_months" not in ignored and filters.get("min_lease_months") is not None:
        # 用户可接受的租期必须不短于房源要求的最短租期。
        if int(unit_type.min_stay_months or 0) > int(filters["min_lease_months"]):
            return False
    if "max_lease_months" not in ignored and filters.get("max_lease_months") is not None:
        if int(unit_type.min_stay_months or 0) > int(filters["max_lease_months"]):
            return False
    if "available_from" not in ignored and filters.get("available_from"):
        available_from = unit_type.available_from
        if available_from is None:
            return False
        requested = str(filters["available_from"]).replace("-", "")[:8]
        candidate = available_from.strftime("%Y%m%d") if isinstance(available_from, date) else str(available_from).replace("-", "")
        if candidate > requested:
            return False
    if "female_only" not in ignored and filters.get("female_only") is not None:
        if bool(institute.female_only) != bool(filters["female_only"]):
            return False
    if "commute_minutes" not in ignored and filters.get("commute_minutes") is not None:
        commute = item.get("_commute_minutes")
        if not isinstance(commute, (int, float)):
            return False
        if commute > float(filters["commute_minutes"]):
            return False
    if "poi_requirements" not in ignored and filters.get("poi_requirements"):
        distances = item.get("_poi_distances") or {}
        for requirement in filters["poi_requirements"]:
            if not isinstance(requirement, dict) or requirement.get("max_distance_m") is None:
                continue
            poi_type = str(requirement.get("type") or "")
            distance = distances.get(poi_type)
            if not isinstance(distance, (int, float)):
                return False
            if distance > float(requirement["max_distance_m"]):
                return False
    return True


def _trial_relaxation(field_name: str, filters: dict[str, Any]) -> tuple[dict[str, Any], str]:
    trial = deepcopy(filters)
    if field_name == "price_max" and trial.get("price_max") is not None:
        before = float(trial["price_max"])
        trial["price_max"] = int(math.ceil(before * 1.2))
        return trial, f"预算上限由 {int(before)} 调到 {trial['price_max']}"
    if field_name == "price_min" and trial.get("price_min") is not None:
        before = float(trial["price_min"])
        trial["price_min"] = max(0, int(math.floor(before * 0.8)))
        return trial, f"最低预算由 {int(before)} 调到 {trial['price_min']}"
    trial.pop(field_name, None)
    return trial, f"暂不限制{FILTER_LABELS.get(field_name, field_name)}"


def apply_constraint_ablation(
    recall_pool: list[dict[str, Any]],
    filters: dict[str, Any],
    *,
    min_results: int = 3,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], int]:
    """逐个移除/放宽约束，找出导致零结果的条件并选择最小改动方案。"""
    strict = [item for item in recall_pool if candidate_matches_filters(item, filters)]
    if len(strict) >= min_results:
        return strict, dict(filters), [], 0

    hard_fields = set(filters.get("hard_filters") or [])
    policy_order = (
        "price_max", "price_min", "district", "property_type", "room_type", "bedrooms",
        "area_min", "area_max", "bathrooms", "amenities", "commute_minutes",
        "poi_requirements", "max_lease_months",
    )
    traces: list[dict[str, Any]] = []
    trials: list[tuple[int, int, str, dict[str, Any], list[dict[str, Any]]]] = []
    for policy_index, field_name in enumerate(policy_order):
        if field_name not in filters or field_name in hard_fields:
            continue
        trial_filters, explanation = _trial_relaxation(field_name, filters)
        matches = [
            item for item in recall_pool
            if candidate_matches_filters(item, trial_filters)
        ]
        trace = {
            "field": field_name,
            "label": FILTER_LABELS.get(field_name, field_name),
            "action": explanation,
            "before_count": len(strict),
            "after_count": len(matches),
            "applied": False,
            "suggested_filters": {
                key: value for key, value in trial_filters.items()
                if filters.get(key) != value or key not in filters
            },
        }
        if field_name not in trial_filters:
            trace["remove_fields"] = [field_name]
        traces.append(trace)
        if len(matches) > len(strict):
            trials.append((len(matches), policy_index, field_name, trial_filters, matches))

    if not trials:
        return strict, dict(filters), traces, 0

    enough = [trial for trial in trials if trial[0] >= min_results]
    if enough:
        # 能补足结果时选策略表中更温和的一项，避免为了多出几十套而过度放宽。
        enough.sort(key=lambda value: (value[1], -value[0]))
        best_count, _priority, best_field, best_filters, best_matches = enough[0]
    else:
        # 都补不够时才优先选择能恢复最多真实候选的一项。
        trials.sort(key=lambda value: (-value[0], value[1]))
        best_count, _priority, best_field, best_filters, best_matches = trials[0]
    # 严格结果为 1-2 套时保留真实严格结果，只给放宽建议；完全无结果才自动应用一次最小放宽。
    should_apply = len(strict) == 0 and best_count > 0
    if should_apply:
        for trace in traces:
            trace["applied"] = trace["field"] == best_field
        return best_matches, best_filters, traces, 1
    return strict, dict(filters), traces, 0


def build_relaxation_options(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把消融诊断转换为前端可点击的放宽建议。"""
    options: list[dict[str, Any]] = []
    for trace in sorted(traces, key=lambda value: value.get("after_count", 0), reverse=True):
        if int(trace.get("after_count", 0)) <= int(trace.get("before_count", 0)):
            continue
        patch = dict(trace.get("suggested_filters") or {})
        for field_name in trace.get("remove_fields") or []:
            patch[field_name] = None
        options.append({
            "label": f"{trace.get('action')}（约 {trace.get('after_count')} 套）",
            "message": str(trace.get("action") or "放宽条件"),
            "filter_patch": patch,
            "kind": "relax",
            "icon": "↗",
        })
    return options[:4]


def lexical_relevance(query: str, item: dict[str, Any]) -> float:
    """轻量 BM25 替代信号：关键词与中文二元组覆盖率，返回 0-1。"""
    unit_type = item["unit_type"]
    institute = item["institute"]
    haystack = " ".join(_text(value) for value in (
        unit_type.name, unit_type.description, institute.name, institute.name_cn,
        institute.district, institute.city, institute.description,
        " ".join(unit_type.amenities or []), " ".join(institute.amenities or []),
    ))
    query_text = _text(query)
    tokens = [token for token in re.split(r"[^\w\u4e00-\u9fff]+", query_text) if len(token) >= 2]
    cn_chars = "".join(re.findall(r"[\u4e00-\u9fff]", query_text))
    tokens.extend(cn_chars[index:index + 2] for index in range(max(0, len(cn_chars) - 1)))
    tokens = list(dict.fromkeys(token for token in tokens if token))
    if not tokens:
        return 0.5
    hit_weight = sum(min(3, haystack.count(token)) for token in tokens)
    return min(1.0, hit_weight / max(len(tokens) * 1.5, 1.0))


def _price_score(price: float, filters: dict[str, Any], pool_prices: list[float]) -> float:
    minimum = filters.get("price_min")
    maximum = filters.get("price_max")
    if maximum is not None:
        target = float(maximum) * 0.9
        spread = max(float(maximum) * 0.35, 1.0)
        return max(0.0, 1.0 - abs(price - target) / spread)
    if minimum is not None:
        target = float(minimum) * 1.1
        spread = max(float(minimum) * 0.4, 1.0)
        return max(0.0, 1.0 - abs(price - target) / spread)
    low, high = min(pool_prices), max(pool_prices)
    return 1.0 - ((price - low) / max(high - low, 1.0))


def _commute_score(item: dict[str, Any], filters: dict[str, Any]) -> float:
    commute = item.get("_commute_minutes")
    if not isinstance(commute, (int, float)):
        return 0.45
    target = filters.get("commute_minutes")
    if target is not None:
        return max(0.0, min(1.0, 1.0 - max(0.0, float(commute) - float(target)) / max(float(target), 1.0)))
    return max(0.0, 1.0 - float(commute) / 60.0)


def _quality_score(item: dict[str, Any]) -> float:
    unit_type = item["unit_type"]
    institute = item["institute"]
    checks = [
        bool(unit_type.name), bool(unit_type.base_rent), unit_type.area_sqm is not None,
        bool(unit_type.description or institute.description), bool(unit_type.image_urls),
        bool(institute.address), int(item.get("available_rooms", 0) or 0) > 0,
    ]
    return sum(1 for passed in checks if passed) / len(checks)


def _source_metadata(item: dict[str, Any]) -> dict[str, Any]:
    """候选数据来源追踪。HEAD: 两层模型，无 legacy properties 路径。"""
    commute_source = item.get("_commute_source") or "missing"
    poi_distances = item.get("_poi_distances") or {}
    return {
        "property": "unit_types",
        "institute": "institutes",
        "inventory": "unit_types.status",
        "semantic": (
            "unit_types.embedding"
            if item.get("embedding_score") is not None else "missing"
        ),
        "commute": commute_source,
        "poi": "institute_pois" if poi_distances else "missing",
        "missing_fields": [
            field_name for field_name, missing in {
                "area_sqm": item["unit_type"].area_sqm is None,
                "description": not bool(item["unit_type"].description or item["institute"].description),
                "commute": commute_source == "missing",
                "poi": not bool(poi_distances),
            }.items() if missing
        ],
    }


def rerank_candidates(
    candidates: list[dict[str, Any]],
    *,
    query: str,
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    """对混合召回池做确定性多信号重排，并注入解释分与来源。"""
    if not candidates:
        return []
    prices = [float(item["unit_type"].base_rent) for item in candidates]
    weights = {
        "semantic": 0.32,
        "lexical": 0.12,
        "price": 0.18,
        "commute": 0.14,
        "poi": 0.10,
        "quality": 0.08,
        "constraint": 0.06,
    }
    for item in candidates:
        semantic = item.get("embedding_score")
        semantic_score = float(semantic) if isinstance(semantic, (int, float)) else 0.5
        poi_raw = item.get("_poi_score")
        poi_score = float(poi_raw) / 100.0 if isinstance(poi_raw, (int, float)) and poi_raw > 1 else (
            float(poi_raw) if isinstance(poi_raw, (int, float)) else 0.5
        )
        breakdown_01 = {
            "semantic": max(0.0, min(1.0, semantic_score)),
            "lexical": lexical_relevance(query, item),
            "price": _price_score(float(item["unit_type"].base_rent), filters, prices),
            "commute": _commute_score(item, filters),
            "poi": max(0.0, min(1.0, poi_score)),
            "quality": _quality_score(item),
            "constraint": 1.0 if candidate_matches_filters(item, filters) else 0.65,
        }
        final_score = sum(breakdown_01[key] * weights[key] for key in weights) * 100
        item["_score_breakdown"] = {
            key: round(value * 100, 1) for key, value in breakdown_01.items()
        }
        item["_final_score"] = round(final_score, 1)
        item["_source_metadata"] = _source_metadata(item)

    candidates.sort(
        key=lambda item: (
            -float(item.get("_final_score", 0.0)),
            -int(item.get("available_rooms", 0) or 0),
            float(item["unit_type"].base_rent),
        )
    )
    for rank, item in enumerate(candidates, 1):
        item["_rank"] = rank
    return candidates


def _describe_match(item: dict[str, Any], filters: dict[str, Any]) -> str:
    """根据房源真实特征描述为什么匹配用户需求。"""
    unit_type = item["unit_type"]
    institute = item["institute"]
    user_wants = filters or {}
    parts: list[str] = []

    # 1. 价格贴合
    price = float(unit_type.base_rent)
    if user_wants.get("price_max") is not None and price <= float(user_wants["price_max"]):
        parts.append("预算内")
    elif user_wants.get("price_max") is not None:
        parts.append(f"略超预算{int(price - float(user_wants['price_max']))}元")

    # 2. 设施匹配
    inst_amenities = {_text(a) for a in (institute.amenities or []) if _text(a)}
    ut_amenities = {_text(a) for a in (unit_type.amenities or []) if _text(a)}
    all_amenities = inst_amenities | ut_amenities

    wanted_amenities = {_text(a) for a in (filters.get("amenities") or [])}
    matched = wanted_amenities & all_amenities
    if matched:
        parts.append(f"含{', '.join(list(matched)[:2])}")

    # 3. 公寓级设施亮点
    inst_highlights = [a for a in list(inst_amenities)[:3] if a and len(a) <= 6]
    if inst_highlights and not matched:
        parts.append(f"配套{', '.join(inst_highlights[:2])}")

    # 4. 户型亮点
    if unit_type.bedrooms is not None and unit_type.bathrooms is not None:
        if user_wants.get("bedrooms") == unit_type.bedrooms:
            parts.append(f"正好{unit_type.bedrooms}室")
    if "ensuite" in ut_amenities or "独卫" in ut_amenities or "独立卫浴" in ut_amenities:
        parts.append("带独卫")

    # 5. 通勤
    commute = item.get("_commute_minutes")
    if isinstance(commute, (int, float)):
        parts.append(f"通勤{int(commute)}分钟")

    # 6. POI 距离
    poi = item.get("_poi_distances") or {}
    if poi:
        nearest = min(poi.items(), key=lambda kv: kv[1])
        parts.append(f"近{nearest[0]}")

    if not parts:
        score = float(item.get("_final_score", 0.0))
        return f"综合匹配{score:.0f}分"
    return " · ".join(parts)


def recommendation_explanation(item: dict[str, Any], filters: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    """从房源真实特征生成推荐理由、优点和缺点。"""
    unit_type = item["unit_type"]
    institute = item["institute"]

    # 推荐理由：描述公寓如何匹配需求
    reason = _describe_match(item, filters)

    # 优点：基于公寓真实设施
    inst_amenities = {_text(a) for a in (institute.amenities or []) if _text(a)}
    ut_amenities = {_text(a) for a in (unit_type.amenities or []) if _text(a)}
    all_amenities = inst_amenities | ut_amenities

    amenity_display = {
        "wifi": "WiFi", "gym": "健身房", "pool": "泳池", "空调": "空调",
        "furnished": "家具齐全", "laundry": "洗衣机", "parking": "停车位",
        "security": "24h安保", "balcony": "阳台", "kitchen": "厨房",
        "study_room": "自习室", "elevator": "电梯", "cleaning": "定期保洁",
    }
    pros = [amenity_display[a] for a in list(all_amenities)[:3] if a in amenity_display]
    if not pros:
        pros = [f"{institute.name} · {unit_type.bedrooms or '?'}室"]

    # 缺点
    cons: list[str] = []
    missing = (item.get("_source_metadata") or {}).get("missing_fields") or []
    missing_labels = {"area_sqm": "面积待确认", "commute": "通勤数据待补充", "poi": "周边数据待补充", "description": "详情较少"}
    cons.extend(missing_labels[field_name] for field_name in missing if field_name in missing_labels)
    if filters.get("price_max") is not None and float(unit_type.base_rent) > float(filters["price_max"]):
        cons.append("超出原预算")
    cons = list(dict.fromkeys(cons))[:2]

    return reason, pros, cons


def build_source_manifest(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总本轮上下文的字段来源，供审计和前端展示。"""
    return {
        "policy": "missing 数据不得推断；推荐 ID 必须来自候选快照",
        "sources": [
            {
                "candidate_id": int(item.get("_property_id", item["unit_type"].id)),
                "unit_type_id": item.get("_unit_type_id"),
                **dict(item.get("_source_metadata") or {}),
            }
            for item in candidates[:10]
        ],
    }
