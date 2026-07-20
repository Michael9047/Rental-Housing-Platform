"""
LLM 智能房源解析服务
利用 OpenAI GPT-4o 从自由文本中提取结构化房源信息
替代 CreateProperty.vue 中的正则 smartParse()，准确率和覆盖范围大幅提升
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── 解析结果 ────────────────────────────────────────────


@dataclass
class ParsedProperty:
    """LLM 解析后的结构化房源信息"""
    title: str | None = None
    address: str | None = None
    district: str | None = None
    price_monthly: float | None = None
    deposit_amount: float | None = None
    service_fee_rate: float | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    area_sqm: float | None = None
    property_type: str | None = None  # apartment/house/studio/shared
    description: str | None = None
    amenities: list[str] = field(default_factory=list)
    latitude: float | None = None
    longitude: float | None = None
    building_name: str | None = None
    room_number: str | None = None
    floor: int | None = None
    orientation: str | None = None
    unrecognized: list[str] = field(default_factory=list)
    confidence: str = "low"  # high/medium/low

    def to_dict(self) -> dict[str, Any]:
        """转为前端可用字典，过滤 None 值"""
        result = {}
        for key, val in self.__dict__.items():
            if val is not None and val != [] and val != "":
                result[key] = val
        return result


# ── 解析服务 ────────────────────────────────────────────


class LLMPropertyParser:
    """
    基于 GPT-4o 的智能房源解析器

    相比正则方案的优势：
    - 能理解自然语言中的隐含信息（"押一付三" → 押金=月租, 付三）
    - 能处理各种句式变体（正则只能覆盖预设模式）
    - 自动提取配套设施标签（amenities）
    - 统一户型术语（"单身公寓" → studio, "两室一厅" → 2室1厅）
    - 零样本，无需训练数据
    """

    # 有效值约束
    VALID_PROPERTY_TYPES = ["apartment", "house", "studio", "shared"]
    VALID_AMENITIES = [
        "电梯", "空调", "洗衣机", "冰箱", "WiFi", "暖气", "阳台",
        "独立卫浴", "健身房", "自习室", "游泳池", "停车场",
        "24小时前台", "校车接驳", "签证咨询", "可养宠物", "近地铁",
        "包水电", "精装修", "首次出租", "南北通透",
    ]
    SUZHOU_DISTRICTS = [
        "工业园区", "姑苏区", "高新区", "吴中区", "相城区", "吴江区",
        "昆山市", "太仓市", "常熟市", "张家港市",
    ]

    def __init__(self, openai_client):
        """
        参数:
            openai_client: AsyncOpenAI 实例
        """
        self.client = openai_client

    async def parse(self, raw_text: str, model: str = "gpt-4o") -> ParsedProperty:
        """
        从自由文本解析房源信息

        参数:
            raw_text: 用户输入的自由文本（描述、中介文案等）
            model: 模型名，默认 gpt-4o，降成本可用 gpt-4o-mini
        返回:
            ParsedProperty 结构化结果
        """
        system_prompt = self._build_system_prompt()
        user_prompt = f"请解析以下房源描述：\n\n{raw_text}"

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=800,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if not content:
                return ParsedProperty(unrecognized=[raw_text[:60]], confidence="low")

            data = json.loads(content)
            return self._parse_response(data, raw_text)

        except Exception as exc:
            logger.exception("LLM parsing failed: %s", exc)
            return ParsedProperty(
                unrecognized=[raw_text[:60]],
                confidence="low",
            )

    async def batch_parse(
        self,
        texts: list[dict],
        model: str = "gpt-4o-mini",
    ) -> list[ParsedProperty]:
        """
        批量解析（用于批量导入时自动标签提取）

        参数:
            texts: [{row, text}] 多行待解析文本
            model: 批量用 gpt-4o-mini 降成本
        返回:
            [{row, parsed}] 解析结果
        """
        results = []
        for item in texts:
            try:
                parsed = await self.parse(item["text"], model=model)
                results.append({"row": item["row"], "parsed": parsed})
            except Exception as exc:
                logger.warning("Batch parse failed for row %s: %s", item["row"], exc)
                results.append({
                    "row": item["row"],
                    "parsed": ParsedProperty(confidence="low"),
                })
        return results

    async def extract_amenities(
        self,
        description: str,
        model: str = "gpt-4o-mini",
    ) -> list[str]:
        """从描述中提取配套设施标签"""
        prompt = f"""根据以下房源描述，判断包含哪些配套设施。

可选标签: {', '.join(self.VALID_AMENITIES)}

规则:
- 只选择描述中明确提到或合理推断的标签
- 不要猜测，不确定就不选
- 返回 JSON: {{"amenities": ["标签1", "标签2"]}}

