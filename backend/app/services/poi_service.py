import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.models.poi import PropertyPOI
from app.models.property import Property
from app.services.geocoding_service import (BaseGeocodingService, get_primary_service)

logger = logging.getLogger(__name__)

NEARBY_SEARCH_PLAN: dict[str, list[str]] = {
    "交通": ["地铁站", "公交站", "火车站"],
    "医疗": ["医院", "诊所", "药店"],
    "教育": ["学校", "大学", "幼儿园"],
    "购物": ["超市", "商场", "便利店"],
    "餐饮": ["餐厅", "美食", "快餐"],
    "生活服务": ["银行", "菜市场", "快递", "洗衣店"],
}

# 地图小卡片 POI 分类 → 搜索关键词（与前端 PropertyMapCard 6 个 Tab 对齐）
MAP_POI_CATEGORIES: dict[str, list[str]] = {
    "school": ["大学"],
    "bus_station": ["公交站"],
    "subway_station": ["地铁站"],
    "supermarket": ["超市"],
    "restaurant": ["餐厅", "快餐"],
    "pharmacy": ["药店"],
    "gym": ["健身房"],
    "medical": ["医院", "诊所", "药店"],
}
MAP_POI_SEARCH_RADIUS = 3000  # 米

class POIService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_poi_for_property(self, property_obj: Property, *, force: bool = False) -> PropertyPOI | None:
        existing = await self.session.execute(
            select(PropertyPOI).where(PropertyPOI.property_id == property_obj.id)
        )
        found = existing.scalar_one_or_none()
        if found and not force:
            return found

        try:
            summary, categories = await self._build_poi_payload(property_obj)
        except Exception as exc:
            logger.error("POI 生成失败 property_id=%s: %s", property_obj.id, exc)
            # 删除旧假数据
            if found:
                await self.session.delete(found)
                await self.session.commit()
            return None

        if found:
            found.content = summary
            found.poi_data = categories
            found.generated_at = datetime.now(timezone.utc)
            found.reviewed = False
            poi = found
        else:
            poi = PropertyPOI(
                property_id=property_obj.id,
                content=summary,
                poi_data=categories,
                generated_at=datetime.now(timezone.utc),
                reviewed=False,
            )
            self.session.add(poi)

        await self.session.commit()
        await self.session.refresh(poi)
        return poi

    async def _build_poi_payload(self, property_obj: Property) -> tuple[str, dict[str, list[dict[str, str]]]]:
        """通过 Overpass/高德 搜索真实周边设施，失败时抛出异常而非返回假数据"""
        geo_service = get_primary_service(property_obj.country)
        location = await self._resolve_location(geo_service, property_obj)
        if not location:
            raise RuntimeError(f"无法解析房源坐标: {property_obj.address}")

        categories = await self._collect_nearby_categories(geo_service, location)
        if not categories:
            raise RuntimeError(f"周边设施搜索无结果: {property_obj.address} (引擎: {type(geo_service).__name__})")

        summary = self._compose_deterministic_summary(property_obj, categories)
        return summary, categories

    async def _resolve_location(
        self,
        geo_service: BaseGeocodingService,
        property_obj: Property,
    ) -> str | None:
        if property_obj.longitude is not None and property_obj.latitude is not None:
            return f"{property_obj.longitude},{property_obj.latitude}"

        geocode = await geo_service.geocode(property_obj.address, property_obj.district)
        return f"{geocode.longitude},{geocode.latitude}"

    async def _collect_nearby_categories(
        self,
        geo_service: BaseGeocodingService,
        location: str,
    ) -> dict[str, list[dict[str, str]]]:
        """并发搜索周边设施，限流 6 个并发避免压垮 Overpass 端点"""
        # 扁平化所有 (category, keyword) 任务
        tasks: list[tuple[str, str]] = []
        for category, keywords in NEARBY_SEARCH_PLAN.items():
            for keyword in keywords:
                tasks.append((category, keyword))

        semaphore = asyncio.Semaphore(6)

        async def search_one(category: str, keyword: str) -> tuple[str, str, list]:
            async with semaphore:
                try:
                    results = await geo_service.search_nearby(location, keyword, category=category)
                except Exception:
                    results = []
                return category, keyword, results

        all_results = await asyncio.gather(
            *[search_one(cat, kw) for cat, kw in tasks],
            return_exceptions=True,
        )

        # 按分类聚合结果
        merged_by_category: dict[str, dict[str, dict[str, str]]] = {}
        for item in all_results:
            if isinstance(item, BaseException):
                continue
            cat, kw, results = item
            if cat not in merged_by_category:
                merged_by_category[cat] = {}
            merged = merged_by_category[cat]
            for poi in results:
                existing = merged.get(poi.name)
                current_dist = self._distance_to_int(poi.distance)
                existing_dist = self._distance_to_int(existing.get("distance")) if existing else None
                if existing is None or (
                    current_dist is not None
                    and (existing_dist is None or current_dist < existing_dist)
                ):
                    merged[poi.name] = poi.to_dict()

        categories: dict[str, list[dict[str, str]]] = {}
        for cat, merged in merged_by_category.items():
            if merged:
                ordered = sorted(
                    merged.values(),
                    key=lambda entry: self._distance_to_int(entry.get("distance")) or 10**9,
                )
                categories[cat] = ordered[:5]

        return categories

    def _compose_deterministic_summary(
        self,
        property_obj: Property,
        categories: dict[str, list[dict[str, str]]],
    ) -> str:
        """根据真实搜索数据生成摘要，不依赖 AI"""
        parts: list[str] = []
        for category, items in categories.items():
            if not items:
                continue
            top_names = "、".join(item["name"] for item in items[:2])
            parts.append(f"{category}{len(items)}项，如{top_names}")

        base = property_obj.district or property_obj.address
        if parts:
            return f"该房源位于{base}，周边已检索到{'；'.join(parts)}等配套，适合日常居住。"
        return f"该房源位于{base}，周边生活配套待补充。"

    @staticmethod
    def _distance_to_int(distance: str | None) -> int | None:
        if not distance:
            return None
        text = str(distance).strip().lower().replace("米", "")
        try:
            if text.endswith("km"):
                return int(float(text[:-2].strip()) * 1000)
            if text.endswith("m"):
                return int(float(text[:-1].strip()))
            return int(float(text))
        except ValueError:
            return None

    async def get_or_generate_poi(self, property_id: int) -> PropertyPOI | None:
        """获取或自动生成房源 POI 数据。

        优先返回已有 POI；不存在时自动生成（含 mock 兜底）。
        仅在房源本身不存在时返回 None。
        """
        result = await self.session.execute(
            select(PropertyPOI).where(PropertyPOI.property_id == property_id)
        )
        poi = result.scalar_one_or_none()
        if poi:
            return poi

        prop = await self.session.get(Property, property_id)
        if not prop:
            return None

        try:
            return await self.generate_poi_for_property(prop)
        except Exception as exc:
            logger.error("生成 POI 失败 property_id=%s: %s", property_id, exc)
            # 生成失败时返回 None，由调用方决定如何处理
            return None

    async def get_poi(self, property_id: int) -> PropertyPOI | None:
        result = await self.session.execute(
            select(PropertyPOI).where(PropertyPOI.property_id == property_id)
        )
        return result.scalar_one_or_none()

    # ── 地图小卡片 POI 预生成 ───────────────────────────────

    @staticmethod
    def is_map_poi_fresh(
        poi: PropertyPOI | None,
        *,
        now: datetime | None = None,
        ttl_hours: int | None = None,
    ) -> bool:
        """判断地图 POI 缓存是否仍在有效期内。"""
        if poi is None or not poi.map_poi_data or poi.generated_at is None:
            return False
        generated_at = poi.generated_at
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        max_age = timedelta(hours=ttl_hours or get_settings().poi_map_cache_ttl_hours)
        return generated_at >= current - max_age

    @staticmethod
    async def _acquire_refresh_lock(property_id: int) -> bool:
        """SETNX 短锁，保证同一房源同时只有一个刷新任务在飞。

        Redis 不可用时一律放行：去重是优化，不该成为刷新的前置条件。
        """
        settings = get_settings()
        try:
            from redis.asyncio import Redis as AsyncRedis

            client = AsyncRedis.from_url(settings.redis_url, decode_responses=False)
        except Exception:
            return True

        try:
            acquired = await client.set(
                f"poi:refresh:{property_id}",
                b"1",
                nx=True,
                ex=settings.poi_refresh_lock_seconds,
            )
            return bool(acquired)
        except Exception:
            return True
        finally:
            try:
                await client.aclose()
            except Exception:
                pass

    @staticmethod
    async def _enqueue_map_poi_refresh(property_id: int) -> None:
        """请求链路只投递刷新任务；测试 eager 模式下避免同步触发外部地图请求。

        必须去重：热门房源缓存过期的瞬间，每个并发请求都会走到这里，
        没有锁就是 N 个请求投 N 个任务、每个任务再打 9 次外部地图搜索。
        """
        try:
            from app.celery_app import celery_app

            if celery_app.conf.task_always_eager:
                logger.debug("Celery eager 模式下跳过 POI 后台刷新 property_id=%s", property_id)
                return

            if not await POIService._acquire_refresh_lock(property_id):
                logger.debug("POI 刷新已在进行中，跳过重复投递 property_id=%s", property_id)
                return

            from app.tasks.poi_tasks import generate_map_pois_for_property

            # .delay() 是 kombu 的同步 broker publish；直接在事件循环里调用，
            # Redis 挂掉时会用 broker_connection_timeout（2s）卡住整个 worker 进程。
            await run_in_threadpool(generate_map_pois_for_property.delay, property_id)
        except Exception:
            logger.warning("POI 后台刷新投递失败 property_id=%s", property_id, exc_info=True)

    async def generate_map_pois(self, property_obj: Property) -> dict | None:
        """生成地图小卡片 POI 数据（含健身与医疗，3km 半径，含 lat/lng）。

        与 AI 分析面板的 _build_poi_payload 独立，分类兼容前端地图与推荐摘要。
        返回的 dict 存入 PropertyPOI.map_poi_data。
        """
        geo_service = get_primary_service(property_obj.country)
        location = await self._resolve_location(geo_service, property_obj)
        if not location:
            logger.error("Map POI: 无法解析房源坐标 property_id=%s", property_obj.id)
            return None

        # 展开所有 (category_key, keyword) 任务（约 7 个，全部并行）
        tasks: list[tuple[str, str]] = []
        for cat_key, keywords in MAP_POI_CATEGORIES.items():
            for kw in keywords:
                tasks.append((cat_key, kw))

        async def search_one(cat_key: str, keyword: str) -> list:
            try:
                return await geo_service.search_nearby(
                    location,
                    keyword,
                    radius=MAP_POI_SEARCH_RADIUS,
                    page_size=25,
                    category=cat_key,
                )
            except Exception:
                return []

        all_results = await asyncio.gather(
            *[search_one(cat, kw) for cat, kw in tasks],
            return_exceptions=True,
        )

        # 按分类聚合，去重，保留最近
        merged: dict[str, dict[str, dict]] = {}
        for i, item in enumerate(all_results):
            if isinstance(item, BaseException):
                continue
            cat_key = tasks[i][0]
            if cat_key not in merged:
                merged[cat_key] = {}
            for poi in item:
                if not poi.name or not poi.lat or not poi.lng:
                    continue
                existing = merged[cat_key].get(poi.name)
                new_dist = poi.distance_meters or 10**9
                old_dist = existing["distance"] if existing else 10**9
                if existing is None or new_dist < old_dist:
                    merged[cat_key][poi.name] = {
                        "id": hash(poi.name) % 10**8,
                        "name": poi.name,
                        "lat": poi.lat,
                        "lng": poi.lng,
                        "distance": poi.distance_meters,
                        "line": None,
                    }

        categories: dict[str, list[dict]] = {}
        for cat_key, merged_items in merged.items():
            if merged_items:
                categories[cat_key] = sorted(
                    merged_items.values(),
                    key=lambda x: x["distance"] if x["distance"] is not None else 10**9,
                )[:30]

        return {
            "search_radius_m": MAP_POI_SEARCH_RADIUS,
            "categories": categories,
        }

    async def get_or_generate_map_pois(self, property_id: int) -> dict | None:
        """获取地图 POI；新鲜缓存直返，过期缓存先返回并异步刷新。"""
        result = await self.session.execute(
            select(PropertyPOI).where(PropertyPOI.property_id == property_id)
        )
        poi = result.scalar_one_or_none()

        # stale-while-revalidate：避免用户请求等待外部地图搜索。
        if poi and poi.map_poi_data:
            if not self.is_map_poi_fresh(poi):
                await self._enqueue_map_poi_refresh(property_id)
            return poi.map_poi_data

        prop = await self.session.get(Property, property_id)
        if not prop:
            return None

        data = await self.generate_map_pois(prop)
        if not data:
            return None

        # 持久化到 map_poi_data
        if poi:
            poi.map_poi_data = data
            poi.generated_at = datetime.now(timezone.utc)
        else:
            poi = PropertyPOI(
                property_id=property_id,
                content="",
                map_poi_data=data,
                generated_at=datetime.now(timezone.utc),
                reviewed=False,
            )
            self.session.add(poi)

        await self.session.commit()
        return data
