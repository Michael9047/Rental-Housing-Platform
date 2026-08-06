"""查询理解 —— 一次调用完成筛选提取与 Query Rewrite。"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.services.llm_service import get_llm_service


QUERY_UNDERSTANDING_PROMPT = """你是海外租房搜索的查询理解模块。结合当前会话状态理解用户最新一句话，只输出 JSON。

目标：
1. extracted_filters：只提取用户这一次明确新增或修改的条件，不要复制未提及的旧条件。
2. remove_fields/remove_values：用户明确取消的条件。
3. rewritten_query：把省略、口语和相对说法改成一条可独立检索的中文查询；允许引用当前状态，但不得新增硬条件。

字段约束：
- currency: CNY/GBP/SGD/USD/HKD
- property_type: studio/1-bed/2-bed/shared/house
- room_type: studio/ensuite/1bed/2bed/3bed+/shared
- commute_mode: walking/bicycling/driving/transit
- amenities 使用标准值：独立卫浴、独立厨房、宠物友好、WiFi、空调、洗衣机、阳台、电梯、健身房、自习室、泳池、家具齐全
- "1500左右"可转成 price_min=1350, price_max=1650
- "短租/短期租住"固定转成 min_lease_months=1, max_lease_months=3
- "中租"固定转成 min_lease_months=3, max_lease_months=6；"长租"转成 min_lease_months=12
- "便宜一点"结合当前 price_max 下调约 15%；"预算提高一点"上调约 15%
- "不要独卫了"放 remove_values.amenities=["独立卫浴"]，不要输出 amenities=[]
- 用户说"必须/一定/只要"时，把对应字段名放进 extracted_filters.hard_filters；
  用户说"最好/尽量/优先"时放进 extracted_filters.soft_preferences
- 不确定的字段不要输出，禁止用 null 覆盖旧状态

输出格式：
{
  "extracted_filters": {},
  "remove_fields": [],
  "remove_values": {},
  "rewritten_query": "",
  "query_kind": "exact|relative|reference|exploratory",
  "explicit_memory_fields": []
}

