"""找房需求槽位（slot filling）—— 循循善诱式追问

把所有缺失条件一次性摆成多组可勾选面板（每个维度一行 chips），用户可以跨维度
多选后一次「发送」提交，而不是一个条件一个条件地串行追问。已经知道的条件
（用户说过的、前端筛选栏填的）绝不重复问。

槽位状态是一个 dict，值有三种：
- 具体值（如 district="苏州工业园区"、price_max=3000）
- ANY 哨兵：用户明确说了"不限/随便" → 视为已回答，不再追问
- 缺失（key 不存在或为 None）→ 需要追问
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# 用户明确表示"不限"时写入的哨兵值：和"还没问"区分开，避免反复追问
ANY = "__any__"

# 追问顺序：区域 → 预算 → 户型 → 类型
SLOT_ORDER = ["district", "price_max", "bedrooms", "property_type"]


@dataclass(frozen=True)
class SlotOption:
    label: str
    value: str  # 传回后端时用的值；"__any__" 表示不限


@dataclass(frozen=True)
class SlotSpec:
    field: str
    label: str
    question: str
    options: list[SlotOption]
    allow_custom: bool = True


SLOT_SPECS: dict[str, SlotSpec] = {
    "district": SlotSpec(
        field="district",
        label="城市/区域",
        question="你想租在哪个城市或区域？",
        options=[
            SlotOption("苏州工业园区", "苏州工业园区"),
            SlotOption("苏州姑苏区", "苏州姑苏区"),
            SlotOption("上海", "上海"),
            SlotOption("北京", "北京"),
            SlotOption("深圳", "深圳"),
            SlotOption("不限", ANY),
        ],
    ),
    "price_max": SlotSpec(
        field="price_max",
        label="预算",
        question="预算大概多少？（每月）",
        options=[
            SlotOption("2000 以内", "2000"),
            SlotOption("2000-3000", "3000"),
            SlotOption("3000-5000", "5000"),
            SlotOption("5000-8000", "8000"),
            SlotOption("8000 以上", "20000"),
            SlotOption("不限", ANY),
        ],
    ),
    "bedrooms": SlotSpec(
        field="bedrooms",
        label="户型",
        question="想要什么户型？",
        options=[
            SlotOption("1 室", "1"),
            SlotOption("2 室", "2"),
            SlotOption("3 室", "3"),
            SlotOption("4 室及以上", "4"),
            SlotOption("不限", ANY),
        ],
    ),
    "property_type": SlotSpec(
        field="property_type",
        label="房源类型",
        question="偏好哪种类型？",
        options=[
            SlotOption("公寓", "apartment"),
            SlotOption("单间", "studio"),
            SlotOption("合租", "shared"),
            SlotOption("整租别墅", "house"),
            SlotOption("不限", ANY),
        ],
    ),
}

# 用户想跳过引导、直接看房源
SKIP_ELICIT_PATTERN = re.compile(
    r"直接推荐|直接看|随便看|先看看|不用问|别问了|快点|都行|随便|无所谓|你决定|看着办"
)

# 用户对当前问题回答"不限"
ANY_ANSWER_PATTERN = re.compile(r"^(不限|随便|都行|无所谓|没要求|都可以|跳过|skip)$")


def _clean(v: Any) -> Any:
    """把 LLM 可能返回的空串/"null"/"未提及" 统一成 None"""
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        if s == "" or s.lower() in ("null", "none", "未提及", "不确定", "未知"):
            return None
        return s
    return v


def normalize_slots(raw: dict[str, Any] | None) -> dict[str, Any]:
    """清洗槽位 dict：去掉空值，数字字段转 int"""
    if not raw:
        return {}
    out: dict[str, Any] = {}
    for key in ("district", "property_type"):
        v = _clean(raw.get(key))
        if v is not None:
            out[key] = v
    for key in ("price_min", "price_max", "bedrooms"):
        v = _clean(raw.get(key))
        if v is None:
            continue
        if v == ANY:
            out[key] = ANY
            continue
        try:
            out[key] = int(float(v))
        except (TypeError, ValueError):
            continue
    return out


def merge_slots(*layers: dict[str, Any] | None) -> dict[str, Any]:
    """按优先级合并槽位（后面的覆盖前面的），空值不覆盖已有值"""
    merged: dict[str, Any] = {}
    for layer in layers:
        for k, v in normalize_slots(layer).items():
            if v is not None:
                merged[k] = v
    return merged


def missing_slots(slots: dict[str, Any]) -> list[SlotSpec]:
    """找出所有还没回答的槽位（按 SLOT_ORDER 顺序），一次性摆成多组面板；都答了返回空列表"""
    return [SLOT_SPECS[field] for field in SLOT_ORDER if slots.get(field) is None]


def option_label(field: str | None, message: str) -> str | None:
    """
    用户点选项时前端回传的是 value（如 "3000"、"__any__"），直接存进对话里很难看。
    这里把 value 翻译回人话 label（"2000-3000"、"不限"），用于展示和历史回放；
    匹配不上（用户是自己打字的）返回 None，按原文存。
    """
    spec = SLOT_SPECS.get(field or "")
    if spec is None:
        return None
    text = message.strip()
    for opt in spec.options:
        if opt.value == text:
            return opt.label
    return None


def to_search_filters(slots: dict[str, Any]) -> dict[str, Any]:
    """把槽位转成 PropertyService.search 用的筛选条件（ANY 视为不限 → 不加条件）"""
    filters: dict[str, Any] = {}
    for key, value in slots.items():
        if value is None or value == ANY:
            continue
        filters[key] = value
    return filters


def describe_slots(slots: dict[str, Any]) -> str:
    """把已知条件拼成一句人话，用于追问时告诉用户「已经记下了什么」"""
    type_labels = {"apartment": "公寓", "house": "别墅", "studio": "单间", "shared": "合租"}
    parts: list[str] = []
    d = slots.get("district")
    if d and d != ANY:
        parts.append(str(d))
    pmax = slots.get("price_max")
    if pmax and pmax != ANY:
        parts.append(f"预算 {pmax} 以内")
    b = slots.get("bedrooms")
    if b and b != ANY:
        parts.append(f"{b} 室")
    t = slots.get("property_type")
    if t and t != ANY:
        parts.append(type_labels.get(str(t), str(t)))
    return "、".join(parts)


def multi_slot_payload(specs: list[SlotSpec], slots: dict[str, Any]) -> dict[str, Any]:
    """构造给前端的追问结构：把 specs 里所有缺失维度一次性摆成多组面板。

    前端渲染成每个维度一行 chips（可跨维度多选），配一个统一的「发送」按钮，
    而不是一个条件问完了才问下一个。
    """
    known = describe_slots(slots)
    prefix = f"已经记下：{known}。\n" if known else ""
    question = specs[0].question if len(specs) == 1 else "还差这几项，选一下吧（也可以直接跳过）："
    return {
        "reply": prefix + question,
        "elicit": {
            "groups": [
                {
                    "field": s.field,
                    "label": s.label,
                    "question": s.question,
                    "options": [{"label": o.label, "value": o.value} for o in s.options],
                }
                for s in specs
            ],
            "allow_custom": True,
        },
    }
