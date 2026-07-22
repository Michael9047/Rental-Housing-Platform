"""搜索 Agent —— 完整搜索管线（提取条件 → 检索+放宽 → 通勤过滤 → 评分 → LLM 推荐）

Phase 5: 从 AgentService 迁移全部搜索逻辑，独立于 AgentService。
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.institute import Institute, InstituteStatus
from app.models.property import Property, PropertyStatus
from app.services.agentic.agents.base_agent import BaseAgent
from app.services.agentic.orchestration.types import AgentContext, AgentResult, AgentError, AgentErrorType
from app.services.agentic.shared import property_to_dict
from app.services.llm_service import get_llm_service
from app.services.property_service import PropertyService
from app.services.safe_fallback import SafeFallback
from app.services.score_gap import detect_score_gap

logger = logging.getLogger(__name__)

AI_UNAVAILABLE_HINT = "（AI 分析暂不可用，已按筛选条件为您检索）"

# ── 配置常量 ────────────────────────────────────────────────────
RELAXATION_MIN_RESULTS = 5
RELAXATION_ORDER: list[dict] = [
    {"key": "district", "label": "区域"},
    {"key": "property_type", "label": "房源类型"},
    {"key": "bedrooms", "label": "户型"},
    {"key": "price_max", "label": "预算上限", "expand_factor": 1.2},
]
_COMMUTE_PRE_FILTER_KM: dict[str, float] = {
    "walking": 5.0, "bicycling": 10.0, "driving": 20.0, "transit": 15.0,
}
_COMMUTE_RELAX_MULTIPLIERS = (1, 2, 3, 4)
_EN_TO_CN_CITY: dict[str, str] = {
    "london": "伦敦", "hong kong": "香港", "hk": "香港",
    "singapore": "新加坡", "sg": "新加坡",
    "los angeles": "洛杉矶", "la": "洛杉矶",
    "san francisco": "旧金山", "sf": "旧金山",
}

# ── Prompts ──────────────────────────────────────────────────────

EXTRACT_FILTERS_PROMPT = """从用户消息中提取结构化的租房搜索条件。

══════════════════════════════
示例（Few-Shot）
══════════════════════════════

示例1：
用户：「园区2000以内带独卫的单间」
→ {"district":"园区","price_max":2000,"amenities":["独立卫浴"],"property_type":"studio","price_min":null,"bedrooms":null,"institution":null,"distance_km":3.0,"commute_mode":null,"commute_minutes":null,"room_type":null,"bathrooms":null,"area_min":null,"area_max":null,"min_lease_months":null}

示例2：
用户：「学校步行15分钟以内，预算2500，要独卫和阳台」
→ {"district":null,"price_max":2500,"amenities":["独立卫浴","阳台"],"institution":"悉尼大学","commute_mode":"walking","commute_minutes":15,"distance_km":5.0,"property_type":null,"bedrooms":null,"room_type":null,"bathrooms":null,"area_min":null,"area_max":null,"min_lease_months":null}

只输出 JSON。设施映射：独卫→独立卫浴, wifi→WiFi, 车位→车位, gym→健身房, 泳池→泳池, 养猫/狗→宠物友好, 做饭→独立厨房, 家具/拎包→家具齐全。
district 是行政区划。不确定时填 null。"""

RECOMMEND_SYSTEM_PROMPT = """你是面向留学生的海外租房推荐助手。系统已从数据库检索出候选房源（附真实数据）。挑选最匹配的 3 套，用口语化中文撰写推荐。

示例1 — 结果充足（≥5套）：
候选：学校周边 8 套，2000 以内单间
→ reply: 「学校周边 2000 以内的单间帮你筛出来了，一共 8 套，这 3 套最值得看：\n\n通勤首选 — 公寓A，单间 ¥1800/月，步行到校 10 分钟，独卫精装\n\n性价比 — 公寓B，单间 ¥1500/月，楼下就是商业街\n\n舒适型 — 公寓C，单间 ¥1950/月，面积大采光好\n\n有中意的加购物车，我帮你详细对比。」