当前会话状态由用户此前明确表达而来，可用于消解"再便宜点、学校附近、还是单间"等省略；如果本轮与状态冲突，以本轮为准。"""

_VALID_FILTER_FIELDS = frozenset({
    "country", "district", "price_min", "price_max", "bedrooms",
    "property_type", "amenities", "room_type", "bathrooms", "area_min",
    "area_max", "min_lease_months", "max_lease_months", "available_from",
    "poi_requirements", "commute_mode", "commute_minutes", "institution",
    "female_only", "hard_filters", "soft_preferences", "currency",
})
_VALID_QUERY_KINDS = frozenset({"exact", "relative", "reference", "exploratory"})

_CITY_HINTS = ("伦敦", "香港", "洛杉矶", "旧金山", "苏州", "园区")
_INSTITUTION_HINTS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"(?<![A-Za-z])NUS(?![A-Za-z])|新加坡国立大学", re.IGNORECASE), "NUS", "SG"),
    (re.compile(r"(?<![A-Za-z])NTU(?![A-Za-z])|南洋理工大学", re.IGNORECASE), "NTU", "SG"),
    (re.compile(r"(?<![A-Za-z])UCLA(?![A-Za-z])|加州大学洛杉矶分校", re.IGNORECASE), "UCLA", "US"),
    (re.compile(r"(?<![A-Za-z])UCL(?![A-Za-z])|伦敦大学学院", re.IGNORECASE), "UCL", "GB"),
    (re.compile(r"(?<![A-Za-z])LSE(?![A-Za-z])|伦敦政治经济学院", re.IGNORECASE), "LSE", "GB"),
    (re.compile(r"(?<![A-Za-z])HKU(?![A-Za-z])|香港大学", re.IGNORECASE), "HKU", "HK"),
)
_COUNTRY_HINTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"新加坡|Singapore", re.IGNORECASE), "SG"),
    (re.compile(r"中国大陆|中国|China", re.IGNORECASE), "CN"),
    (re.compile(r"英国|UK|United Kingdom", re.IGNORECASE), "GB"),
    (re.compile(r"美国|USA|United States", re.IGNORECASE), "US"),
    (re.compile(r"香港|Hong Kong", re.IGNORECASE), "HK"),
)
_AMENITY_ALIASES = {
    "独立卫浴": ("独卫", "独立卫浴"),
    "独立厨房": ("独立厨房",),
    "宠物友好": ("宠物友好", "可养宠", "可以养宠物"),
    "WiFi": ("wifi", "无线网"),
    "空调": ("空调",),
    "洗衣机": ("洗衣机",),
    "阳台": ("阳台",),
    "电梯": ("电梯",),
    "健身房": ("健身房",),
    "自习室": ("自习室", "学习室", "自习空间", "study room"),
    "泳池": ("泳池", "游泳池"),
    "家具齐全": ("家具齐全", "拎包入住"),
    "快递代收": ("快递代收", "代收快递", "包裹代收", "快递", "收快递", "取快递"),
    "停车位": ("停车位", "停车场", "车位"),
    "门禁": ("门禁", "门禁系统", "24h安保", "24小时安保"),
    "公共厨房": ("公共厨房", "共享厨房"),
    "冰箱": ("冰箱",),
    "微波炉": ("微波炉",),
}


@dataclass(slots=True)
class QueryUnderstanding:
    """可验证、可记录的查询理解结果。"""

    extracted_filters: dict[str, Any] = field(default_factory=dict)
    remove_fields: list[str] = field(default_factory=list)
    remove_values: dict[str, list[Any]] = field(default_factory=dict)
    rewritten_query: str = ""
    query_kind: str = "exact"
    explicit_memory_fields: list[str] = field(default_factory=list)
    used_llm: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def embedding_text(self, original_query: str) -> str:
        """构建语义召回文本，避免把内部说明和来源标签编码进去。"""
        return (self.rewritten_query.strip() or original_query.strip())[:1200]


def _apply_explicit_location_hints(message: str, extracted: dict[str, Any]) -> None:
    """用确定性词典兜住高频学校与国家，避免分类模型漏掉显式地点。"""
    for pattern, institution, country in _INSTITUTION_HINTS:
        if pattern.search(message):
            extracted["institution"] = institution
            extracted["country"] = country
            hard_filters = list(extracted.get("hard_filters") or [])
            if "institution" not in hard_filters:
                hard_filters.append("institution")
            extracted["hard_filters"] = hard_filters
            break

    if "country" not in extracted:
        for pattern, country in _COUNTRY_HINTS:
            if pattern.search(message):
                extracted["country"] = country
                break

    # "新加坡"在当前数据模型中是国家市场，不应再作为中文 district 与
    # 英文 Singapore 城市值做一次相互冲突的精确筛选。
    if extracted.get("country") == "SG" and str(extracted.get("district") or "").lower() in {
        "新加坡", "singapore",
    }:
        extracted.pop("district", None)


def _apply_location_switch_resets(
    previous_filters: dict[str, Any],
    extracted: dict[str, Any],
    remove_fields: list[str],
) -> None:
    """显式切换国家时清掉旧学校和区域，避免跨市场条件互相冲突。"""
    previous_country = str(previous_filters.get("country") or "").upper()
    next_country = str(extracted.get("country") or "").upper()
    if not previous_country or not next_country or previous_country == next_country:
        return
    for field_name in ("institution", "district"):
        if field_name not in extracted and field_name not in remove_fields:
            remove_fields.append(field_name)


def _apply_explicit_lease_hints(
    message: str,
    extracted: dict[str, Any],
    remove_fields: list[str] | None = None,
) -> None:
    """确定性识别租期口语，避免模型漏掉"短租"等搜索页可见条件。"""
    removed = remove_fields if remove_fields is not None else []
    exact_months = re.search(
        r"(?:租|住|租期(?:是|为)?)\s*(\d{1,2})\s*(?:个)?月",
        message,
    )
    if exact_months:
        months = max(1, int(exact_months.group(1)))
        extracted["min_lease_months"] = months
        extracted["max_lease_months"] = months
        return

    if re.search(r"短租|短期(?:租|住)|按月短租", message):
        extracted["min_lease_months"] = 1
        extracted["max_lease_months"] = 3
    elif re.search(r"中租|中期(?:租|住)", message):
        extracted["min_lease_months"] = 3
        extracted["max_lease_months"] = 6
    elif re.search(r"长租|长期(?:租|住)", message):
        extracted["min_lease_months"] = 12
        extracted.pop("max_lease_months", None)
        if "max_lease_months" not in removed:
            removed.append("max_lease_months")


def _safe_filters(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        key: item for key, item in value.items()
        if key in _VALID_FILTER_FIELDS and item is not None and item != "" and item != []
    }


def _rule_fallback(message: str, previous_filters: dict[str, Any]) -> QueryUnderstanding:
    """无 LLM 时处理高频相对修改，保证跨轮搜索不完全失效。"""
    extracted: dict[str, Any] = {}
    remove_fields: list[str] = []
    remove_values: dict[str, list[Any]] = {}
    lowered = re.search(r"(便宜一点|再便宜|预算降|少一点)", message)
    raised = re.search(r"(预算提高|贵一点也行|多一点|加点预算)", message)
    current_max = previous_filters.get("price_max")
    if current_max is not None:
        try:
            if lowered:
                extracted["price_max"] = int(float(current_max) * 0.85)
            elif raised:
                extracted["price_max"] = int(float(current_max) * 1.15)
        except (TypeError, ValueError):
            pass
    if re.search(r"(不限预算|预算无所谓|取消预算)", message):
        remove_fields.extend(["price_min", "price_max"])
    if re.search(r"(不限区域|区域无所谓|取消地区)", message):
        remove_fields.append("district")

    # 常见绝对预算；"左右"生成区间，"以上/至少"作为下限，其余作为上限。
    money_match = re.search(
        r"(?:预算|月租|租金)?\s*(至少|不低于)?\s*"
        r"([0-9]+(?:\.[0-9]+)?)\s*(万|千|[kK])?\s*"
        r"(?:人民币|英镑|镑|新币|美元|港币|元|块|£|S\$|\$)?\s*"
        r"(以内|以下|不超过|左右|以上|不低于|至少)?",
        message,
    )
    if money_match and (money_match.group(1) or money_match.group(4) or re.search(r"预算|月租|租金", message)):
        amount = float(money_match.group(2))
        multiplier = {"万": 10_000, "千": 1_000, "k": 1_000, "K": 1_000}.get(
            money_match.group(3) or "", 1
        )
        amount *= multiplier
        qualifier = money_match.group(1) or money_match.group(4)
        if qualifier == "左右":
            extracted["price_min"] = int(amount * 0.9)
            extracted["price_max"] = int(amount * 1.1)
        elif qualifier in {"以上", "不低于", "至少"}:
            extracted["price_min"] = int(amount)
        else:
            extracted["price_max"] = int(amount)

    currency_patterns = {
        "GBP": r"(英镑|镑|£)",
        "SGD": r"(新币|新加坡元|S\$)",
        "HKD": r"(港币|港元|HK\$)",
        "USD": r"(美元|美金|(?<![A-Z])\$)",
        "CNY": r"(人民币|元|块|¥)",
    }
    for currency, pattern in currency_patterns.items():
        if re.search(pattern, message, re.IGNORECASE):
            extracted["currency"] = currency
            break

    for city in _CITY_HINTS:
        if city in message:
            extracted["district"] = city
            break

    district_match = re.search(
        r"(?:只看|想看|找|位于)\s*"
        r"([A-Za-z][A-Za-z\s-]{1,30}?|[\u4e00-\u9fff]{2,12}?)\s*"
        r"(?:区|区域)(?:的|里|内)?",
        message,
        re.IGNORECASE,
    )
    if district_match:
        extracted["district"] = district_match.group(1).strip()

    institution = re.search(r"(?<![A-Za-z])([A-Z]{2,8})(?![A-Za-z])", message)
    if institution:
        extracted["institution"] = institution.group(1)
    _apply_explicit_location_hints(message, extracted)
    _apply_location_switch_resets(previous_filters, extracted, remove_fields)
    _apply_explicit_lease_hints(message, extracted, remove_fields)

    bedroom_match = re.search(r"(\d+)\s*(?:室|房|bed)", message, re.IGNORECASE)
    if bedroom_match:
        extracted["bedrooms"] = int(bedroom_match.group(1))
    if re.search(r"(studio|单间|开间)", message, re.IGNORECASE):
        extracted["property_type"] = "studio"
        extracted["room_type"] = "studio"
    elif re.search(r"(合租|shared|床位)", message, re.IGNORECASE):
        extracted["property_type"] = "shared"
        extracted["room_type"] = "shared"

    amenities: list[str] = []
    removed_amenities: list[str] = []
    for canonical, aliases in _AMENITY_ALIASES.items():
        for alias in aliases:
            if not re.search(re.escape(alias), message, re.IGNORECASE):
                continue
            if re.search(rf"(不要|取消|不需要).{{0,4}}{re.escape(alias)}|{re.escape(alias)}.{{0,4}}不要", message, re.IGNORECASE):
                removed_amenities.append(canonical)
            else:
                amenities.append(canonical)
            break
    if amenities:
        extracted["amenities"] = list(dict.fromkeys(amenities))
    if removed_amenities:
        remove_values["amenities"] = list(dict.fromkeys(removed_amenities))

    commute = re.search(
        r"(步行|走路|公交|地铁|开车|骑车).{0,6}?(\d+)\s*分钟(?:以内|内|左右)?",
        message,
    )
    if commute:
        mode_text = commute.group(1)
        extracted["commute_mode"] = {
            "步行": "walking", "走路": "walking", "公交": "transit",
            "地铁": "transit", "开车": "driving", "骑车": "bicycling",
        }[mode_text]
        extracted["commute_minutes"] = int(commute.group(2))

    if re.search(r"(仅限女生|只要女生|女生公寓|female.?only)", message, re.IGNORECASE):
        extracted["female_only"] = True

    hard_fields: list[str] = []
    soft_fields: list[str] = []
    if "institution" in extracted:
        hard_fields.append("institution")
    if re.search(r"(必须|一定|硬性|只要|只看|不能没有|至少|不低于|以上)", message):
        hard_fields.extend(
            field_name for field_name in (
                "amenities", "room_type", "commute_minutes", "female_only",
                "price_min", "price_max", "district",
            )
            if field_name in extracted
        )
    if re.search(r"(最好|尽量|优先|可以的话)", message):
        soft_fields.extend(
            field_name for field_name in (
                "amenities", "room_type", "commute_minutes", "price_max", "district",
            )
            if field_name in extracted
        )
    if hard_fields:
        extracted["hard_filters"] = list(dict.fromkeys(hard_fields))
    if soft_fields:
        extracted["soft_preferences"] = list(dict.fromkeys(soft_fields))

    if re.search(r"第\s*(?:\d+|[一二两三四五六七八九十])\s*[个套间]|最便宜|刚才那", message):
        query_kind = "reference"
    elif lowered or raised or remove_fields or remove_values:
        query_kind = "relative"
    elif re.search(r"(随便看看|有什么推荐|先看看)", message):
        query_kind = "exploratory"
    else:
        query_kind = "exact"

    rewrite_state = dict(previous_filters)
    for field_name in remove_fields:
        rewrite_state.pop(field_name, None)
    rewrite_state.update(extracted)
    rewrite_parts = [message.strip()]
    if rewrite_state:
        stable_state = {
            key: rewrite_state[key]
            for key in (
                "institution", "district", "price_min", "price_max", "currency",
                "bedrooms", "room_type", "amenities", "commute_mode", "commute_minutes",
                "min_lease_months", "max_lease_months",
            )
            if key in rewrite_state
        }
        labels = {
            "institution": "学校", "district": "区域", "price_min": "最低预算",
            "price_max": "最高预算", "currency": "币种", "bedrooms": "卧室",
            "room_type": "房型", "amenities": "设施", "commute_mode": "通勤方式",
            "commute_minutes": "通勤分钟", "min_lease_months": "最短租期",
            "max_lease_months": "最长租期",
        }
        state_text = "，".join(
            f"{labels.get(key, key)}={value if not isinstance(value, list) else '、'.join(map(str, value))}"
            for key, value in stable_state.items()
        )
        if state_text:
            rewrite_parts.append(f"当前有效条件：{state_text}")

    return QueryUnderstanding(
        extracted_filters=extracted,
        remove_fields=remove_fields,
        remove_values=remove_values,
        rewritten_query="；".join(part for part in rewrite_parts if part),
        query_kind=query_kind,
        explicit_memory_fields=list(extracted),
        used_llm=False,
    )


async def understand_query(
    message: str,
    previous_filters: dict[str, Any] | None = None,
    rolling_summary: str | None = None,
) -> QueryUnderstanding:
    """结合短期状态理解查询；所有结构化输出均经过白名单校验。"""
    previous_filters = previous_filters or {}
    llm = get_llm_service()
    if not llm.is_available:
        return _rule_fallback(message, previous_filters)

    state_payload = {
        "filters": previous_filters,
        "summary": (rolling_summary or "")[:1200],
    }
    user_prompt = (
        f"当前状态：\n{json.dumps(state_payload, ensure_ascii=False)}\n\n"
        f"用户最新消息：{message}"
    )
    try:
        raw = await llm.complete_json(
            QUERY_UNDERSTANDING_PROMPT,
            user_prompt,
            temperature=0.0,
            max_tokens=900,
            model=None,  # 使用默认模型（settings.deepseek_chat_model）
        )
    except Exception:
        return _rule_fallback(message, previous_filters)

    if not isinstance(raw, dict):
        return _rule_fallback(message, previous_filters)
    extracted = _safe_filters(raw.get("extracted_filters"))
    _apply_explicit_location_hints(message, extracted)
    remove_fields = [
        str(field_name) for field_name in (raw.get("remove_fields") or [])
        if str(field_name) in _VALID_FILTER_FIELDS
    ]
    raw_remove_values = raw.get("remove_values")
    remove_values = {
        str(key): list(value)
        for key, value in (raw_remove_values.items() if isinstance(raw_remove_values, dict) else [])
        if str(key) in _VALID_FILTER_FIELDS and isinstance(value, list)
    }
    deterministic_filters = _rule_fallback(message, previous_filters).extracted_filters
    deterministic_fields = {
        field_name for field_name in ("price_min", "price_max", "currency", "district")
        if field_name in deterministic_filters
    }
    for field_name in deterministic_fields:
        extracted[field_name] = deterministic_filters[field_name]
    if deterministic_filters.get("hard_filters"):
        extracted["hard_filters"] = list(dict.fromkeys([
            *(extracted.get("hard_filters") or []),
            *deterministic_filters["hard_filters"],
        ]))
    _apply_location_switch_resets(previous_filters, extracted, remove_fields)
    _apply_explicit_lease_hints(message, extracted, remove_fields)
    query_kind = str(raw.get("query_kind", "exact"))
    if query_kind not in _VALID_QUERY_KINDS:
        query_kind = "exact"
    rewritten_query = str(raw.get("rewritten_query") or message).strip()[:1000]
    explicit_memory_fields = [
        str(field_name) for field_name in (raw.get("explicit_memory_fields") or [])
        if str(field_name) in extracted
    ]
    for field_name in dict.fromkeys((
        "institution", "country", "min_lease_months", "max_lease_months",
        *sorted(deterministic_fields),
    )):
        if field_name in extracted and field_name not in explicit_memory_fields:
            explicit_memory_fields.append(field_name)
    return QueryUnderstanding(
        extracted_filters=extracted,
        remove_fields=remove_fields,
        remove_values=remove_values,
        rewritten_query=rewritten_query,
        query_kind=query_kind,
        explicit_memory_fields=explicit_memory_fields,
        used_llm=True,
    )
