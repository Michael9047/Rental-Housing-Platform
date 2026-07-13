import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.poi import PropertyPOI
from app.models.property import Property
from app.services.geocoding_service import (BaseGeocodingService, get_primary_service, search_nearby_with_fallback)

logger = logging.getLogger(__name__)
settings = get_settings()

MOCK_POI = {
    "工业园区": {
        "summary": "该地址位于苏州工业园区核心地段，周边商业配套成熟，交通便捷。邻近金鸡湖景区，环境优美，适合居住。",
        "categories": {
            "交通": [
                {"name": "地铁1号线时代广场站", "distance": "500m"},
                {"name": "地铁3号线东方之门站", "distance": "800m"},
                {"name": "星海街公交站", "distance": "300m"},
            ],
            "餐饮": [
                {"name": "星海广场美食街", "distance": "400m"},
                {"name": "圆融时代广场", "distance": "600m"},
            ],
            "购物": [
                {"name": "久光百货", "distance": "500m"},
                {"name": "圆融时代商圈", "distance": "600m"},
            ],
        },
    },
    "姑苏区": {
        "summary": "该地址位于苏州古城区，历史文化氛围浓厚。周边园林景观优美，古典与现代交融，生活便利。",
        "categories": {
            "交通": [
                {"name": "地铁4号线乐桥站", "distance": "600m"},
                {"name": "地铁1号线临顿路站", "distance": "900m"},
            ],
            "餐饮": [
                {"name": "平江路美食街", "distance": "300m"},
                {"name": "观前街小吃一条街", "distance": "1km"},
            ],
            "购物": [
                {"name": "观前街商圈", "distance": "1km"},
                {"name": "美罗商城", "distance": "1.5km"},
            ],
        },
    },
    "高新区": {
        "summary": "该地址位于苏州高新区，周边高新企业众多，商业配套快速发展。交通便利，环境宜居。",
        "categories": {
            "交通": [
                {"name": "地铁3号线狮山路站", "distance": "400m"},
                {"name": "有轨电车1号线", "distance": "600m"},
            ],
            "餐饮": [
                {"name": "龙湖天街美食层", "distance": "500m"},
                {"name": "绿宝广场", "distance": "800m"},
            ],
            "购物": [
                {"name": "龙湖天街", "distance": "500m"},
            ],
        },
    },
    "吴中区": {
        "summary": "该地址位于吴中区，紧邻太湖，自然环境优越。周边新兴商圈快速发展，生态居住区域。",
        "categories": {
            "交通": [{"name": "地铁4号线支线太湖新城站", "distance": "1km"}],
            "餐饮": [{"name": "永旺梦乐城", "distance": "800m"}],
            "购物": [{"name": "永旺梦乐城", "distance": "800m"}],
        },
    },
    "相城区": {
        "summary": "该地址位于相城区，交通便捷，高铁新城辐射显著。商业配套在快速完善中。",
        "categories": {
            "交通": [
                {"name": "地铁2号线高铁苏州北站", "distance": "500m"},
                {"name": "高铁苏州北站", "distance": "500m"},
            ],
            "餐饮": [{"name": "高铁新城商业街", "distance": "400m"}],
            "购物": [{"name": "高铁新城吾悦广场", "distance": "600m"}],
        },
    },
    "吴江区": {
        "summary": "该地址位于吴江区，水乡特色鲜明，生活成本较低。交通便捷，与上海青浦接壤。",
        "categories": {
            "交通": [
                {"name": "地铁4号线汾湖站", "distance": "1km"},
                {"name": "汾湖高速入口", "distance": "2km"},
            ],
            "餐饮": [{"name": "汾湖商业街", "distance": "500m"}],
            "购物": [{"name": "汾湖中心商场", "distance": "800m"}],
        },
    },
}

NEARBY_SEARCH_PLAN: dict[str, list[str]] = {
    "交通": ["地铁站", "公交站", "火车站"],
    "医疗": ["医院", "诊所", "药店"],
    "教育": ["学校", "大学", "幼儿园"],
    "购物": ["超市", "商场", "便利店"],
    "餐饮": ["餐厅", "美食", "快餐"],
    "生活服务": ["银行", "菜市场", "快递", "洗衣店"],
}