示例2 — 无结果：
候选：0 套
→ reply: 「园区独卫单间目前在 1500 以内确实没有。建议：1）预算提到 1800 就有独卫单间了；2）考虑合租；3）换到吴中。你想试试哪个方向？」
→ recommendations: []

规则：只推荐候选列表里的 property_id，禁止编造。回复 150-250 字口语。价格用¥。

只输出 JSON：{"intent":"recommend","reply":"三段式口语推荐回复","recommendations":[{"property_id":1,"match_reason":"...","pros":["..."],"cons":["..."]}]}"""


# ── 确定性评分（模块级函数，SearchAgent + ToolRegistry 共用） ──

def score_properties(
    candidates: list[Property],
    filters: dict[str, Any],
    extracted: dict[str, Any],
) -> list[dict[str, Any]]:
    """对候选房源进行确定性质量评分，返回 top 3 附带亮点理由。"""
    if not candidates:
        return []

    price_min = filters.get("price_min") or extracted.get("price_min")
    price_max = filters.get("price_max") or extracted.get("price_max")

    prices = [float(p.price_monthly) for p in candidates]
    median_price = sorted(prices)[len(prices) // 2]

    target_price = median_price
    if price_min is not None and price_max is not None:
        target_price = (float(price_min) + float(price_max)) / 2
    elif price_min is not None:
        target_price = float(price_min) * 1.1
    elif price_max is not None:
        target_price = float(price_max) * 0.9

    price_range = max(prices) - min(prices) if len(prices) > 1 else max(prices) or 1

    scored: list[dict[str, Any]] = []
    for p in candidates:
        price_diff = abs(float(p.price_monthly) - target_price)
        price_score = max(0, 100 - (price_diff / max(price_range, 1)) * 100)
        area = float(p.area_sqm) if p.area_sqm else 0
        space_score = min(100, (min(area / max((p.bedrooms or 0) * 20 + 15, 1), 2.0)) * 60 + 20) if area > 0 else 60
        facility_score = 60
        if p.images and len(p.images) > 0:
            facility_score += 15
        if p.address:
            facility_score += 10
        if p.description and len(p.description) > 20:
            facility_score += 10
        facility_score = min(100, facility_score)
        total = price_score * 0.40 + space_score * 0.20 + facility_score * 0.20 + 60 * 0.20

        highlights: list[str] = []
        if price_score >= 80:
            highlights.append("租金贴合预算")
        elif price_score >= 60:
            highlights.append("价格在可接受范围")
        if area > 0 and space_score >= 75:
            highlights.append(f"{p.bedrooms or 0}室{p.bathrooms or 0}卫布局合理")
        if p.images and len(p.images) > 0:
            highlights.append("有实拍图片")
        if p.district:
            highlights.append(f"位于{p.district}")
        if not highlights:
            highlights.append("符合筛选条件")

        scored.append({"property": p, "score": round(total, 1), "highlights": highlights[:3]})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:3]


def _props_text(props: list[Property]) -> str:
    """将房源列表转为 LLM 可读的文本摘要。"""
    lines = []
    for i, p in enumerate(props, 1):
        d = property_to_dict(p)
        line = (
            f"{i}. [property_id={d['property_id']}] {d['title']} | 区域: {d['district']} | "
            f"月租: ¥{d['price_monthly']} | 户型: {d['bedrooms']}室{d['bathrooms']}卫 | "
            f"面积: {d['area_sqm'] or '未知'}㎡ | 简介: {d['description'] or '无'}"
        )
        commute_time = getattr(p, '_commute_time', None)
        if commute_time is not None:
            source_note = "（路线API实时计算）" if getattr(p, '_commute_source', None) == "api" else "（估算）"
            line += f" | 通勤: {commute_time}分钟{source_note}"
        lines.append(line)
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# SearchAgent
# ═══════════════════════════════════════════════════════════════════

class SearchAgent(BaseAgent):
    """房源搜索 Agent。完整管线：提取条件 → 检索+放宽 → 通勤过滤 → 评分 → LLM 推荐。

    替代 AgentService 中的 recommend_properties / _search_with_relaxation
    / _geo_search / _filter_by_commute / _lookup_institution。
    """

    name = "search_agent"
    description = "房源搜索 + 渐进放宽 + 通勤过滤 + 质量评分。独立于 AgentService。"
    tools = [
        "extract_filters", "property_search", "score_properties",
        "gap_detect", "safe_fallback_check", "query_rewrite",
        "poi_lookup", "commute_calc",
    ]

    def __init__(self, session: AsyncSession | None = None, tool_registry=None) -> None:
        super().__init__(tool_registry)
        self._session = session
        self._property_service: PropertyService | None = None
        self._safe_fallback = SafeFallback()

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("SearchAgent 未绑定 DB session")
        return self._session

    @property
    def property_service(self) -> PropertyService:
        if self._property_service is None:
            self._property_service = PropertyService(self.session)
        return self._property_service

    # ── 主入口 ────────────────────────────────────────────────────

    async def search(
        self, message: str, filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """检索 + LLM 推荐。逻辑与 AgentService.recommend_properties() 完全一致。"""
        filters = filters or {}
        llm = get_llm_service()

        # 1. LLM 提取结构化筛选条件
        extracted: dict[str, Any] = {}
        if llm.is_available:
            try:
                extracted = await llm.complete_json(EXTRACT_FILTERS_PROMPT, message, temperature=0.0, max_tokens=400)
                if not isinstance(extracted, dict):
                    extracted = {}
            except Exception:
                logger.debug("LLM 提取搜索条件失败")

        district = filters.get("district") or extracted.get("district") or None
        if district and district.lower().strip() in _EN_TO_CN_CITY:
            district = _EN_TO_CN_CITY[district.lower().strip()]
        price_min = filters.get("price_min") or extracted.get("price_min")
        price_max = filters.get("price_max") or extracted.get("price_max")
        bedrooms = filters.get("bedrooms") or extracted.get("bedrooms")
        property_type = filters.get("property_type") or extracted.get("property_type") or None

        # 硬约束字段合并
        amenities: list[str] | None = filters.get("amenities") or extracted.get("amenities") or None
        room_type: str | None = filters.get("room_type") or extracted.get("room_type") or None
        bathrooms: int | None = filters.get("bathrooms") or extracted.get("bathrooms") or None
        area_min: float | None = filters.get("area_min") or extracted.get("area_min") or None
        area_max: float | None = filters.get("area_max") or extracted.get("area_max") or None
        min_lease_months: int | None = filters.get("min_lease_months") or extracted.get("min_lease_months") or None
        max_lease_months: int | None = filters.get("max_lease_months") or extracted.get("max_lease_months") or None
        available_from: str | None = filters.get("available_from") or extracted.get("available_from") or None

        # 2. 学校/机构查找
        institution_name = filters.get("institution") or extracted.get("institution") or None
        distance_km = extracted.get("distance_km", 3.0)
        if not isinstance(distance_km, (int, float)) or distance_km < 0.5 or distance_km > 10.0:
            distance_km = 3.0
        institute_id: int | None = None

        commute_mode = extracted.get("commute_mode") or None
        commute_minutes = extracted.get("commute_minutes") or None
        if commute_minutes is not None:
            try:
                commute_minutes = int(commute_minutes)
            except (TypeError, ValueError):
                commute_minutes = None
        institute_info: dict[str, Any] | None = None

        if institution_name and not district:
            try:
                inst = await self._lookup_institution(institution_name)
                if inst:
                    institute_id = inst["id"]
                    institute_info = inst
                    if commute_mode and commute_mode in _COMMUTE_PRE_FILTER_KM:
                        distance_km = max(distance_km, _COMMUTE_PRE_FILTER_KM[commute_mode])
                    logger.info("机构匹配: %s → id=%s", institution_name, institute_id)
            except Exception:
                logger.exception("机构查找失败: %s", institution_name)

        query_parts = [message]
        if filters.get("country"):
            query_parts.append(str(filters["country"]))
        if institution_name and not institute_id:
            query_parts.append(institution_name)
        query_text = " ".join(p for p in query_parts if p)

        merged_filters = {
            "district": district, "price_min": price_min, "price_max": price_max,
            "bedrooms": bedrooms, "property_type": property_type,
            "institute_id": institute_id, "distance_km": distance_km,
            "amenities": amenities, "room_type": room_type,
            "bathrooms": bathrooms, "area_min": area_min, "area_max": area_max,
            "min_lease_months": min_lease_months, "max_lease_months": max_lease_months,
            "available_from": available_from,
        }

        # 3. 搜索
        if institute_id is not None:
            rows = await self._geo_search(institute_id, distance_km, merged_filters)
            relaxation_level = 0
            relaxed_fields: list[str] = []
        else:
            relax_result = await self._search_with_relaxation(query=query_text, filters=merged_filters)
            rows = relax_result["rows"]
            relaxation_level = relax_result["relaxation_level"]
            relaxed_fields = relax_result["relaxed_fields"]

        candidates = [prop for prop, _sim in rows]

        # 4. 通勤时间过滤
        if commute_mode and commute_minutes and institute_info:
            candidates = await self._filter_by_commute(
                origin_lat=institute_info["lat"], origin_lng=institute_info["lng"],
                candidates=candidates, mode=commute_mode, max_minutes=commute_minutes,
                country=institute_info.get("country"), city=institute_info.get("city_cn"),
            )

        # 5. 得分间隙检测
        scores = [float(sim) if sim is not None else 0.0 for _prop, sim in rows]
        score_gap = detect_score_gap(scores)

        # 6. 安全兜底
        if self._safe_fallback.should_fallback(documents=candidates, top_score=score_gap["top_score"], relaxation_level=relaxation_level):
            fallback_reply = self._safe_fallback.build_fallback_response(query=message, active_filters=merged_filters, relaxation_level=relaxation_level)
            return {
                "reply": fallback_reply, "recommendations": [], "ai_available": True,
                "extracted_filters": extracted, "top_picks": [],
                "score_gap": score_gap, "relaxation_level": relaxation_level, "source_info": "",
            }

        # 7. AI 精选 Top 3
        top_picks = score_properties(candidates, filters, extracted)
        top_picks_payload = [
            {"property_id": tp["property"].id, "match_reason": " · ".join(tp["highlights"]),
             "pros": tp["highlights"], "cons": [], "property": tp["property"]}
            for tp in top_picks
        ]

        all_recs = [
            {"property_id": p.id, "match_reason": "", "pros": [], "cons": [], "property": p}
            for p in candidates
        ]

        candidate_ids = [p.id for p in candidates]
        source_info = self._build_source_info(len(candidates), merged_filters, relaxation_level, relaxed_fields)

        # 8. LLM 生成回复
        if llm.is_available:
            try:
                top_props = [tp["property"] for tp in top_picks]
                user_prompt = (
                    f"用户需求：{message}\n"
                    f"检索结果：共 {len(candidates)} 套\n"
                    f"精选房源：\n{_props_text(top_props[:3])}"
                )
                result = await llm.complete_json(RECOMMEND_SYSTEM_PROMPT, user_prompt, max_tokens=800)
                reply = str(result.get("reply") or f"为您找到 {len(candidates)} 套符合需求的房源。") + source_info
            except Exception:
                logger.exception("LLM 推荐生成失败")
                reply = f"为您找到 {len(candidates)} 套符合需求的房源。{AI_UNAVAILABLE_HINT}{source_info}"
        else:
            reply = f"为您找到 {len(candidates)} 套符合需求的房源。{AI_UNAVAILABLE_HINT}{source_info}"

        return {
            "reply": reply, "recommendations": all_recs, "ai_available": llm.is_available,
            "extracted_filters": extracted, "top_picks": top_picks_payload,
            "score_gap": score_gap, "relaxation_level": relaxation_level,
            "candidate_snapshot": candidate_ids, "source_info": source_info,
        }

    # ── 检索+放宽 ─────────────────────────────────────────────────

    async def _search_with_relaxation(
        self, query: str | None, filters: dict[str, Any], limit: int = 500,
    ) -> dict[str, Any]:
        """渐进放宽检索条件。"""
        rows: list = []
        relaxation_level = 0
        relaxed_fields: list[str] = []

        has_structured = any(
            filters.get(k) is not None and filters.get(k) != ""
            for k in ("district", "price_min", "price_max", "bedrooms", "property_type", "institute_id")
        )
        effective_query = query if not has_structured else None

        search_kwargs = self._build_search_kwargs(filters, limit=limit)
        try:
            rows = await self.property_service.search(query=effective_query, **search_kwargs)
        except Exception:
            logger.warning("检索失败，降级为纯条件筛选", exc_info=True)
            rows = await self.property_service.search(query=None, **search_kwargs)

        if len(rows) >= RELAXATION_MIN_RESULTS:
            return {"rows": rows, "relaxation_level": 0, "relaxed_fields": []}

        # 地理半径优先放宽
        if filters.get("institute_id") and len(rows) < RELAXATION_MIN_RESULTS:
            current_dist = filters.get("distance_km", 3.0)
            for expand_km in (5.0, 10.0):
                if len(rows) >= RELAXATION_MIN_RESULTS:
                    break
                if current_dist < expand_km:
                    relaxed = dict(filters)
                    relaxed["distance_km"] = expand_km
                    relaxed_fields.append(f"搜索半径扩大到 {expand_km}km")
                    relaxation_level += 1
                    try:
                        rows = await self.property_service.search(query=None, **self._build_search_kwargs(relaxed, limit=limit))
                    except Exception:
                        pass
            if len(rows) >= RELAXATION_MIN_RESULTS:
                return {"rows": rows, "relaxation_level": relaxation_level, "relaxed_fields": relaxed_fields}

        # 逐级放宽
        relaxed = dict(filters)
        for relax_spec in RELAXATION_ORDER:
            if len(rows) >= RELAXATION_MIN_RESULTS:
                break
            key = relax_spec["key"]
            if key in relaxed:
                del relaxed[key]
                relaxed_fields.append(relax_spec["label"])
            elif key == "price_max" and relaxed.get("price_max") is not None:
                factor = relax_spec.get("expand_factor", 1.2)
                relaxed["price_max"] = int(float(relaxed["price_max"]) * factor)
                relaxed_fields.append(f"{relax_spec['label']} 扩大 {int((factor-1)*100)}%")
            relaxation_level += 1
            search_kwargs = self._build_search_kwargs(relaxed, limit=limit)
            has_any = any(relaxed.get(k) is not None and relaxed.get(k) != ""
                          for k in ("district", "price_min", "price_max", "bedrooms", "property_type", "institute_id"))
            relaxed_query = query if not has_any else None
            try:
                rows = await self.property_service.search(query=relaxed_query, **search_kwargs)
            except Exception:
                rows = await self.property_service.search(query=None, **search_kwargs)

        # 最终回退：英文关键词裸搜
        if len(rows) == 0 and query:
            import re as _re
            tokens = _re.findall(r'[A-Za-z0-9]+', query)
            acronyms = _re.findall(r'\b[A-Z]{2,5}\b', query)
            all_tokens = list(dict.fromkeys(acronyms + tokens))
            if all_tokens:
                short_query = ' '.join(all_tokens[:3])
                relaxation_level += 1
                relaxed_fields.append("关键词回退搜索")
                try:
                    keyword_rows = await self.property_service.search(query=short_query, limit=limit)
                    rows = [(prop, 0.5) for prop, _ in keyword_rows] if keyword_rows else []
                except Exception:
                    pass

        return {"rows": rows, "relaxation_level": relaxation_level, "relaxed_fields": relaxed_fields}

    # ── 地理搜索 ──────────────────────────────────────────────────

    async def _geo_search(
        self, institute_id: int, distance_km: float, base_kwargs: dict[str, Any]
    ) -> list[tuple[Property, float | None]]:
        """Haversine 精筛。"""
        from app.services.geo_utils import hav_distance

        inst = await self.session.get(Institute, institute_id)
        if not inst or inst.latitude is None or inst.longitude is None:
            return []

        search_kwargs = dict(base_kwargs)
        search_kwargs.pop("district", None)
        search_kwargs["limit"] = search_kwargs.get("limit", 500) * 3
        rows = await self.property_service.search(query=None, **search_kwargs)

        inst_lat, inst_lng = float(inst.latitude), float(inst.longitude)
        results: list[tuple[Property, float]] = []
        for prop, _sim in rows:
            if prop.latitude is None or prop.longitude is None:
                continue
            dist = hav_distance(inst_lat, inst_lng, float(prop.latitude), float(prop.longitude))
            if dist <= distance_km:
                results.append((prop, dist))

        results.sort(key=lambda x: x[1])
        return [(p, d) for p, d in results[:500]]

    # ── 通勤过滤 ──────────────────────────────────────────────────

    async def _filter_by_commute(
        self, origin_lat: float, origin_lng: float,
        candidates: list[Property], mode: str, max_minutes: int,
        country: str | None = None, city: str | None = None,
    ) -> list[Property]:
        """路线 API 通勤过滤（多引擎降级）。"""
        from app.services.commute_service import CommuteDestination, calculate_commute_batch_resilient

        destinations = [
            CommuteDestination(dest_id=p.id, lat=float(p.latitude), lng=float(p.longitude))
            for p in candidates
            if p.latitude is not None and p.longitude is not None
        ]
        if not destinations:
            return candidates

        batch_result = await calculate_commute_batch_resilient(
            origin_lat, origin_lng, destinations, country=country, city=city,
        )

        result_by_id: dict[int | str, Any] = {}
        for r in batch_result.results:
            result_by_id[r.dest_id] = r

        mode_key = {"walking": "walk_min", "bicycling": "bike_min",
                     "driving": "drive_min", "transit": "transit_min"}[mode]

        for relax_minutes in (max_minutes, max_minutes * 2, max_minutes * 3, max_minutes * 4):
            passed: list[Property] = []
            for p in candidates:
                if p.id not in result_by_id:
                    continue
                r = result_by_id[p.id]
                if getattr(r, mode_key, 999) <= relax_minutes:
                    object.__setattr__(p, '_commute_time', getattr(r, mode_key))
                    object.__setattr__(p, '_commute_source', r.source)
                    passed.append(p)
            if len(passed) >= 5 or relax_minutes >= max_minutes * 4:
                passed.sort(key=lambda x: getattr(x, '_commute_time', 999))
                return passed

        for p in candidates:
            if p.id in result_by_id:
                r = result_by_id[p.id]
                object.__setattr__(p, '_commute_time', getattr(r, mode_key, 999))
                object.__setattr__(p, '_commute_source', r.source)
        candidates.sort(key=lambda x: getattr(x, '_commute_time', 999))
        return candidates

    # ── 辅助方法 ──────────────────────────────────────────────────

    async def _lookup_institution(self, name: str) -> dict[str, Any] | None:
        """模糊查找学校/机构 → {id, name, lat, lng}。"""
        if not name or not name.strip():
            return None
        name = name.strip()

        # 精确 abbreviation
        stmt = select(Institute).where(
            func.lower(Institute.abbreviation) == name.lower(),
            Institute.status == InstituteStatus.active,
        )
        result = await self.session.scalars(stmt)
        inst = result.first()
        if inst and inst.latitude is not None and inst.longitude is not None:
            return {"id": inst.id, "name": inst.name, "lat": float(inst.latitude), "lng": float(inst.longitude)}

        # ILIKE name
        pattern = f"%{name}%"
        stmt = select(Institute).where(
            func.lower(Institute.name).ilike(pattern), Institute.status == InstituteStatus.active,
        )
        result = await self.session.scalars(stmt)
        inst = result.first()
        if inst and inst.latitude is not None and inst.longitude is not None:
            return {"id": inst.id, "name": inst.name, "lat": float(inst.latitude), "lng": float(inst.longitude)}

        # ILIKE abbreviation
        stmt = select(Institute).where(
            func.lower(Institute.abbreviation).ilike(pattern), Institute.status == InstituteStatus.active,
        )
        result = await self.session.scalars(stmt)
        inst = result.first()
        if inst and inst.latitude is not None and inst.longitude is not None:
            return {"id": inst.id, "name": inst.name, "lat": float(inst.latitude), "lng": float(inst.longitude)}

        return None

    @staticmethod
    def _build_search_kwargs(filters: dict, limit: int = 500) -> dict[str, Any]:
        """将 Agent filters 转为 PropertyService.search() 参数。"""
        kwargs: dict[str, Any] = {
            "price_min": Decimal(str(filters["price_min"])) if filters.get("price_min") is not None else None,
            "price_max": Decimal(str(filters["price_max"])) if filters.get("price_max") is not None else None,
            "bedrooms": filters.get("bedrooms"),
            "property_type": filters.get("property_type"),
            "status": PropertyStatus.available.value,
            "limit": limit,
        }
        district = filters.get("district")
        if district:
            kwargs["district"] = district
        institute_id = filters.get("institute_id")
        if institute_id:
            kwargs["institute_id"] = institute_id
            kwargs["distance_km"] = filters.get("distance_km", 3.0)
        amenities = filters.get("amenities")
        if amenities and isinstance(amenities, list) and len(amenities) > 0:
            kwargs["amenities"] = amenities
        for k in ("room_type", "bathrooms", "area_min", "area_max", "min_lease_months", "max_lease_months", "available_from"):
            v = filters.get(k)
            if v is not None and v != "":
                kwargs[k] = float(v) if k in ("area_min", "area_max") else (int(v) if k in ("bathrooms", "min_lease_months", "max_lease_months") else str(v))
        return kwargs

    @staticmethod
    def _build_source_info(result_count: int, filters: dict[str, Any], relaxation_level: int, relaxed_fields: list[str]) -> str:
        """生成检索溯源信息。"""
        parts = [f"\n\n---\n[检索] 本次基于 {result_count} 套房源检索"]
        filter_parts = []
        for key, label in {"district": "区域", "price_min": "最低预算", "price_max": "最高预算",
                            "bedrooms": "户型", "property_type": "类型"}.items():
            val = filters.get(key)
            if val is not None and val != "":
                if key in ("price_min", "price_max"):
                    val = f"¥{int(val):,}"
                elif key == "property_type":
                    val = {"apartment": "公寓", "house": "别墅", "studio": "单间", "shared": "合租"}.get(str(val), str(val))
                filter_parts.append(f"{label}: {val}")
        if filter_parts:
            parts.append("条件: " + " | ".join(filter_parts))
        if relaxation_level > 0 and relaxed_fields:
            parts.append(f"已放宽: {' → '.join(relaxed_fields)}")
        return "\n".join(parts)

    @staticmethod
    def validate_recommendations(recommendations: list[dict], candidate_snapshot: list[int]) -> tuple[list[dict], int]:
        """校验 LLM 推荐：所有房源必须在候选快照中。"""
        valid: list[dict] = []
        dropped = 0
        snapshot_set = set(candidate_snapshot) if candidate_snapshot else set()
        for rec in recommendations:
            if rec.get("property_id") in snapshot_set:
                valid.append(rec)
            else:
                logger.warning("一致性校验：LLM 编造了不在候选快照中的房源 property_id=%s", rec.get("property_id"))
                dropped += 1
        return valid, dropped

    # ── ReAct Tool Loop 模式（复杂查询：通勤/POI/模糊条件） ────

    SEARCH_REACT_PROMPT = """你是面向留学生的海外租房搜索专家。按需使用工具，不要全部调用。

