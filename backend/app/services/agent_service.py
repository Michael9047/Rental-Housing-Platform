"""租房推荐 Agent 服务 —— 意图解析、房源推荐、购物车管理、房源对比

复用 PropertyService.search 做检索，复用 chat_sessions/chat_messages 存对话，
LLM 仅基于数据库中的真实房源数据生成推荐理由和对比分析；
LLM 不可用时降级为普通筛选 + 规则化对比。
"""
from __future__ import annotations

import logging
import re
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_cart import AgentCart, AgentCartItem
from app.models.chat import ChatMessage, ChatMessageRole, ChatSession
from app.models.poi import PropertyPOI
from app.models.property import Property, PropertyStatus
from app.models.review import Review, ReviewStatus
from app.services.agent_faq import (
    FaqEntry,
    faq_kb_text,
    get_faq,
    is_bare_topic,
    match_faq,
)
from app.services.agent_slots import (
    ANY,
    ANY_ANSWER_PATTERN,
    SKIP_ELICIT_PATTERN,
    SLOT_ORDER,
    merge_slots,
    missing_slots,
    multi_slot_payload,
    normalize_slots,
    option_label,
    to_search_filters,
)
from app.services.compare_scoring import (
    DIMENSION_LABELS,
    PRIORITY_LABELS,
    PropertyMetrics,
    compute_scores,
    format_commute,
    nearest_transit_meters,
    normalize_priority,
)
from app.services.llm_service import get_llm_service
from app.services.property_service import PropertyService

logger = logging.getLogger(__name__)

AI_UNAVAILABLE_HINT = "（AI 分析暂不可用，已按筛选条件为您检索）"

# 新建会话的占位标题；收到第一条用户消息后会被自动替换成消息摘要
DEFAULT_SESSION_TITLE = "新对话"

# ── 意图解析提示词 ─────────────────────────────────────────────────

INTENT_SYSTEM_PROMPT = """你是租房平台的智能助手。判断用户这句话的意图，只输出 JSON：

{
  "intent": "recommend | add_to_cart | remove_from_cart | compare_cart | faq | general 之一",
  "refs": [用户提到的序号列表，如"第一个"是 1，"前两个"是 1 和 2，没提到则为空数组],
  "faq_id": "仅当 intent 为 faq 时给出：find_house | booking | contract | deposit | refund | fees 之一",
  "faq_confidence": "仅当 intent 为 faq 时给出：high 或 low"
}

意图说明：
- recommend：用户在描述租房需求，希望推荐房源
- add_to_cart：用户想把某个/某些房源加入购物车或候选清单
- remove_from_cart：用户想从购物车/清单移除房源
- compare_cart：用户想对比购物车/清单中的房源
- faq：用户在问平台使用/政策类问题（find_house 如何找房 / booking 预订流程 /
  contract 合同签署 / deposit 押金退还 / refund 退款政策 / fees 费用构成）。
  很确定属于其中一类填 high；只是可能相关、拿不准填 low。
- general：与上述都无关的普通咨询

只输出 JSON。"""

RECOMMEND_SYSTEM_PROMPT = """你是租房平台的智能推荐助手。系统已经根据用户条件从数据库检索出候选房源（附真实数据）。你的任务是从中挑选最匹配用户需求的房源（最多 5 套）并给出推荐理由。

严格规则：
1. 只能推荐候选列表里出现的 property_id，禁止编造房源、价格、地址、设施。
2. 推荐理由、优缺点必须基于给出的真实字段（价格、区域、户型、面积、描述）。
3. match_reason **禁止**写成"预算符合、区域匹配"这种照抄筛选条件的空话——用户自己填的条件他当然知道符合。
   要点出候选数据里具体的信息：面积数字、楼层、描述里提到的地铁站/学校/商圈名字、装修或设施关键词等，
   让用户一眼看出"这套房子哪里好"，而不是"这套房子符合我填的条件"。
4. 如果候选列表为空或都不合适，recommendations 返回空数组，并在 reply 中建议用户放宽条件。

只输出 JSON，格式：
{
  "intent": "recommend",
  "reply": "给用户的自然语言回复",
  "recommendations": [
    {
      "property_id": 1,
      "match_reason": "45㎡南向一居室，步行5分钟到地铁2号线，独立厨房适合自己开火",
      "pros": ["价格低", "面积适中"],
      "cons": ["距离市中心较远"]
    }
  ]
}"""

COMPARE_SYSTEM_PROMPT = """你是租房平台的智能对比助手。系统已经按用户选择的优先级，用数据库真实数据（价格、面积、最近交通站点距离、机构真实评价）计算好每套房源的综合得分和分项得分。你的任务是**解释和分析**，不是打分。

严格规则：
1. 只能基于给出的真实字段分析，禁止编造价格、距离、设施、评价。
2. items 必须覆盖给出的每一套房源，property_id 不得超出给定列表。
3. score 必须原样使用系统计算的综合得分，禁止修改或自创。
4. pros/cons 结合价格、通勤（最近交通站点距离）、面积、评价与描述来写，和分项得分保持一致。
5. recommendation 要呼应用户的优先级（如预算优先/通勤优先）。

只输出 JSON，格式：
{
  "summary": "综合对比结论，一两句话",
  "items": [
    {
      "property_id": 1,
      "pros": ["价格最低", "步行3分钟到地铁"],
      "cons": ["面积较小"],
      "score": 86,
      "best_for": "预算有限、单人居住"
    }
  ],
  "recommendation": "按您的优先级推荐房源 1，因为..."
}"""

GENERAL_SYSTEM_PROMPT = """你是一个专业的租房顾问助手，用中文简洁友好地回答用户的租房相关咨询。
不要编造任何不存在的房源信息；如果用户想找房，引导他描述地区、预算、户型等需求。"""

SLOT_EXTRACT_SYSTEM_PROMPT = """你是租房平台的需求解析器。从用户这句话里抽取租房条件，只输出 JSON：

{
  "district": "城市或区域名，如「苏州工业园区」「上海」。没提到填 null",
  "price_max": 预算上限（整数，单位元/月）。没提到填 null,
  "price_min": 预算下限（整数）。没提到填 null,
  "bedrooms": 卧室数量（整数）。没提到填 null,
  "property_type": "apartment(公寓) | studio(单间) | shared(合租) | house(别墅) 之一。没提到填 null"
}

规则：
- 只抽取用户**明确说了**的条件，没说的一律 null，禁止臆测。
- 「3000 以内」「预算 3000」→ price_max=3000。「3000 到 5000」→ price_min=3000, price_max=5000。
- 「一居室」「单间」既可能是户型也可能是类型：一居室 → bedrooms=1；「单间」→ property_type=studio。
- 如果用户对某个条件明确表示「不限/随便/都行」，该字段填字符串 "__any__"。

只输出 JSON。"""

