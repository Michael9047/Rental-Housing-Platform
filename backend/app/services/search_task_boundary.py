"""搜索任务边界服务 —— 用确定性规则区分继续、开新任务与必要澄清。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal, Mapping


TaskRelation = Literal["continue", "new", "clarify"]


@dataclass(frozen=True, slots=True)
class TaskBoundaryDecision:
    """一次任务边界判断结果。"""

    relation: TaskRelation
    reason: str
    reset_fields: list[str]
    clarification_question: str | None
    turn_anchors: dict[str, Any]


# 新任务不能继承的任务级状态。顺序固定，便于调用方稳定展示和测试。
NEW_TASK_RESET_FIELDS: tuple[str, ...] = (
    "country",
    "city",
    "district",
    "institution",
    "institute_id",
    "currency",
    "price_min",
    "price_max",
    "commute_mode",
    "commute_minutes",
    "_candidate_ids",
    "_compare_ids",
    "_cleared_filters",
)


# 学校同时提供默认国家和城市，用于识别“NUS 换 UCL”这类隐含跨市场变化。
_INSTITUTIONS: dict[str, dict[str, Any]] = {
    "NUS": {
        "country": "SG",
        "city": "Singapore",
        "aliases": (
            "National University of Singapore",
            "新加坡国立大学",
            "新加坡国大",
            "新国大",
            "NUS",
        ),
    },
    "NTU": {
        "country": "SG",
        "city": "Singapore",
        "aliases": (
            "Nanyang Technological University",
            "南洋理工大学",
            "南洋理工",
            "NTU",
        ),
    },
    "SMU": {
        "country": "SG",
        "city": "Singapore",
        "aliases": (
            "Singapore Management University",
            "新加坡管理大学",
            "新管大",
            "SMU",
        ),
    },
    "SUTD": {
        "country": "SG",
        "city": "Singapore",
        "aliases": (
            "Singapore University of Technology and Design",
            "新加坡科技设计大学",
            "新科大",
            "SUTD",
        ),
    },
    "UCL": {
        "country": "GB",
        "city": "London",
        "aliases": (
            "University College London",
            "伦敦大学学院",
            "倫敦大學學院",
            "UCL",
        ),
    },
    "LSE": {
        "country": "GB",
        "city": "London",
        "aliases": (
            "London School of Economics and Political Science",
            "London School of Economics",
            "伦敦政治经济学院",
            "倫敦政治經濟學院",
            "伦敦政经",
            "LSE",
        ),
    },
    "KCL": {
        "country": "GB",
        "city": "London",
        "aliases": (
            "King's College London",
            "Kings College London",
            "伦敦国王学院",
            "倫敦國王學院",
            "KCL",
        ),
    },
    "QMUL": {
        "country": "GB",
        "city": "London",
        "aliases": (
            "Queen Mary University of London",
            "伦敦玛丽女王大学",
            "倫敦瑪麗女王大學",
            "玛丽女王大学",
            "QMUL",
        ),
    },
    "HKU": {
        "country": "HK",
        "city": "Hong Kong",
        "aliases": (
            "The University of Hong Kong",
            "University of Hong Kong",
            "香港大学",
            "香港大學",
            "港大",
            "HKU",
        ),
    },
    "CUHK": {
        "country": "HK",
        "city": "Hong Kong",
        "aliases": (
            "The Chinese University of Hong Kong",
            "Chinese University of Hong Kong",
            "香港中文大学",
            "香港中文大學",
            "港中大",
            "CUHK",
        ),
    },
    "HKUST": {
        "country": "HK",
        "city": "Hong Kong",
        "aliases": (
            "Hong Kong University of Science and Technology",
            "香港科技大学",
            "香港科技大學",
            "港科大",
            "HKUST",
        ),
    },
    "UCLA": {
        "country": "US",
        "city": "Los Angeles",
        "aliases": (
            "University of California Los Angeles",
            "University of California, Los Angeles",
            "加州大学洛杉矶分校",
            "加州大學洛杉磯分校",
            "UCLA",
        ),
    },
    "USC": {
        "country": "US",
        "city": "Los Angeles",
        "aliases": (
            "University of Southern California",
            "南加州大学",
            "南加州大學",
            "南加大",
            "USC",
        ),
    },
}


_COUNTRIES: dict[str, tuple[str, ...]] = {
    "SG": ("新加坡", "Singapore", "SG"),
    "GB": (
        "英国",
        "英國",
        "United Kingdom",
        "Great Britain",
        "Britain",
        "England",
        "UK",
        "GB",
    ),
    "HK": ("中国香港", "中國香港", "香港", "Hong Kong", "HK"),
    "US": (
        "美国",
        "美國",
        "United States of America",
        "United States",
        "USA",
        "US",
    ),
    "CN": ("中国大陆", "中國大陸", "中国", "中國", "Mainland China", "China", "CN"),
    "AU": ("澳大利亚", "澳大利亞", "澳洲", "Australia", "AU"),
    "CA": ("加拿大", "Canada", "CA"),
}


_CITIES: dict[str, dict[str, Any]] = {
    "Singapore": {
        "country": "SG",
        "aliases": ("新加坡市", "新加坡", "Singapore"),
    },
    "London": {
        "country": "GB",
        "aliases": ("伦敦", "倫敦", "London"),
    },
    "Hong Kong": {
        "country": "HK",
        "aliases": ("香港", "Hong Kong"),
    },
    "Los Angeles": {
        "country": "US",
        "aliases": ("洛杉矶", "洛杉磯", "Los Angeles", "LA"),
    },
    "Suzhou": {
        "country": "CN",
        "aliases": ("苏州", "蘇州", "Suzhou"),
    },
    "Sydney": {
        "country": "AU",
        "aliases": ("悉尼", "Sydney"),
    },
    "Toronto": {
        "country": "CA",
        "aliases": ("多伦多", "多倫多", "Toronto"),
    },
}


_EXPLICIT_NEW_PATTERN = re.compile(
    r"(?:"
    r"另(?:一(?:个|套|批|组))|"
    r"另外(?:再|也)?[^。！？]{0,18}(?:找|看|搜|租)|"
    r"重新(?:帮我|替我|给我)?找(?:一批|一组|一套|些)?|"
    r"再找(?:一批|一组|一套|些)|"
    r"另一批|新(?:的)?(?:找房)?任务|新方案|"
    r"(?:帮|替|给)(?:我)?(?:朋友|同学|室友|家人)[^。！？]{0,12}(?:找|看)|"
    r"顺便(?:也)?[^。！？]{0,12}(?:找|看)|"
    r"从头(?:开始)?(?:找|看)|"
    r"\b(?:start over|new search|another (?:search|batch)|separate search)\b|"
    r"\b(?:for|help) my (?:friend|roommate|classmate|family)\b"
    r")",
    re.IGNORECASE,
)


_NEGATED_NEW_PATTERN = re.compile(
    r"(?:"
    r"(?:不(?:是|算|要|用)|并非|无需)(?:要|想|在)?"
    r"(?:另开|新开|重新开|开启)?(?:一(?:个|项))?(?:新的?)?"
    r"(?:找房|搜索)?(?:新)?(?:任务|方案|搜索)|"
    r"\bnot (?:a )?(?:new|separate) (?:task|search|plan)\b"
    r")",
    re.IGNORECASE,
)


_RETRACTION_PATTERN = re.compile(
    r"(?:"
    r"算了(?:吧)?|当(?:我)?没说|作罢|撤回(?:刚才|前面)?(?:那句|的话|的要求)?|"
    r"忽略(?:刚才|前面)(?:那句|的话|的要求)?|"
    r"\bnever mind\b|\bscratch that\b|\bdisregard (?:that|what I said)\b"
    r")",
    re.IGNORECASE,
)


_TARGET_REPLACEMENT_PATTERN = re.compile(
    r"(?:"
    r"(?:不要|不看|不再看|放弃|取消)[^。！？.!?]{0,40}"
    r"(?:换(?:成|到|去|看)?|改看|改成|转(?:去|到)|(?:再|想)?看看?)|"
    r"\b(?:drop|stop looking at|give up on)\b[^.!?]{0,48}"
    r"\b(?:switch|change|move)\s+(?:to|over to)\b"
    r")",
    re.IGNORECASE,
)


_CURRENT_MUTATION_PATTERN = re.compile(
    r"(?:"
    r"(?:把|将)?(?:我)?(?:当前|现在|现有|这次|这个|原来|原有|正在)(?:的)?"
    r"(?:搜索|找房|任务|方案|学校|目的地)?[^。！？]{0,24}"
    r"(?:改成|改为|改看|换成|换到|调整为|切到|转到)|"
    r"在(?:当前|现在|现有|这个|原来|原有)(?:搜索|任务|方案)里[^。！？]{0,24}"
    r"(?:改成|改为|改看|换成|换到|调整为|切到|转到)|"
    r"\b(?:change|switch|move|update) (?:my |the )?current "
    r"(?:search|task|plan|destination)[^.!?]{0,32}\b(?:to|into)\b"
    r")",
    re.IGNORECASE,
)


_COMPARE_OR_REFERENCE_PATTERN = re.compile(
    r"(?:"
    r"对比|比较|哪个好|哪套|哪一个更|区别|\bvs\b|\bpk\b|"
    r"第\s*(?:\d+|[一二两三四五六七八九十])\s*[个套条]?|"
    r"刚才(?:那|这)?[个套间]?|这个房源|那个房源|这套|那套|"
    r"候选清单|购物车|"
    r"\bcompare\b|\bcomparison\b|\bversus\b|\bwhich (?:one|school|property) is better\b|"
    r"\b(?:first|second|third|previous|last) (?:one|property|listing)\b"
    r")",
    re.IGNORECASE,
)


_FAQ_PATTERN = re.compile(
    r"(?:押金|定金|合同|签约|退款|退租|退押|预订流程|预约流程|"
    r"手续费|服务费|中介费|付款|支付|发票|水电费|账单|"
    r"入住手续|违约|客服|平台规则|政策|"
    r"\bdeposit\b|\bcontract\b|\brefund\b|\bbooking\b|\bfees?\b|"
    r"\bpayment\b|\binvoice\b|\butilities\b|\bpolicy\b|\bcustomer service\b)",
    re.IGNORECASE,
)


_CANCEL_PATTERN = re.compile(
    r"(?:取消|清除|清空|去掉|移除|不再要求|不限|不设限|无所谓|都可以|"
    r"\bcancel\b|\bclear\b|\bremove\b|\bno preference\b|\bany area\b)",
    re.IGNORECASE,
)


_VAGUE_SCHOOL_PATTERN = re.compile(
    r"(?:学校|大学)(?:附近|周边|旁边)|离(?:这个|那个|该|这所|那所)?学校(?:近|不远)|"
    r"(?:这个|那个|该|这所|那所)学校|"
    r"\b(?:near|around) (?:the |this |that )?school\b|\b(?:this|that) school\b",
    re.IGNORECASE,
)


_VAGUE_PLACE_PATTERN = re.compile(
    r"(?:那里|那边|那儿|那一带|那个地方|这边|这里|这附近|那附近|"
    r"\bthere\b|\bthat area\b|\bthis area\b)",
    re.IGNORECASE,
)


def _is_ascii_alias(alias: str) -> bool:
    return all(ord(char) < 128 for char in alias)


def _alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias)
    if _is_ascii_alias(alias) and alias[0].isalnum() and alias[-1].isalnum():
        escaped = rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"
    return re.compile(escaped, re.IGNORECASE)


def _find_last_alias_hit(
    text: str,
    catalogue: Mapping[str, tuple[str, ...]],
) -> tuple[str, int, int] | None:
    """返回规范值、结束位置和长度；同位置结束时优先完整别名。"""
    best: tuple[int, int, str] | None = None
    for canonical, aliases in catalogue.items():
        for alias in aliases:
            for match in _alias_pattern(alias).finditer(text):
                # 国家代码 US 只有大写才视为美国，避免把英文代词 “us” 当地点。
                if canonical == "US" and alias == "US" and match.group(0) != "US":
                    continue
                candidate = (match.end(), len(alias), canonical)
                if best is None or candidate[:2] > best[:2]:
                    best = candidate
    return (best[2], best[0], best[1]) if best else None


def _find_last_alias(
    text: str,
    catalogue: Mapping[str, tuple[str, ...]],
) -> str | None:
    hit = _find_last_alias_hit(text, catalogue)
    return hit[0] if hit else None


def _institution_catalogue() -> dict[str, tuple[str, ...]]:
    return {
        name: tuple(info["aliases"])
        for name, info in _INSTITUTIONS.items()
    }


def _city_catalogue() -> dict[str, tuple[str, ...]]:
    return {
        name: tuple(info["aliases"])
        for name, info in _CITIES.items()
    }


def _normalize_catalogue_value(
    value: Any,
    catalogue: Mapping[str, tuple[str, ...]],
) -> Any:
    """将请求和历史里的中英文锚点统一成规范值。"""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return None
    direct = _find_last_alias(stripped, catalogue)
    if direct is not None:
        return direct
    return re.sub(r"\s+", " ", stripped).casefold()


def _normalize_country(value: Any) -> Any:
    return _normalize_catalogue_value(value, _COUNTRIES)


def _normalize_city(value: Any) -> Any:
    return _normalize_catalogue_value(value, _city_catalogue())


def _normalize_institution(value: Any) -> Any:
    return _normalize_catalogue_value(value, _institution_catalogue())


def _extract_message_anchors(message: str) -> dict[str, Any]:
    anchors: dict[str, Any] = {}
    institution_hit = _find_last_alias_hit(message, _institution_catalogue())
    city_hit = _find_last_alias_hit(message, _city_catalogue())
    country_hit = _find_last_alias_hit(message, _COUNTRIES)
    institution = institution_hit[0] if institution_hit else None
    city = city_hit[0] if city_hit else None
    country = country_hit[0] if country_hit else None

    if institution:
        info = _INSTITUTIONS[institution]
        anchors.update({
            "institution": institution,
            "country": info["country"],
            "city": info["city"],
        })
    if city:
        anchors["city"] = city
        anchors["country"] = _CITIES[city]["country"]
    # “从新加坡换到伦敦”同时含旧国家和新城市；较早的国家不能覆盖新城市推断。
    latest_destination_end = max(
        institution_hit[1] if institution_hit else -1,
        city_hit[1] if city_hit else -1,
    )
    if country and country_hit and country_hit[1] >= latest_destination_end:
        anchors["country"] = country
    return anchors


def _extract_turn_anchors(
    message: str,
    turn_filters: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """提取本轮显式锚点；结构化 turn_filters 拥有最高优先级。"""
    anchors = _extract_message_anchors(message)
    supplied = turn_filters or {}

    if supplied.get("institution") not in (None, ""):
        institution = _normalize_institution(supplied["institution"])
        anchors["institution"] = institution
        if institution in _INSTITUTIONS:
            info = _INSTITUTIONS[institution]
            anchors["country"] = info["country"]
            anchors["city"] = info["city"]
    if supplied.get("city") not in (None, ""):
        city = _normalize_city(supplied["city"])
        anchors["city"] = city
        if city in _CITIES:
            anchors["country"] = _CITIES[city]["country"]
    if supplied.get("country") not in (None, ""):
        anchors["country"] = _normalize_country(supplied["country"])
    if supplied.get("district") not in (None, ""):
        anchors["district"] = str(supplied["district"]).strip().casefold()
    if supplied.get("institute_id") not in (None, ""):
        anchors["institute_id"] = supplied["institute_id"]
    return anchors


def _current_anchors(current_filters: Mapping[str, Any]) -> dict[str, Any]:
    anchors: dict[str, Any] = {}
    institution = _normalize_institution(current_filters.get("institution"))
    if institution is not None:
        anchors["institution"] = institution
        if institution in _INSTITUTIONS:
            info = _INSTITUTIONS[institution]
            anchors.update({"country": info["country"], "city": info["city"]})

    city = _normalize_city(current_filters.get("city"))
    if city is not None:
        anchors["city"] = city
        if city in _CITIES:
            anchors["country"] = _CITIES[city]["country"]
    country = _normalize_country(current_filters.get("country"))
    if country is not None:
        anchors["country"] = country
    if current_filters.get("district") not in (None, ""):
        anchors["district"] = str(current_filters["district"]).strip().casefold()
    if current_filters.get("institute_id") not in (None, ""):
        anchors["institute_id"] = current_filters["institute_id"]
    return anchors


def _anchor_conflicts(
    current: Mapping[str, Any],
    turn: Mapping[str, Any],
) -> set[str]:
    return {
        field
        for field in ("country", "city", "district", "institution", "institute_id")
        if field in current and field in turn and current[field] != turn[field]
    }


def _has_current_task(current_filters: Mapping[str, Any], has_candidates: bool) -> bool:
    if has_candidates:
        return True
    return any(
        value not in (None, "", [], {})
        for key, value in current_filters.items()
        if not key.startswith("_")
    ) or bool(current_filters.get("_candidate_ids"))


def _effective_message_after_retraction(message: str) -> tuple[str, bool]:
    """只保留最后一次撤回标记之后的文本，避免已撤回条件泄漏。"""
    matches = list(_RETRACTION_PATTERN.finditer(message))
    if not matches:
        return message, False
    return message[matches[-1].end():], True


def effective_task_message(message: str) -> str:
    """返回用于条件提取的最终有效话术，供分发器与边界判断共用。"""
    return _effective_message_after_retraction(str(message or ""))[0].strip()


def _reset_fields_for_conflicts(conflicts: set[str]) -> list[str]:
    """返回冲突锚点及依赖它们的派生状态。"""
    if not conflicts:
        return []
    if "country" in conflicts:
        return list(NEW_TASK_RESET_FIELDS)

    fields: set[str] = {"_candidate_ids", "_compare_ids", "_cleared_filters"}
    if "city" in conflicts:
        fields.update({
            "city", "district", "institution", "institute_id", "currency",
            "price_min", "price_max", "commute_mode", "commute_minutes",
        })
    if "district" in conflicts:
        fields.update({"district", "institute_id", "commute_mode", "commute_minutes"})
    if "institution" in conflicts:
        fields.update({
            "district", "institution", "institute_id",
            "commute_mode", "commute_minutes",
        })
    if "institute_id" in conflicts:
        fields.add("institute_id")
    return [field for field in NEW_TASK_RESET_FIELDS if field in fields]


def _clarification_for_vague_reference(
    message: str,
    current: Mapping[str, Any],
    turn: Mapping[str, Any],
) -> tuple[str, str] | None:
    """仅在指代确实没有可用锚点时追问。"""
    if _VAGUE_SCHOOL_PATTERN.search(message):
        if not (turn.get("institution") or current.get("institution")):
            return (
                "学校指代缺少可解析锚点",
                "你说的是哪所学校？可以告诉我学校名称或缩写吗？",
            )
    if _VAGUE_PLACE_PATTERN.search(message):
        location_fields = ("country", "city", "district", "institution", "institute_id")
        if not any(turn.get(field) or current.get(field) for field in location_fields):
            return (
                "地点指代缺少可解析锚点",
                "你说的“那里/那边”是哪个国家、城市或区域？",
            )
    return None


def detect_task_boundary(
    message: str,
    current_filters: Mapping[str, Any] | None,
    turn_filters: Mapping[str, Any] | None = None,
    has_candidates: bool = False,
    mode: str = "auto",
) -> TaskBoundaryDecision:
    """判断本轮是在继续当前搜索、开启新搜索，还是必须先澄清。"""
    text = str(message or "").strip()
    effective_text, had_retraction = _effective_message_after_retraction(text)
    current_filters = current_filters or {}
    turn_anchors = _extract_turn_anchors(effective_text, turn_filters)
    active_anchors = _current_anchors(current_filters)
    conflicts = _anchor_conflicts(active_anchors, turn_anchors)

    normalized_mode = str(mode or "auto").strip().casefold()
    if normalized_mode == "new":
        return TaskBoundaryDecision(
            relation="new",
            reason="调用方显式指定新任务",
            reset_fields=list(NEW_TASK_RESET_FIELDS),
            clarification_question=None,
            turn_anchors=turn_anchors,
        )
    if normalized_mode == "continue":
        return TaskBoundaryDecision(
            relation="continue",
            reason="调用方显式指定继续当前任务",
            reset_fields=_reset_fields_for_conflicts(conflicts),
            clarification_question=None,
            turn_anchors=turn_anchors,
        )

    vague = _clarification_for_vague_reference(
        effective_text,
        active_anchors,
        turn_anchors,
    )
    if vague is not None:
        reason, question = vague
        return TaskBoundaryDecision(
            relation="clarify",
            reason=reason,
            reset_fields=[],
            clarification_question=question,
            turn_anchors=turn_anchors,
        )

    has_current_task = _has_current_task(current_filters, has_candidates)
    if not has_current_task:
        return TaskBoundaryDecision(
            relation="continue",
            reason="尚无当前搜索任务，本轮直接作为首轮条件",
            reset_fields=[],
            clarification_question=None,
            turn_anchors=turn_anchors,
        )

    # 用户明确说“把当前搜索改成”时，即便跨市场也属于原任务改写。
    if _CURRENT_MUTATION_PATTERN.search(effective_text):
        return TaskBoundaryDecision(
            relation="continue",
            reason="用户明确修改当前搜索",
            reset_fields=_reset_fields_for_conflicts(conflicts),
            clarification_question=None,
            turn_anchors=turn_anchors,
        )

    # “不是新任务”优先于其中包含的“新任务”字样。
    if _NEGATED_NEW_PATTERN.search(effective_text):
        return TaskBoundaryDecision(
            relation="continue",
            reason="用户明确否定另开任务",
            reset_fields=_reset_fields_for_conflicts(conflicts),
            clarification_question=None,
            turn_anchors=turn_anchors,
        )

    # 放弃旧目的地并换到新目的地属于当前任务改写，但不能继承旧市场状态。
    if conflicts and _TARGET_REPLACEMENT_PATTERN.search(effective_text):
        return TaskBoundaryDecision(
            relation="continue",
            reason="用户明确替换当前任务的目标",
            reset_fields=_reset_fields_for_conflicts(conflicts),
            clarification_question=None,
            turn_anchors=turn_anchors,
        )

    if _EXPLICIT_NEW_PATTERN.search(effective_text):
        return TaskBoundaryDecision(
            relation="new",
            reason="用户明确要求另开一批搜索",
            reset_fields=list(NEW_TASK_RESET_FIELDS),
            clarification_question=None,
            turn_anchors=turn_anchors,
        )

    # FAQ、候选引用、对比和取消只操作当前上下文，不能因提到另一所学校而误开任务。
    if (
        _COMPARE_OR_REFERENCE_PATTERN.search(effective_text)
        or _FAQ_PATTERN.search(effective_text)
        or _CANCEL_PATTERN.search(effective_text)
    ):
        return TaskBoundaryDecision(
            relation="continue",
            reason="本轮是当前任务内的问答、对比、引用或条件取消",
            reset_fields=[],
            clarification_question=None,
            # 这些学校/地点只用于提问或对比，不得被分发器当作新搜索条件。
            turn_anchors={},
        )

    if conflicts:
        conflict_labels = {
            "country": "国家",
            "city": "城市",
            "district": "区域",
            "institution": "学校",
            "institute_id": "公寓",
        }
        names = "、".join(conflict_labels[field] for field in conflict_labels if field in conflicts)
        return TaskBoundaryDecision(
            relation="new",
            reason=f"本轮{names}与当前搜索冲突",
            reset_fields=list(NEW_TASK_RESET_FIELDS),
            clarification_question=None,
            turn_anchors=turn_anchors,
        )

    return TaskBoundaryDecision(
        relation="continue",
        reason=(
            "用户已撤回前述要求，本轮按最后意图继续当前搜索"
            if had_retraction
            else "本轮属于当前搜索的补充或调整"
        ),
        reset_fields=[],
        clarification_question=None,
        turn_anchors=turn_anchors,
    )


__all__ = [
    "NEW_TASK_RESET_FIELDS",
    "TaskBoundaryDecision",
    "TaskRelation",
    "detect_task_boundary",
    "effective_task_message",
]