class POIService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.client = None
        try:
            if settings.openai_api_key:
                from openai import AsyncOpenAI
                self.client = AsyncOpenAI(
                    api_key=settings.openai_api_key,
                    base_url=getattr(settings, "openai_base_url", None),
                )
        except Exception as e:
            logger.warning("OpenAI init failed: %s", e)

    async def generate_poi_for_property(self, property_obj: Property, *, force: bool = False) -> PropertyPOI | None:
        existing = await self.session.execute(
            select(PropertyPOI).where(PropertyPOI.property_id == property_obj.id)
        )
        found = existing.scalar_one_or_none()
        if found and not force:
            return found

        summary, categories = await self._build_poi_payload(property_obj)

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
        district = property_obj.district or "工业园区"

        try:
            geo_service = get_primary_service(getattr(property_obj, 'country', None))
            location = await self._resolve_location(geo_service, property_obj)
            if location:
                categories = await self._collect_nearby_categories(geo_service, location)
                if categories:
                    summary = await self._compose_summary(property_obj, categories)
                    return summary, categories
        except Exception as exc:
            logger.warning("Primary geocoding nearby generation failed, using fallback: %s", exc)

        mock = MOCK_POI.get(district, MOCK_POI["工业园区"])
        summary = mock["summary"]
        categories = mock["categories"]

        if self.client:
            try:
                prompt = (
                    "请根据以下房源地址与周边设施数据，用中文生成一段自然的居住环境简介。"
                    "要求：不要编造不存在的设施，不要分点，控制在80-120字。"
                    + "\n\n地址：" + property_obj.address
                    + "\n\n周边设施JSON："
                    + json.dumps(categories, ensure_ascii=False)
                    + "\n\n请只返回JSON：{\"summary\": \"...\"}"
                )
                response = await self.client.chat.completions.create(
                    model=settings.openai_chat_model or "gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,
                    max_tokens=300,
                    response_format={"type": "json_object"},
                )
                content_text = response.choices[0].message.content
                if content_text:
                    result = json.loads(content_text)
                    summary = result.get("summary", summary)
            except Exception as e:
                logger.warning("OpenAI POI failed, using fallback: %s", e)

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
        categories: dict[str, list[dict[str, str]]] = {}

        for category, keywords in NEARBY_SEARCH_PLAN.items():
            merged: dict[str, dict[str, str]] = {}
            for keyword in keywords:
                results = await geo_service.search_nearby(location, keyword, category=category)
                for item in results:
                    existing = merged.get(item.name)
                    current_distance = self._distance_to_int(item.distance)
                    existing_distance = self._distance_to_int(existing.get("distance")) if existing else None
                    if existing is None or (
                        current_distance is not None
                        and (existing_distance is None or current_distance < existing_distance)
                    ):
                        merged[item.name] = item.to_dict()

            if merged:
                ordered = sorted(
                    merged.values(),
                    key=lambda entry: self._distance_to_int(entry.get("distance")) or 10**9,
                )
                categories[category] = ordered[:5]

        return categories

    async def _compose_summary(
        self,
        property_obj: Property,
        categories: dict[str, list[dict[str, str]]],
    ) -> str:
        if self.client:
            try:
                prompt = (
                    "请根据以下房源地址和周边设施数据，用中文生成一段真实、克制的居住环境简介。"
                    "不要夸大，不要编造，只返回JSON：{\"summary\": \"...\"}。"
                    + "\n\n地址：" + property_obj.address
                    + "\n\n周边设施JSON："
                    + json.dumps(categories, ensure_ascii=False)
                )
                response = await self.client.chat.completions.create(
                    model=settings.openai_chat_model or "gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.4,
                    max_tokens=240,
                    response_format={"type": "json_object"},
                )
                content_text = response.choices[0].message.content
                if content_text:
                    result = json.loads(content_text)
                    summary = result.get("summary")
                    if summary:
                        return summary
            except Exception as exc:
                logger.warning("OpenAI summary failed, using deterministic summary: %s", exc)

        parts: list[str] = []
        for category, items in categories.items():
            if not items:
                continue
            top_names = "、".join(item["name"] for item in items[:2])
            parts.append(f"{category}{len(items)}项，如{top_names}")

        base = property_obj.district or property_obj.address
        if parts:
            return f"该房源位于{base}，周边已检索到{ '；'.join(parts) }等配套，适合日常居住。"
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
        result = await self.session.execute(
            select(PropertyPOI).where(PropertyPOI.property_id == property_id)
        )
        poi = result.scalar_one_or_none()
        if poi:
            return poi
        prop = await self.session.get(Property, property_id)
        if not prop:
            return None
        return await self.generate_poi_for_property(prop)

    async def get_poi(self, property_id: int) -> PropertyPOI | None:
        result = await self.session.execute(
            select(PropertyPOI).where(PropertyPOI.property_id == property_id)
        )
        return result.scalar_one_or_none()