FAQ_ANSWER_SYSTEM_PROMPT = """你是租房平台里一位经验丰富的租房顾问，正在跟用户对话。下面给你一段【平台知识库】内容，
以及用户的问题，请像一个真的懂行、替用户着想的人那样自然作答，而不是照本宣科念规章制度。

语气要求（重要）：
- 不要用"您好""关于XX，"这类客服模板开场白，直接切入用户想知道的点。
- 优先用陈述句、口语化的自然段落组织答案；只有在确实是"按顺序操作的步骤"时才用编号列表，
  不要把本来是几句话就能说清楚的内容硬拆成 1. 2. 3.。
- 可以有一点人情味和态度（比如提醒用户注意什么、什么情况下要多留意），不要冷冰冰罗列条款。
- 别啰嗦，能一两句话讲清楚的不要展开成一大段。

严格规则（事实层面，不能因为追求语气而破坏）：
1. 只能使用知识库里出现的事实。**禁止编造**退款时限、金额、比例、扣费标准等任何知识库没写的具体规则。
2. 如果用户问的细节知识库没覆盖，就如实说明"这一点以合同条款/平台最新规则为准，可联系客服确认"，不要猜。
3. 知识库开头如果有"占位说明"之类的免责声明，请保留这层意思（说明以正式规则和合同为准）。
4. 用中文。不要输出 JSON，直接输出给用户看的正文。
5. 聊天气泡支持渲染 **加粗**，只用来强调真正关键的结论或数字，不要整句整段加粗；
   不支持 # 标题和 - 列表符号，需要列表时用"1. 2. 3."。"""

# 聊天气泡渲染 **加粗**，但不支持标题/无序列表符号，这里把这两种转成纯文本安全形式
# （标题去掉井号，列表符号统一成"· "），加粗标记保留给前端渲染。
_MD_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*", re.M)
_MD_BULLET = re.compile(r"^\s{0,3}[-*+]\s+", re.M)


def _strip_markdown(text: str) -> str:
    """去掉聊天气泡不支持的 Markdown 标记（标题/无序列表符号），保留 **加粗**。"""
    text = _MD_HEADING.sub("", text)
    text = _MD_BULLET.sub("· ", text)
    return text


def _linkify_properties(text: str, recs: list[dict[str, Any]]) -> str:
    """把回复文本里出现的房源标题包成 `[标题](property:id)` 内联链接。

    只链接本轮真实推荐列表里的房源（id 有保证，不会链到不存在的房源）；
    按标题长度从长到短匹配，避免短标题恰好是长标题子串时抢先命中。
    房源标题通常是"核心地段+户型 补充卖点"（如"星湖街地铁口一居室 智能门锁"），
    LLM 转述时常常只说核心部分、不带后面的卖点，所以完整标题匹配不上时
    再退一步试标题里第一个空格前的部分。
    """
    ordered = sorted(recs, key=lambda r: -len(r["property"].title or ""))
    linked: set[int] = set()
    for r in ordered:
        title = r["property"].title or ""
        pid = r["property_id"]
        if not title or pid in linked:
            continue
        core = title.split(" ", 1)[0]
        for candidate in (title, core):
            if len(candidate) < 2:
                continue
            idx = text.find(candidate)
            if idx == -1:
                continue
            text = f"{text[:idx]}[{candidate}](property:{pid}){text[idx + len(candidate):]}"
            linked.add(pid)
            break
    return text


# ── 中文序号解析 ──────────────────────────────────────────────────

_CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

_ADD_PATTERN = re.compile(r"(加入|加到|添加|放进|放入|收藏|加购)")
_REMOVE_PATTERN = re.compile(r"(移除|删除|去掉|拿掉|清除)")
_COMPARE_PATTERN = re.compile(r"(对比|比较|哪个好|哪套好|哪一?[个套]更)")
_CART_PATTERN = re.compile(r"(购物车|候选|清单|收藏)")
# 找房信号词：命中即直接走 recommend，跳过 LLM 意图分类（省一次串行调用，显著降低延迟）
_RECOMMEND_SIGNAL = re.compile(
    r"找|推荐|租|房源|房子|居室|单间|公寓|合租|别墅|预算|地铁|学校|大学|附近|[0-9一二两三四五]\s*室|元|块|㎡|平米|平方"
)


def _parse_refs(message: str) -> list[int]:
    """从消息中提取序号引用，如 '第一个'、'第2套' → [1] / [2]"""
    refs: list[int] = []
    for m in re.finditer(r"第\s*(\d+|[一二两三四五六七八九十])\s*[个套条]?", message):
        token = m.group(1)
        num = int(token) if token.isdigit() else _CN_NUM.get(token, 0)
        if num > 0:
            refs.append(num)
    if re.search(r"(前两[个套]|前2[个套])", message):
        refs.extend([1, 2])
    if re.search(r"(全部|都加|所有)", message):
        refs.append(-1)  # -1 表示全部
    return list(dict.fromkeys(refs))


def _parse_property_ids(message: str) -> list[int]:
    """提取显式房源 ID 引用，如 '房源 12'"""
    return [int(m.group(1)) for m in re.finditer(r"房源\s*(\d+)", message)]


def _heuristic_intent(message: str) -> str:
    """无需 LLM 的规则意图判断"""
    if _COMPARE_PATTERN.search(message):
        return "compare_cart"
    if _ADD_PATTERN.search(message) and (_CART_PATTERN.search(message) or _parse_refs(message) or _parse_property_ids(message)):
        return "add_to_cart"
    if _REMOVE_PATTERN.search(message) and (_CART_PATTERN.search(message) or _parse_refs(message) or _parse_property_ids(message)):
        return "remove_from_cart"
    return "recommend"