可用工具：
- extract_filters: 从自然语言提取筛选条件（district/price/bedrooms/amenities）
- property_search: 搜索房源（支持 query + 结构化条件，自动渐进放宽）
- score_properties: 对搜索结果质量评分（传入 candidate_ids）
- gap_detect: 检测分数断层
- safe_fallback_check: 检查检索质量
- query_rewrite: 改写模糊查询为精确条件
- poi_lookup: 查询房源周边设施（超市/地铁/餐厅）
- commute_calc: 计算通勤时间

流程建议（不要死板遵循，按实际情况灵活调整）：
1. extract_filters → 提取条件
2. property_search → 搜索（可同时传 query 和 filters）
3. 如果用户提到通勤 → commute_calc
4. 如果用户问周边 → poi_lookup
5. score_properties → 评分
6. 用中文输出推荐回复（先总结数量，再逐套介绍亮点）

关键规则：
- 最多调用 4 个工具，之后必须输出中文回复
- 只推荐真实房源，不编造
- 结果少时诚实告知+给放宽建议
- 口语化中文，像朋友在给建议"""

    async def search_react(self, message: str, filters: dict[str, Any] | None = None) -> AgentResult:
        """ReAct Tool Loop 搜索：LLM 自主决定工具调用顺序。

        适用场景：涉及通勤计算、POI 查询、条件模糊需要改写等复杂查询。
        简单条件查询仍走 search() 快速路径。
        """
        return await self.handle_with_react(
            context=AgentContext(
                user_message=message,
                filters=filters,
            ),
            system_prompt=self.SEARCH_REACT_PROMPT,
            max_iterations=5,
        )

    # ── Agent 接口 ────────────────────────────────────────────────

    async def handle(self, context: AgentContext) -> AgentResult:
        """搜索入口：根据查询复杂度自动选择快速路径或 ReAct 模式。

        简单条件（district + price）→ search() 快速管线
        复杂条件（含通勤/POI/模糊查询）→ search_react() Tool Loop
        """
        try:
            msg = context.user_message.lower()
            is_complex = any(kw in msg for kw in [
                "通勤", "多远", "多久", "地铁站", "公交", "走路", "骑车", "开车",
                "附近有", "周边", "超市", "餐馆", "健身房",
                "便宜点", "贵一点", "少一点", "多一点",
            ])

            if is_complex:
                react_result = await self.search_react(
                    message=context.user_message,
                    filters=context.filters,
                )
                return react_result

            result = await self.search(
                message=context.user_message,
                filters=context.filters,
            )
            return AgentResult(
                content=result.get("reply", ""),
                success=True,
                data=result,
            )
        except Exception as exc:
            logger.exception("SearchAgent 失败")
            return AgentResult(
                content="",
                success=False,
                error=AgentError(
                    type_=AgentErrorType.EXTERNAL_API_FAILURE,
                    message=str(exc),
                    agent_id="search_agent",
                ),
            )
