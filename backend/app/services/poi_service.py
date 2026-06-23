import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.poi import PropertyPOI
from app.models.property import Property

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

    async def generate_poi_for_property(self, property_obj: Property) -> PropertyPOI | None:
        existing = await self.session.execute(
            select(PropertyPOI).where(PropertyPOI.property_id == property_obj.id)
        )
        found = existing.scalar_one_or_none()
        if found:
            return found

        district = property_obj.district or "工业园区"
        mock = MOCK_POI.get(district, MOCK_POI["工业园区"])
        summary = mock["summary"]
        categories = mock["categories"]

        if self.client:
            try:
                prompt = (
                    "为以下地址生成周边设施描述（中文），"
                    "包含交通、餐饮、购物、教育、医疗等类别。"
                    + "\n\n地址：" + property_obj.address
                    + "\n\n请返回JSON："
                    + '{"summary": "综合描述", "categories": {"交通":[{"name":"站名","distance":"距离"}], ...}}'
                )
                response = await self.client.chat.completions.create(
                    model=settings.openai_chat_model or "gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=800,
                    response_format={"type": "json_object"},
                )
                content_text = response.choices[0].message.content
                if content_text:
                    result = json.loads(content_text)
                    summary = result.get("summary", summary)
                    categories = result.get("categories", categories)
            except Exception as e:
                logger.warning("OpenAI POI failed, using mock: %s", e)

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