def _property_to_dict(prop: Property) -> dict[str, Any]:
    """将 Property ORM 转为 LLM 上下文用的 dict（仅真实字段）"""
    return {
        "property_id": prop.id,
        "title": prop.title,
        "district": prop.district,
        "address": prop.address,
        "price_monthly": float(prop.price_monthly),
        "area_sqm": float(prop.area_sqm) if prop.area_sqm else None,
        "bedrooms": prop.bedrooms,
        "bathrooms": prop.bathrooms,
        "property_type": prop.property_type.value if hasattr(prop.property_type, "value") else str(prop.property_type),
        "description": (prop.description or "")[:200],
    }


def _props_text(props: list[Property]) -> str:
    lines = []
    for i, p in enumerate(props, 1):
        d = _property_to_dict(p)
        lines.append(
            f"{i}. [property_id={d['property_id']}] {d['title']} | 区域: {d['district']} | 地址: {d['address']} | "
            f"月租: ¥{d['price_monthly']} | 户型: {d['bedrooms']}室{d['bathrooms']}卫 | "
            f"面积: {d['area_sqm'] or '未知'}㎡ | 类型: {d['property_type']} | 简介: {d['description'] or '无'}"
        )
    return "\n".join(lines)


class AgentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.property_service = PropertyService(session)

    # ── 购物车 ────────────────────────────────────────────────────

    async def get_or_create_cart(self, user_id: int) -> AgentCart:
        stmt = (
            select(AgentCart)
            .where(AgentCart.user_id == user_id)
            .order_by(AgentCart.created_at.desc())
        )
        cart = (await self.session.scalars(stmt)).first()
        if cart is None:
            cart = AgentCart(user_id=user_id)
            self.session.add(cart)
            await self.session.commit()
            await self.session.refresh(cart)
        return cart

    async def add_to_cart(
        self, user_id: int, property_id: int, reason: str | None = None
    ) -> AgentCartItem:
        """加入购物车；重复添加返回已有项"""
        prop = await self.session.get(Property, property_id)
        if prop is None:
            raise ValueError("房源不存在")

        cart = await self.get_or_create_cart(user_id)
        stmt = select(AgentCartItem).where(
            AgentCartItem.cart_id == cart.id,
            AgentCartItem.property_id == property_id,
        )
        existing = (await self.session.scalars(stmt)).first()
        if existing is not None:
            return existing

        item = AgentCartItem(cart_id=cart.id, property_id=property_id, reason=reason)
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def remove_from_cart(self, user_id: int, property_id: int) -> bool:
        cart = await self.get_or_create_cart(user_id)
        stmt = select(AgentCartItem).where(
            AgentCartItem.cart_id == cart.id,
            AgentCartItem.property_id == property_id,
        )
        item = (await self.session.scalars(stmt)).first()
        if item is None:
            return False
        await self.session.delete(item)
        await self.session.commit()
        return True

    async def get_cart_items(self, user_id: int) -> tuple[AgentCart, list[AgentCartItem]]:
        cart = await self.get_or_create_cart(user_id)
        stmt = (
            select(AgentCartItem)
            .where(AgentCartItem.cart_id == cart.id)
            .order_by(AgentCartItem.created_at.asc())
        )
        items = list(await self.session.scalars(stmt))
        return cart, items

    # ── 意图解析 ──────────────────────────────────────────────────

    async def parse_user_intent(
        self, message: str, history: list[dict] | None = None
    ) -> dict[str, Any]:
        """判断用户意图；LLM 可用时用 LLM，否则用规则"""
        llm = get_llm_service()
        if llm.is_available:
            try:
                result = await llm.complete_json(
                    INTENT_SYSTEM_PROMPT,
                    message,
                    temperature=0.0,
                    max_tokens=200,
                )
                intent = result.get("intent")
                if intent == "faq" and get_faq(str(result.get("faq_id", ""))) is not None:
                    return {
                        "intent": "faq",
                        "refs": [],
                        "faq_id": str(result["faq_id"]),
                        "faq_confidence": "high" if result.get("faq_confidence") == "high" else "low",
                    }
                if intent in ("recommend", "add_to_cart", "remove_from_cart", "compare_cart", "general"):
                    refs = [r for r in result.get("refs", []) if isinstance(r, int)]
                    # 规则解析结果做兜底合并
                    refs = refs or _parse_refs(message)
                    return {"intent": intent, "refs": refs}
            except Exception:
                logger.exception("LLM 意图解析失败，降级为规则判断")
        return {"intent": _heuristic_intent(message), "refs": _parse_refs(message)}

    # ── 推荐 ──────────────────────────────────────────────────────

    async def recommend_properties(
        self, message: str, filters: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """检索 + LLM 推荐。返回 {reply, recommendations: [{property_id, match_reason, pros, cons, property}], ai_available}"""
        filters = filters or {}

        district = filters.get("district") or None
        price_min = filters.get("price_min")
        price_max = filters.get("price_max")
        bedrooms = filters.get("bedrooms")
        property_type = filters.get("property_type") or None

        # country 不是数据库字段，并入语义检索文本
        query_parts = [message]
        if filters.get("country"):
            query_parts.append(str(filters["country"]))
        query_text = " ".join(p for p in query_parts if p)

        search_kwargs: dict[str, Any] = {
            "district": district,
            "price_min": Decimal(str(price_min)) if price_min is not None else None,
            "price_max": Decimal(str(price_max)) if price_max is not None else None,
            "bedrooms": bedrooms,
            "property_type": property_type,
            "status": PropertyStatus.available.value,
            "limit": 10,
        }

        # 优先语义检索；embedding 服务不可用时降级为纯筛选
        try:
            rows = await self.property_service.search(query=query_text, **search_kwargs)
        except Exception:
            logger.warning("语义检索不可用，降级为条件筛选", exc_info=True)
            rows = await self.property_service.search(query=None, **search_kwargs)

        candidates = [prop for prop, _sim in rows]

        if not candidates:
            return {
                "reply": "抱歉，没有找到符合条件的房源。建议放宽预算、扩大区域范围或调整户型要求再试试。",
                "recommendations": [],
                "ai_available": True,
            }

        by_id = {p.id: p for p in candidates}
        llm = get_llm_service()

        if llm.is_available:
            try:
                user_prompt = (
                    f"用户需求：{message}\n"
                    f"筛选条件：{filters}\n\n"
                    f"候选房源（数据库真实数据）：\n{_props_text(candidates)}"
                )
                result = await llm.complete_json(RECOMMEND_SYSTEM_PROMPT, user_prompt)
                recs = []
                for rec in result.get("recommendations", []):
                    pid = rec.get("property_id")
                    if pid not in by_id:
                        continue  # 丢弃 LLM 编造的 id
                    recs.append({
                        "property_id": pid,
                        "match_reason": str(rec.get("match_reason", "")),
                        "pros": [str(x) for x in rec.get("pros", [])],
                        "cons": [str(x) for x in rec.get("cons", [])],
                        "property": by_id[pid],
                    })
                if recs:
                    shown = recs[:5]
                    reply_text = str(result.get("reply") or f"为您找到 {len(shown)} 套符合需求的房源。")
                    return {
                        "reply": _linkify_properties(reply_text, shown),
                        "recommendations": shown,
                        "ai_available": True,
                    }
            except Exception:
                logger.exception("LLM 推荐生成失败，降级为普通筛选结果")

        # 降级：直接返回检索结果前 5 条
        top = candidates[:5]
        return {
            "reply": f"根据您的筛选条件，为您找到 {len(candidates)} 套房源，以下是前 {len(top)} 套。{AI_UNAVAILABLE_HINT}",
            "recommendations": [
                {
                    "property_id": p.id,
                    "match_reason": "符合您设置的筛选条件",
                    "pros": [],
                    "cons": [],
                    "property": p,
                }
                for p in top
            ],
            "ai_available": False,
        }

    # ── 对比 ──────────────────────────────────────────────────────

    async def compare_cart(
        self,
        user_id: int,
        property_ids: list[int] | None = None,
        priority: str | None = None,
    ) -> dict[str, Any]:
        """对比房源。

        - 传入 property_ids 时：只对比这些房源（可来自推荐横条或购物车，不要求已加购）。
        - 未传时：对比整个购物车（兼容旧行为，自然语言「对比一下」也走这里）。
        - priority：用户优先级（balanced/budget/commute/space），决定加权评分的权重。
        购物车为空或所选房源无效时抛 ValueError。
        """
        if property_ids:
            props: list[Property] = []
            for pid in dict.fromkeys(property_ids):  # 去重保序
                prop = await self.session.get(Property, pid)
                if prop is not None:
                    props.append(prop)
            if len(props) < 2:
                raise ValueError("请至少选择 2 套有效房源进行对比")
            return await self._compare_props(props, priority)

        _cart, items = await self.get_cart_items(user_id)
        if not items:
            raise ValueError("购物车为空，请先添加房源再对比")

        props = []
        for item in items:
            prop = await self.session.get(Property, item.property_id)
            if prop is not None:
                props.append(prop)
        if not props:
            raise ValueError("购物车中的房源已不存在")

        return await self._compare_props(props, priority)

    async def _gather_compare_metrics(
        self, props: list[Property]
    ) -> tuple[list[PropertyMetrics], dict[int, dict]]:
        """为对比补充真实数据：POI 通勤距离 + 机构评价聚合。

        返回 (metrics 列表, {property_id: 展示用附加信息})
        """
        ids = [p.id for p in props]

        pois: dict[int, PropertyPOI] = {}
        try:
            rows = await self.session.scalars(
                select(PropertyPOI).where(PropertyPOI.property_id.in_(ids))
            )
            pois = {poi.property_id: poi for poi in rows}
        except Exception:
            logger.exception("加载 POI 数据失败，通勤维度取中性分")

        rating_by_inst: dict[int, tuple[float, int]] = {}
        inst_ids = {p.institute_id for p in props if p.institute_id}
        if inst_ids:
            try:
                rows = await self.session.execute(
                    select(
                        Review.institute_id,
                        func.avg(Review.rating),
                        func.count(Review.id),
                    )
                    .where(
                        Review.institute_id.in_(inst_ids),
                        Review.status == ReviewStatus.approved,
                    )
                    .group_by(Review.institute_id)
                )
                rating_by_inst = {r[0]: (float(r[1]), int(r[2])) for r in rows}
            except Exception:
                logger.exception("加载评价聚合失败，评分维度取中性分")

        metrics: list[PropertyMetrics] = []
        extras: dict[int, dict] = {}
        for p in props:
            poi = pois.get(p.id)
            transit = nearest_transit_meters(poi.poi_data if poi else None)
            rating, count = (None, 0)
            if p.institute_id and p.institute_id in rating_by_inst:
                rating, count = rating_by_inst[p.institute_id]
            metrics.append(
                PropertyMetrics(
                    property_id=p.id,
                    price=float(p.price_monthly),
                    area=float(p.area_sqm) if p.area_sqm else None,
                    transit_meters=transit,
                    rating=rating,
                    review_count=count,
                )
            )
            extras[p.id] = {
                "commute": format_commute(transit),
                "rating": round(rating, 1) if rating is not None else None,
                "review_count": count,
            }
        return metrics, extras

    async def _compare_props(
        self, props: list[Property], priority: str | None = None
    ) -> dict[str, Any]:
        """对一组房源做对比。

        评分与解释分离：先用真实数据（价格/面积/POI 通勤/机构评价）按用户优先级
        算出确定性加权得分；LLM 只负责解释优劣势，分数不允许它改。LLM 不可用时
        用规则模板生成解释，分数完全一致。
        """
        by_id = {p.id: p for p in props}
        pr = normalize_priority(priority)
        metrics, extras = await self._gather_compare_metrics(props)
        scores = compute_scores(metrics, pr)

        def _base_item(pid: int) -> dict[str, Any]:
            return {
                "property_id": pid,
                "title": by_id[pid].title,
                "score": scores[pid]["total"],
                "score_breakdown": scores[pid]["breakdown"],
                "commute": extras[pid]["commute"],
                "rating": extras[pid]["rating"],
                "review_count": extras[pid]["review_count"],
                "property": by_id[pid],
            }

        llm = get_llm_service()
        if llm.is_available:
            try:
                lines = []
                for i, p in enumerate(props, 1):
                    d = _property_to_dict(p)
                    e = extras[p.id]
                    s = scores[p.id]
                    lines.append(
                        f"{i}. [property_id={d['property_id']}] {d['title']} | 区域: {d['district']} | "
                        f"月租: ¥{d['price_monthly']} | 户型: {d['bedrooms']}室{d['bathrooms']}卫 | "
                        f"面积: {d['area_sqm'] or '未知'}㎡ | 通勤: {e['commute'] or '无数据'} | "
                        f"评价: {(str(e['rating']) + '分/' + str(e['review_count']) + '条') if e['rating'] is not None else '暂无'} | "
                        f"简介: {d['description'] or '无'}\n"
                        f"   系统得分（禁止修改）: 综合 {s['total']} | "
                        + " ".join(f"{DIMENSION_LABELS[k]} {v}" for k, v in s["breakdown"].items())
                    )
                user_prompt = (
                    f"用户优先级：{PRIORITY_LABELS[pr]}\n\n"
                    f"待对比房源（数据库真实数据 + 系统计算得分）：\n" + "\n".join(lines)
                )
                result = await llm.complete_json(COMPARE_SYSTEM_PROMPT, user_prompt, max_tokens=2000)

                parsed: dict[int, dict] = {}
                for it in result.get("items", []):
                    pid = it.get("property_id")
                    if pid in by_id:
                        parsed[pid] = it

                items_out = []
                for p in props:
                    item = _base_item(p.id)
                    it = parsed.get(p.id, {})
                    item["pros"] = [str(x) for x in it.get("pros", [])] or ["条件均衡"]
                    item["cons"] = [str(x) for x in it.get("cons", [])]
                    item["best_for"] = str(it.get("best_for", ""))
                    items_out.append(item)

                if parsed:
                    return {
                        "summary": str(result.get("summary", "")),
                        "items": items_out,
                        "recommendation": str(result.get("recommendation", "")),
                        "ai_available": True,
                        "priority": pr,
                    }
            except Exception:
                logger.exception("LLM 对比解释生成失败，降级为规则解释（得分不变）")

        return self._rule_based_compare(props, scores, extras, pr)

    def _rule_based_compare(
        self,
        props: list[Property],
        scores: dict[int, dict],
        extras: dict[int, dict],
        priority: str,
    ) -> dict[str, Any]:
        """LLM 不可用时的规则解释：得分同一套加权公式，优劣势按分项名次生成"""
        by_id = {p.id: p for p in props}

        # 各维度冠军（得分并列都算）
        best: dict[str, int] = {}
        for dim in DIMENSION_LABELS:
            best[dim] = max(scores[p.id]["breakdown"][dim] for p in props)

        dim_pros = {
            "price": "价格最有优势",
            "commute": "通勤最便利",
            "space": "空间最宽敞",
            "rating": "评价最好",
        }

        items_out = []
        for p in props:
            b = scores[p.id]["breakdown"]
            pros = [
                text for dim, text in dim_pros.items()
                if b[dim] == best[dim] and b[dim] > 60 and len(props) > 1
            ]
            cons = []
            if b["price"] <= 45:
                cons.append("价格偏高")
            if b["space"] <= 45:
                cons.append("面积偏小")
            if extras[p.id]["commute"] is None:
                cons.append("暂无通勤数据")
            if not pros:
                pros.append("条件均衡")

            top_dim = max(b, key=lambda k: b[k])
            item = {
                "property_id": p.id,
                "title": p.title,
                "pros": pros,
                "cons": cons,
                "score": scores[p.id]["total"],
                "score_breakdown": b,
                "best_for": f"{DIMENSION_LABELS[top_dim]}优先",
                "commute": extras[p.id]["commute"],
                "rating": extras[p.id]["rating"],
                "review_count": extras[p.id]["review_count"],
                "property": by_id[p.id],
            }
            items_out.append(item)

        prices = [float(p.price_monthly) for p in props]
        winner = max(props, key=lambda p: scores[p.id]["total"])
        return {
            "summary": (
                f"按「{PRIORITY_LABELS[priority]}」共对比 {len(props)} 套房源，"
                f"价格区间 ¥{min(prices):.0f} - ¥{max(prices):.0f}。{AI_UNAVAILABLE_HINT}"
            ),
            "items": items_out,
            "recommendation": (
                f"按「{PRIORITY_LABELS[priority]}」综合得分最高的是"
                f"「{winner.title}」（{scores[winner.id]['total']} 分）。"
            ),
            "ai_available": False,
            "priority": priority,
        }

    # ── 会话消息主流程 ────────────────────────────────────────────

    async def _last_recommendations(self, session_id: int) -> list[dict]:
        """取会话中最近一条带推荐列表的 assistant 消息 metadata"""
        stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.role == ChatMessageRole.assistant,
            )
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(20)
        )
        for msg in await self.session.scalars(stmt):
            meta = msg.metadata_ or {}
            recs = meta.get("recommendations")
            if recs:
                return recs
        return []

    async def _history(self, session_id: int, limit: int = 10) -> list[dict]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(limit)
        )
        msgs = list(await self.session.scalars(stmt))
        return [
            {"role": m.role.value, "content": m.content}
            for m in reversed(msgs)
            if m.role in (ChatMessageRole.user, ChatMessageRole.assistant)
        ]

    # ── 多会话管理 ────────────────────────────────────────────────

    async def list_sessions(self, user_id: int) -> list[ChatSession]:
        """列出该用户的所有 AI 管家会话（最近活跃的在前）"""
        stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id, ChatSession.kind == "agent")
            .order_by(ChatSession.updated_at.desc())
        )
        return list(await self.session.scalars(stmt))

    async def get_session(self, session_id: int, user_id: int) -> ChatSession | None:
        stmt = select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
            ChatSession.kind == "agent",
        )
        return (await self.session.scalars(stmt)).first()

    async def delete_session(self, session_id: int, user_id: int) -> bool:
        chat_session = await self.get_session(session_id, user_id)
        if chat_session is None:
            return False
        await self.session.delete(chat_session)
        await self.session.commit()
        return True

    async def get_session_messages(self, session_id: int) -> list[dict[str, Any]]:
        """回放一段会话：把历史消息还原成前端能直接渲染的结构。

        推荐卡在 metadata 里只存了 property_id + match_reason（省空间），这里按 id
        把真实房源查回来，让历史里的横滑卡片能照常显示；已删除的房源自动跳过。
        """
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        msgs = list(await self.session.scalars(stmt))

        # 一次性把所有引用到的房源查出来，避免逐条 N+1
        all_ids: set[int] = set()
        for m in msgs:
            for rec in (m.metadata_ or {}).get("recommendations") or []:
                if isinstance(rec.get("property_id"), int):
                    all_ids.add(rec["property_id"])
        props: dict[int, Property] = {}
        if all_ids:
            rows = await self.session.scalars(
                select(Property).where(Property.id.in_(all_ids))
            )
            props = {p.id: p for p in rows}

        out: list[dict[str, Any]] = []
        for m in msgs:
            meta = m.metadata_ or {}
            recs = []
            for rec in meta.get("recommendations") or []:
                prop = props.get(rec.get("property_id"))
                if prop is None:
                    continue  # 房源已下架/删除
                recs.append(
                    {
                        "property_id": prop.id,
                        "match_reason": rec.get("match_reason", ""),
                        "pros": [],
                        "cons": [],
                        "property": prop,
                    }
                )
            out.append(
                {
                    "id": m.id,
                    "role": m.role.value,
                    "content": m.content,
                    "recommendations": recs,
                    "elicit": meta.get("elicit"),
                    "feedback": meta.get("feedback"),
                    "intent": meta.get("intent"),
                    "created_at": m.created_at,
                }
            )
        return out

    # ── 引导式追问：槽位 ──────────────────────────────────────────

    async def _last_slot_state(
        self, session_id: int
    ) -> tuple[dict[str, Any], list[str], str | None]:
        """取会话中最近一次记录的引导状态。

        返回 (已收集的槽位, 上一轮正在追问的字段列表, 最初那句需求描述)
        """
        stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.role == ChatMessageRole.assistant,
            )
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(10)
        )
        for msg in await self.session.scalars(stmt):
            meta = msg.metadata_ or {}
            if "slots" in meta:
                # 兼容旧数据：改造前存的是单个 pending_field 字符串
                pending_fields = meta.get("pending_fields")
                if pending_fields is None:
                    legacy = meta.get("pending_field")
                    pending_fields = [legacy] if legacy else []
                return (
                    normalize_slots(meta.get("slots")),
                    pending_fields,
                    meta.get("seed_query"),
                )
        return {}, [], None

    async def _extract_slots(self, message: str) -> dict[str, Any]:
        """用 LLM 从用户消息里抽取租房条件；LLM 不可用时返回空（靠前端筛选栏兜底）"""
        llm = get_llm_service()
        if not llm.is_available:
            return {}
        try:
            result = await llm.complete_json(
                SLOT_EXTRACT_SYSTEM_PROMPT,
                message,
                temperature=0.0,
                max_tokens=200,
            )
            return normalize_slots(result)
        except Exception:
            logger.exception("LLM 槽位抽取失败")
            return {}

    @staticmethod
    def _answer_pending_slots(message: str, pending_fields: list[str]) -> dict[str, Any]:
        """把用户对上一轮追问面板的直接回答落到对应槽位。

        面板多选的正常提交走 `filters`（前端把每个维度选的 value 精确打包），
        这里只处理两种不需要 LLM 的快路径：
        - 说"不限/随便"→ 面板里所有缺失维度都记成 ANY
        - 只剩一个维度在追问时，用户直接打字（数字/类型码/地名）→ 按单维度规则解析

        剩下的情况（多个维度都缺、用户又是打字而不是走面板）留给 LLM 抽取，
        避免"3000"这种数字被同时错误塞进价格和户型两个维度。
        """
        if not pending_fields:
            return {}
        text = message.strip()
        if ANY_ANSWER_PATTERN.match(text) or text == ANY:
            return {field: ANY for field in pending_fields}
        if len(pending_fields) != 1:
            return {}
        field = pending_fields[0]
        if field in ("price_max", "bedrooms"):
            # 允许用户直接打数字（"3000"、"2"），或带单位（"3000元"）
            m = re.fullmatch(r"\s*(\d+)\s*(元|块|室|间)?\s*", text)
            if m:
                return {field: int(m.group(1))}
        if field == "property_type" and text in ("apartment", "studio", "shared", "house"):
            return {field: text}
        if field == "district" and len(text) <= 20:
            # 区域是自由文本，短回答直接当答案（但别把整句需求当成区域）
            if not _RECOMMEND_SIGNAL.search(text) or re.fullmatch(r"[一-龥A-Za-z·\s]+", text):
                return {field: text}
        return {}

    def _resolve_refs(
        self, refs: list[int], explicit_ids: list[int], last_recs: list[dict]
    ) -> list[int]:
        """把序号引用解析成 property_id 列表"""
        ids = list(explicit_ids)
        rec_ids = [r.get("property_id") for r in last_recs if r.get("property_id")]
        if -1 in refs:  # 全部
            ids.extend(rec_ids)
        else:
            for ref in refs:
                if 1 <= ref <= len(rec_ids):
                    ids.append(rec_ids[ref - 1])
        return list(dict.fromkeys(ids))

    @staticmethod
    def _faq_answer(entry: FaqEntry) -> dict[str, Any]:
        """FAQ 强命中：返回占位政策答案 + 页面深链 + 后续建议 chips"""
        return {
            "reply": entry.answer,
            "quick_replies": list(entry.next_chips),
            "links": [{"label": link.label, "to": link.to} for link in entry.links],
            "faq_id": entry.id,
        }

    @staticmethod
    def _faq_confirm(hits: list[FaqEntry]) -> dict[str, Any]:
        """仅用于「孤立主题词」（用户光打了个"押金"）：问清他到底想了解什么。

        注意：只要用户问的是一个完整的问题（带疑问词/动词），就不该走这里，
        而应该由 _faq_answer_llm 基于知识库直接作答。
        """
        if len(hits) == 1:
            reply = f"你是想了解「{hits[0].chip}」吗？点下面的按钮，或者直接把问题说完整些。"
        else:
            names = "、".join(f"「{e.chip}」" for e in hits)
            reply = f"你想了解的是 {names} 中的哪一个？点下面的按钮选择，或把问题说得具体些。"
        return {
            "reply": reply,
            "quick_replies": [e.chip for e in hits],
            "links": [],
            "faq_id": None,
        }

    async def _faq_answer_llm(
        self, entry: FaqEntry, message: str, history: list[dict] | None = None
    ) -> dict[str, Any]:
        """FAQ 由 LLM 基于知识库内容组织回答，贴合用户实际问法。

        知识库是唯一事实来源（禁止编造政策细节）；LLM 只负责"怎么说"。
        LLM 不可用/失败时退回原样输出知识库全文，保证永远有答案。
        """
        llm = get_llm_service()
        if llm.is_available:
            try:
                msgs = [{"role": "system", "content": FAQ_ANSWER_SYSTEM_PROMPT}]
                for h in (history or [])[-4:]:
                    msgs.append(h)
                msgs.append(
                    {
                        "role": "user",
                        "content": (
                            f"【平台知识库】\n{faq_kb_text(entry)}\n\n"
                            f"【用户的问题】\n{message}\n\n"
                            "请针对用户的问题作答。"
                        ),
                    }
                )
                reply = _strip_markdown((await llm.complete_text(msgs, temperature=0.3)).strip())
                if reply:
                    return {
                        "reply": reply,
                        "quick_replies": list(entry.next_chips),
                        "links": [{"label": link.label, "to": link.to} for link in entry.links],
                        "faq_id": entry.id,
                    }
            except Exception:
                logger.exception("LLM 组织 FAQ 答案失败，退回知识库原文")

        return self._faq_answer(entry)

    async def handle_message(
        self,
        chat_session: ChatSession,
        user_id: int,
        message: str,
        filters: dict[str, Any] | None = None,
        slot_answers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Agent 消息主入口：意图识别 → 分发处理 → 持久化对话"""
        history = await self._history(chat_session.id)
        explicit_ids = _parse_property_ids(message)

        recommendations: list[dict] = []
        cart_changed = False
        ai_available = True
        quick_replies: list[str] = []
        links: list[dict] = []
        faq_id: str | None = None
        elicit: dict[str, Any] | None = None

        # 上一轮的引导状态（正在追问哪些字段、已经收集到什么条件）
        prior_slots, pending_fields, seed_query = await self._last_slot_state(chat_session.id)
        # 上一轮问的是哪些槽位（pending_fields 下面会被本轮改写，先留一份用于回显 label）
        prior_pending_fields = pending_fields
        answered = self._answer_pending_slots(message, pending_fields)
        # 面板提交：slot_answers 里带了任意一个正在追问的字段，就算这轮在回答面板
        panel_answered = bool(slot_answers) and any(f in slot_answers for f in pending_fields)
        slots: dict[str, Any] = dict(prior_slots)

        # ── 意图路由 ───────────────────────────────────────────────
        # 分层原则：
        #   1. 点 chip / 明确问法（强正则）→ 直接给知识库答案，零成本零误判
        #   2. 孤立主题词（光打个"押金"）→ 反问确认
        #   3. 正在引导追问，且这条像是在回答 → 继续找房流程
        #   4. 明确的操作类（加购/移除/对比）→ 正则可靠，跳过 LLM 省一次调用
        #   5. 纯找房需求（有找房信号且完全没有 FAQ 主题词）→ 找房
        #   6. 其余一律交 LLM 判断（含"定房子要哪些费用"这种带房源词的 FAQ 问题）
        #      命中 FAQ → 让 LLM 基于知识库组织答案，而不是机械反问
        faq_payload: dict[str, Any] | None = None
        strength, faq_hits = match_faq(message)
        heuristic = _heuristic_intent(message)

        if strength == "strong":
            # 强命中（多为点 chip 触发）也交给 LLM 组织语言，不直接甩知识库原文——
            # 原文是照顾"标准答案"写的模板句式，读起来像客服话术；
            # LLM 不可用/失败时 _faq_answer_llm 内部会自动退回原文，不会没有答案。
            intent, refs = "faq", []
            faq_payload = await self._faq_answer_llm(faq_hits[0], message, history)

        elif strength == "weak" and is_bare_topic(message):
            # 孤立主题词，问不出具体想知道什么 → 反问
            intent, refs = "faq", []
            faq_payload = self._faq_confirm(faq_hits)

        elif pending_fields and (answered or panel_answered or SKIP_ELICIT_PATTERN.search(message)):
            # 用户在回答我们上一轮的追问面板（勾了选项一次性发送 / 打了数字 / 说"不限"/"直接推荐"）
            intent, refs = "recommend", []

        elif heuristic in ("add_to_cart", "remove_from_cart", "compare_cart"):
            intent, refs = heuristic, _parse_refs(message)

        elif strength == "none" and _RECOMMEND_SIGNAL.search(message):
            # 注意必须要求 strength == "none"：否则"定房子要哪些费用"会因为含"房子"
            # 被误判成找房需求
            intent, refs = "recommend", _parse_refs(message)

        else:
            parsed = await self.parse_user_intent(message, history)
            intent = parsed["intent"]
            refs = parsed["refs"]
            if intent == "faq":
                entry = get_faq(parsed.get("faq_id") or "")
                if entry is None:
                    intent = "general"  # LLM 给了未知 id → 兜底为普通咨询
                else:
                    # 不管置信度高低，只要能对上某个 FAQ 主题，就让 LLM 基于知识库
                    # 正面回答用户的问题（知识库是唯一事实来源，禁止编造）
                    faq_payload = await self._faq_answer_llm(entry, message, history)
            elif intent == "general" and strength == "weak":
                # LLM 觉得是闲聊，但消息里确实有 FAQ 主题词 → 按最相关的 FAQ 作答，
                # 总比给一句无用的客套话强
                intent = "faq"
                faq_payload = await self._faq_answer_llm(faq_hits[0], message, history)

        if intent == "faq" and faq_payload is not None:
            reply = faq_payload["reply"]
            quick_replies = faq_payload["quick_replies"]
            links = faq_payload["links"]
            faq_id = faq_payload["faq_id"]

        elif intent == "recommend":
            # 循循善诱：把「上一轮已收集的条件 + 前端筛选栏 + 追问面板提交 + 本句抽取到的
            # + 对追问的纯文本回答」合并起来，缺的维度一次性摆成多组面板，已知的绝不重复问。
            # 面板提交（slot_answers 已经精确带上答案）或纯文本快路径命中时，跳过 LLM 抽取；
            # 否则才交给 LLM 从自然语言里抽条件（省一次调用）。
            extracted = (
                {} if (answered or panel_answered) else await self._extract_slots(message)
            )
            slots = merge_slots(prior_slots, filters, slot_answers, extracted, answered)

            # 用户明确不想被追问 → 剩下的全部按「不限」处理，直接给结果
            if SKIP_ELICIT_PATTERN.search(message):
                for field in SLOT_ORDER:
                    slots.setdefault(field, ANY)

            # 语义检索用的原始需求描述：沿用最初那句，避免把"3000"这种回答当查询词
            if not seed_query and not answered and not panel_answered:
                seed_query = message

            missing = missing_slots(slots)
            if missing:
                intent = "elicit"
                payload = multi_slot_payload(missing, slots)
                reply = payload["reply"]
                elicit = payload["elicit"]
                pending_fields = [s.field for s in missing]
            else:
                pending_fields = []
                query = seed_query or message
                result = await self.recommend_properties(query, to_search_filters(slots))
                reply = result["reply"]
                recommendations = result["recommendations"]
                ai_available = result["ai_available"]

        elif intent == "add_to_cart":
            last_recs = await self._last_recommendations(chat_session.id)
            target_ids = self._resolve_refs(refs, explicit_ids, last_recs)
            if not target_ids and len(last_recs) == 1:
                target_ids = [last_recs[0]["property_id"]]
            if not target_ids:
                reply = "请告诉我要加入哪套房源，比如「把第一个加入购物车」。"
            else:
                added_titles = []
                reason_by_id = {
                    r["property_id"]: r.get("match_reason") for r in last_recs
                }
                for pid in target_ids:
                    try:
                        await self.add_to_cart(user_id, pid, reason_by_id.get(pid))
                        prop = await self.session.get(Property, pid)
                        added_titles.append(prop.title if prop else f"房源 {pid}")
                        cart_changed = True
                    except ValueError:
                        continue
                if added_titles:
                    reply = f"已将「{'」「'.join(added_titles)}」加入候选清单。需要继续找房还是对比一下？"
                else:
                    reply = "没有找到对应的房源，请确认序号或房源编号。"

        elif intent == "remove_from_cart":
            _cart, items = await self.get_cart_items(user_id)
            cart_ids = [it.property_id for it in items]
            target_ids = list(explicit_ids)
            if -1 in refs:
                target_ids.extend(cart_ids)
            else:
                for ref in refs:
                    if 1 <= ref <= len(cart_ids):
                        target_ids.append(cart_ids[ref - 1])
            target_ids = list(dict.fromkeys(target_ids))
            if not target_ids:
                reply = "请告诉我要移除哪套房源，比如「把第一个从清单里移除」。"
            else:
                removed = 0
                for pid in target_ids:
                    if await self.remove_from_cart(user_id, pid):
                        removed += 1
                        cart_changed = True
                reply = f"已从候选清单移除 {removed} 套房源。" if removed else "候选清单中没有找到对应的房源。"

        elif intent == "compare_cart":
            try:
                compare = await self.compare_cart(user_id)
                ai_available = compare["ai_available"]
                lines = [compare["summary"]]
                for it in compare["items"]:
                    lines.append(
                        f"「{it['title']}」推荐指数 {it['score']}：优势 {'、'.join(it['pros']) or '—'}；"
                        f"劣势 {'、'.join(it['cons']) or '—'}"
                        + (f"；适合{it['best_for']}" if it.get("best_for") else "")
                    )
                lines.append(compare["recommendation"])
                reply = "\n".join(x for x in lines if x)
            except ValueError as e:
                reply = str(e)

        else:  # general
            llm = get_llm_service()
            if llm.is_available:
                try:
                    msgs = [{"role": "system", "content": GENERAL_SYSTEM_PROMPT}]
                    msgs.extend(history)
                    msgs.append({"role": "user", "content": message})
                    reply = await llm.complete_text(msgs)
                except Exception:
                    logger.exception("LLM 普通咨询回复失败")
                    reply = "我是租房推荐助手，可以告诉我您想找的地区、预算和户型，我来帮您推荐房源。"
            else:
                reply = "我是租房推荐助手，可以告诉我您想找的地区、预算和户型，我来帮您推荐房源。"
                ai_available = False

        # 只剩一个维度追问、用户直接打字回答时，可能打的是原始 value（"3000"/"__any__"），
        # 翻成人话再展示；多维度面板提交时前端已经构造好人话文案，这里不用再翻译
        display_message = message
        if len(prior_pending_fields) == 1:
            display_message = option_label(prior_pending_fields[0], message) or message

        # 会话标题：用第一条用户消息自动命名（方便左侧会话列表辨认）
        if not chat_session.title or chat_session.title == DEFAULT_SESSION_TITLE:
            chat_session.title = display_message.strip()[:30] or DEFAULT_SESSION_TITLE

        # 持久化对话
        # - recommendations 存 metadata，供后续"把第一个加入购物车"引用、以及历史回放
        # - slots/pending_fields/seed_query 存引导状态，下一轮接着问
        user_msg = ChatMessage(
            session_id=chat_session.id,
            role=ChatMessageRole.user,
            content=display_message,
            metadata_={"filters": filters or {}},
        )
        assistant_meta: dict[str, Any] = {
            "intent": intent,
            "faq_id": faq_id,
            "recommendations": [
                {
                    "property_id": r["property_id"],
                    "match_reason": r.get("match_reason", ""),
                }
                for r in recommendations
            ],
        }
        if intent in ("recommend", "elicit"):
            assistant_meta["slots"] = slots
            assistant_meta["pending_fields"] = pending_fields
            assistant_meta["seed_query"] = seed_query
            if elicit is not None:
                assistant_meta["elicit"] = elicit

        assistant_msg = ChatMessage(
            session_id=chat_session.id,
            role=ChatMessageRole.assistant,
            content=reply,
            metadata_=assistant_meta,
        )
        self.session.add_all([user_msg, assistant_msg])
        await self.session.commit()

        return {
            "message_id": assistant_msg.id,
            "reply": reply,
            "intent": intent,
            "recommendations": recommendations,
            "cart_changed": cart_changed,
            "ai_available": ai_available,
            "quick_replies": quick_replies,
            "links": links,
            "elicit": elicit,
        }

    async def set_message_feedback(
        self, user_id: int, message_id: int, feedback: str | None
    ) -> bool:
        """记录用户对某条 AI 回复的点赞/点踩；feedback 传 None 表示取消。

        校验消息属于该用户自己的 Agent 会话，避免跨用户读写他人对话。
        """
        stmt = (
            select(ChatMessage)
            .join(ChatSession, ChatMessage.session_id == ChatSession.id)
            .where(
                ChatMessage.id == message_id,
                ChatMessage.role == ChatMessageRole.assistant,
                ChatSession.user_id == user_id,
                ChatSession.kind == "agent",
            )
        )
        msg = await self.session.scalar(stmt)
        if msg is None:
            return False
        # JSON 字段要整体重新赋值才能让 SQLAlchemy 感知到变化
        msg.metadata_ = {**(msg.metadata_ or {}), "feedback": feedback}
        await self.session.commit()
        return True
