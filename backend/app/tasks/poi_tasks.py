# POI 预生成 Celery 任务
# 房源创建/更新时异步触发 Google Maps 全量 POI 检索并存入 PropertyPOI
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.celery_app import celery_app
from app.core.config import get_settings
from app.models.poi import PropertyPOI
from app.models.property import Property
from app.services.google_poi_service import GooglePOIService

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# 新任务：Google Maps 全量 POI 检索（16 关键词 / 3 路径）
# ═══════════════════════════════════════════════════════

@celery_app.task(
    name="generate_full_poi_for_property",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def generate_full_poi_for_property(property_id: int) -> None:
    """Google Maps 全量 POI 检索——16 关键词，searchText 网格 + searchNearby"""

    import asyncio

    async def _run() -> None:
        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        async with async_session() as session:
            prop = await session.get(Property, property_id)
            if not prop:
                logger.warning("Full POI task: property %s not found", property_id)
                return

            lat = float(prop.latitude) if prop.latitude else None
            lng = float(prop.longitude) if prop.longitude else None
            if lat is None or lng is None:
                logger.warning("Full POI task: property %s missing coordinates", property_id)
                return

            poi_service = GooglePOIService()
            try:
                result_map = await poi_service.search_all(lat, lng, radius_m=2000)
                # 后处理：去重 + keyword 回填
                raw_map: dict[str, list] = {}
                for kw, pois in result_map.items():
                    raw_map[kw] = [p for p in pois]  # 此时是 dict

                # 重建 POIItem 列表以应用去重
                from app.services.google_poi_service import POIItem as PItem
                item_map: dict[str, list[PItem]] = {}
                for kw, pois in result_map.items():
                    item_map[kw] = [PItem(**p) for p in pois]

                item_map = poi_service.apply_all_dedup(item_map)
                await poi_service.close()

                # 组装 map_poi_data（前端地图卡片格式）
                map_categories: dict[str, list[dict]] = {}
                for kw in KW_ORDER:
                    if kw in item_map and item_map[kw]:
                        items = []
                        for p in item_map[kw]:
                            items.append({
                                "id": p.place_id or p.name,
                                "name": p.name,
                                "lat": p.lat,
                                "lng": p.lng,
                                "distance": p.distance_m,
                                "line": [ln.get("ref", "") for ln in p.transit_lines] if p.transit_lines else [],
                            })
                        if items:
                            # kw → 母类
                            parent = next((cat for cat, kws in (
                                ("交通", ["地铁站", "公交站"]),
                                ("医疗", ["医院", "药店"]),
                                ("购物", ["超市", "便利店", "商场", "酒吧"]),
                                ("美食", ["餐厅", "cafe", "烘焙", "快餐", "食阁"]),
                                ("生活", ["市场", "健身房"]),
                                ("地标", ["小贩中心"]),
                            ) if kw in kws), "其他")
                            map_categories.setdefault(parent, []).extend(items)

                map_poi_data = {
                    "search_radius_m": 2000,
                    "categories": map_categories,
                }

                # 组装 poi_data（分析面板结构化数据）
                poi_data: dict[str, list[dict]] = {}
                for cat, kws in (
                    ("交通", ["地铁站", "公交站"]),
                    ("医疗", ["医院", "药店"]),
                    ("教育", []),
                    ("购物", ["超市", "便利店", "商场", "酒吧"]),
                    ("餐饮", ["餐厅", "cafe", "烘焙", "快餐", "食阁"]),
                    ("生活", ["市场", "健身房"]),
                ):
                    cat_items = []
                    for kw in kws:
                        if kw in item_map:
                            for p in item_map[kw][:5]:  # 每关键词 top 5
                                cat_items.append({
                                    "name": p.name,
                                    "distance": f"{p.distance_m}m",
                                    "keyword": kw,
                                    "rating": p.rating,
                                })
                    if cat_items:
                        poi_data[cat] = sorted(cat_items, key=lambda x: int(x["distance"].rstrip("m")))

                # 组装 content 文本摘要
                address_parts = [p for p in [prop.address, prop.district] if p]
                base = address_parts[0] if address_parts else "该房源"
                lines = [f"该房源位于{base}，周边配套设施如下："]
                for cat, items in poi_data.items():
                    if items:
                        names = "、".join(i["name"] for i in items[:3])
                        lines.append(f"{cat}：{names}等{len(items)}项")
                content = "\n".join(lines) if len(lines) > 1 else f"该房源位于{base}，周边配套设施较少。"

                # ── 安全评分 ──
                safety_data = None
                try:
                    from app.services.safety_scoring import SafetyScoringService
                    safety_svc = SafetyScoringService()
                    country = (prop.country or "").upper()
                    if country in ("SG", "GB", "UK"):
                        result = await safety_svc.score_single(
                            property_id,
                            lat=lat, lng=lng,
                            country=country,
                        )
                        safety_data = result.to_dict()
                        logger.info("Safety score for property %s: %.0f (source: %s)",
                                    property_id, result.score, result.data_source)
                except Exception:
                    logger.exception("Safety scoring failed for property %s", property_id)

                # Upsert PropertyPOI
                from sqlalchemy import select as sa_select
                result = await session.execute(
                    sa_select(PropertyPOI).where(PropertyPOI.property_id == property_id)
                )
                poi_record = result.scalar_one_or_none()
                if poi_record:
                    poi_record.content = content
                    poi_record.poi_data = poi_data
                    poi_record.map_poi_data = map_poi_data
                    poi_record.safety_data = safety_data
                    poi_record.generated_at = datetime.now(timezone.utc)
                else:
                    poi_record = PropertyPOI(
                        property_id=property_id,
                        content=content,
                        poi_data=poi_data,
                        map_poi_data=map_poi_data,
                        safety_data=safety_data,
                        generated_at=datetime.now(timezone.utc),
                        reviewed=False,
                    )
                    session.add(poi_record)

                await session.commit()
                total = sum(len(v) for v in item_map.values())
                logger.info("Full POI generated for property %s: %d POIs across %d keywords",
                            property_id, total, len(item_map))

            except Exception:
                logger.exception("Full POI task failed for property %s", property_id)
                await poi_service.close()

        await engine.dispose()

    asyncio.run(_run())


# ═══════════════════════════════════════════════════════
# 旧任务（保留向后兼容）
# ═══════════════════════════════════════════════════════


@celery_app.task(
    name="generate_map_pois_for_property",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def generate_map_pois_for_property(property_id: int) -> None:
    """异步生成房源地图 POI 数据，存入 PropertyPOI.map_poi_data"""

    import asyncio

    async def _run() -> None:
        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        async with async_session() as session:
            prop = await session.get(Property, property_id)
            if not prop:
                logger.warning("Map POI task: property %s not found", property_id)
                return

            poi_service = GooglePOIService()
            saved = await poi_service.generate_and_save(prop, session)
            if not saved:
                logger.warning("Map POI task: empty results for property %s", property_id)
                return

            logger.info("Map POI generated for property %s: %d categories",
                        property_id, len((saved.map_poi_data or {}).get("categories", {})))

        await engine.dispose()

    asyncio.run(_run())


@celery_app.task(
    name="backfill_all_map_pois",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=1,
)
def backfill_all_map_pois() -> int:
    """存量房源批量补生成地图 POI（查找 map_poi_data 为空的房源）"""

    import asyncio

    async def _run() -> int:
        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        async with async_session() as session:
            # 查找有坐标但 map_poi_data 缺失的房源
            from sqlalchemy import and_, or_
            result = await session.execute(
                select(Property.id)
                .where(
                    Property.latitude.isnot(None),
                    Property.longitude.isnot(None),
                )
            )
            all_ids = [row[0] for row in result.all()]

            # 检查哪些还没有 map_poi_data
            missing: list[int] = []
            for pid in all_ids:
                poi_result = await session.execute(
                    select(PropertyPOI.map_poi_data)
                    .where(PropertyPOI.property_id == pid)
                )
                row = poi_result.first()
                if not row or not row[0]:
                    missing.append(pid)

        await engine.dispose()

        for pid in missing:
            generate_map_pois_for_property.delay(pid)

        logger.info("Backfill enqueued: %d properties for map POI generation", len(missing))
        return len(missing)

    return asyncio.run(_run())


# ═══════════════════════════════════════════════════════
# 安全评分回填
# ═══════════════════════════════════════════════════════

@celery_app.task(
    name="backfill_safety_scores",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=1,
)
def backfill_safety_scores() -> int:
    """存量房源批量补生成安全评分——遍历有坐标房源，逐条 dispatch"""

    import asyncio

    async def _run() -> int:
        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        async with async_session() as session:
            result = await session.execute(
                select(Property.id)
                .where(
                    Property.latitude.isnot(None),
                    Property.longitude.isnot(None),
                )
            )
            all_ids = [row[0] for row in result.all()]

            # 过滤已有 safety_data 的房源
            missing = []
            for pid in all_ids:
                poi_result = await session.execute(
                    select(PropertyPOI.safety_data)
                    .where(PropertyPOI.property_id == pid)
                )
                row = poi_result.first()
                if not row or not row[0]:
                    missing.append(pid)

        await engine.dispose()

        for pid in missing:
            generate_full_poi_for_property.delay(pid)

        logger.info("Safety backfill enqueued: %d properties", len(missing))
        return len(missing)

    return asyncio.run(_run())