描述: {description}"""

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=300,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            if content:
                data = json.loads(content)
                amenities = data.get("amenities", [])
                return [a for a in amenities if a in self.VALID_AMENITIES]
        except Exception as exc:
            logger.warning("Amenity extraction failed: %s", exc)

        return []

    # ── 私有方法 ────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        return f"""你是一个专业的房源信息提取助手。从用户输入的房源描述中提取结构化字段。

字段说明:
- title: 房源标题（20字以内，格式如"工业园区翰林缘精装单间"）
- address: 详细地址（提取路名+小区名+门牌号）
- district: 所属区域，必须是以下之一: {', '.join(self.SUZHOU_DISTRICTS)}
- price_monthly: 月租金（数字，单位元/月。如"押一付三"不填价格）
- deposit_amount: 押金金额（数字，单位元）
- service_fee_rate: 服务费比例（如 10% 填 0.10）
- bedrooms: 卧室数量（整数。如"两室一厅"→2，"单身公寓"→0或1）
- bathrooms: 卫生间数量（整数。"独立卫浴"→1）
- area_sqm: 面积（数字，单位㎡）
- property_type: 房源类型，必须是以下之一:
  - "apartment": 普通公寓/住宅
  - "house": 别墅/独栋
  - "studio": 单间/单身公寓/开间
  - "shared": 合租/合住
- building_name: 楼栋/小区名称
- room_number: 房号/门牌号
- floor: 所在楼层（整数，不带"层"字）
- orientation: 朝向（"东南西北"组合）
- description: 房源描述（整理后200字以内）
- amenities: 配套设施列表，从以下选择:
  {', '.join(self.VALID_AMENITIES)}
- unrecognized: 无法归类的剩余文本片段
- confidence: 置信度（"high": 大部分字段确认, "medium": 部分推测, "low": 信息不足）

规则:
1. 缺失的字段不要编造，填 null
2. 数字字段只返回数字，不要带单位
3. "押一付三"→ deposit_amount=price_monthly（押金=1个月租金）
4. "独立卫浴"→ bathrooms=1
5. "精装修"→ amenities 包含"精装修"
6. 所有金额单位为人民币元
7. 只返回 JSON，不要额外解释"""

    def _parse_response(self, data: dict, raw_text: str) -> ParsedProperty:
        """将 LLM 返回的 JSON 转为 ParsedProperty，做合法性校验"""
        result = ParsedProperty()

        # 字符串字段
        for field in ["title", "address", "district", "description",
                       "building_name", "room_number", "orientation"]:
            val = data.get(field)
            if isinstance(val, str) and val.strip():
                setattr(result, field, val.strip())

        # 区域校验
        if result.district and result.district not in self.SUZHOU_DISTRICTS:
            result.unrecognized.append(f"区域'{result.district}'不在已知列表中")
            result.district = None

        # 数字字段
        for field in ["price_monthly", "deposit_amount", "area_sqm"]:
            val = data.get(field)
            if val is not None:
                try:
                    setattr(result, field, float(val))
                except (ValueError, TypeError):
                    pass

        # 整数字段
        for field in ["bedrooms", "bathrooms", "floor"]:
            val = data.get(field)
            if val is not None:
                try:
                    setattr(result, field, int(val))
                except (ValueError, TypeError):
                    pass

        # 比例字段
        val = data.get("service_fee_rate")
        if val is not None:
            try:
                rate = float(val)
                if rate > 1:  # 用户可能传 10 而不是 0.10
                    rate = rate / 100
                result.service_fee_rate = rate
            except (ValueError, TypeError):
                pass

        # 枚举字段
        ptype = data.get("property_type")
        if isinstance(ptype, str) and ptype.strip().lower() in self.VALID_PROPERTY_TYPES:
            result.property_type = ptype.strip().lower()

        # 配套标签
        amenities = data.get("amenities", [])
        if isinstance(amenities, list):
            result.amenities = [a for a in amenities if a in self.VALID_AMENITIES]

        # 经纬度
        for field in ["latitude", "longitude"]:
            val = data.get(field)
            if val is not None:
                try:
                    setattr(result, field, float(val))
                except (ValueError, TypeError):
                    pass

        # 未识别内容
        unrecognized = data.get("unrecognized", [])
        if isinstance(unrecognized, list):
            result.unrecognized = unrecognized[:3]

        # 置信度
        conf = data.get("confidence", "medium")
        if conf in ("high", "medium", "low"):
            result.confidence = conf

        # 如果几乎所有字段都为空，降级为 low
        filled = sum(1 for v in result.__dict__.values()
                      if v is not None and v != [] and v != "")
        if filled <= 2:
            result.confidence = "low"
            result.unrecognized.append(raw_text[:60])

        return result
