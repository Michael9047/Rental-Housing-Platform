"""StarRez PMS Connector — 拉取 → 映射 → 输出标准化 Property dict"""
import json
import logging
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.services.llm_service import get_llm_service
from app.services.pms.base import PMSConnector, PMSPropertyData
from app.services.pms.starrez.client import StarRezClient
from app.services.pms.starrez.extractor import StarRezExtractor

logger = logging.getLogger(__name__)

# 加载对照表
_FIELD_MAP_PATH = Path(__file__).parent / "field_map.json"
with open(_FIELD_MAP_PATH, encoding="utf-8") as _f:
    FIELD_MAP: dict[str, Any] = json.load(_f)


class StarRezConnector(PMSConnector):
    """StarRez REST API 连接器"""

    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        super().__init__(base_url, api_key)
        self.client = StarRezClient(base_url=base_url, api_key=api_key)
        llm = None
        try:
            llm = get_llm_service()
        except Exception:
            logger.warning("LLM service unavailable — AI description extraction disabled")
        self.extractor = StarRezExtractor(llm)

    @property
    def pms_type(self) -> str:
        return "starrez"

    # ── PMSConnector 接口实现 ────────────────────────────

    async def fetch_properties(self) -> list[dict[str, Any]]:
        return await self.client.fetch_spaces()

    def get_field_map(self) -> dict[str, Any]:
        return FIELD_MAP

    # ── 核心映射逻辑 ──────────────────────────────────────

    async def map_property(
        self,
        raw: dict[str, Any],
        overrides: dict[str, Any] | None = None,
        room_type_mapping: dict[str, str] | None = None,
    ) -> PMSPropertyData:
        """将一条 StarRez space 数据翻译为平台标准 dict"""
        fields_config = (overrides or {}).get("fields") or FIELD_MAP["fields"]
        effective_room_types = room_type_mapping or {}

        mapped: dict[str, Any] = {}
        unmapped: dict[str, Any] = {}
        confidence: dict[str, str] = {}

        for starrez_path, config in fields_config.items():
            value = self._get_nested(raw, starrez_path)
            if value is None:
                continue

            target = config.get("target")
            map_type = config.get("type")

            try:
                if map_type == "direct":
                    if target:
                        mapped[target] = value
                        confidence[target] = "direct"

                elif map_type == "lookup" and config.get("strategy") == "array_lookup":
                    # amenities 数组逐项查表 — 必须放在普通 lookup 之前，因为 value 是 list
                    if target and isinstance(value, list):
                        lookup = config.get("lookup", {})
                        mapped_values = [lookup.get(item, item) for item in value]
                        mapped[target] = mapped_values
                        confidence[target] = "lookup"

                elif map_type == "lookup":
                    if target and isinstance(value, str) and value in config.get("lookup", {}):
                        mapped[target] = config["lookup"][value]
                        confidence[target] = "lookup"
                    elif target and config.get("fallback") == "ai":
                        unmapped[starrez_path] = {"value": value, "target": target, "reason": "no_match"}

                elif map_type == "computed":
                    result = self._apply_transform(config.get("transform", ""), raw, value)
                    if target and result is not None:
                        mapped[target] = result
                        confidence[target] = "computed"

                elif map_type == "direct_array":
                    if target and isinstance(value, list):
                        mapped[target] = value
                        confidence[target] = "direct"

            except Exception:
                logger.warning("Field mapping failed for %s → %s", starrez_path, target, exc_info=True)
                unmapped[starrez_path] = {"value": value, "target": target, "reason": "mapping_error"}

        # ── 处理 room_type_mapping 覆盖 ──
        starrez_type = self._get_nested(raw, "type")
        if starrez_type and "property_type" not in mapped and effective_room_types:
            mapped_type = effective_room_types.get(starrez_type)
            if mapped_type:
                mapped["property_type"] = mapped_type
                confidence["property_type"] = "override"

        # ── rent_type 推断 ──
        if "rent_type" not in mapped:
            capacity = raw.get("capacity", 1)
            space_type = str(starrez_type or "").lower()
            if "shared" in space_type or "twin" in space_type or "triple" in space_type:
                mapped["rent_type"] = "shared"
            elif capacity > 1:
                mapped["rent_type"] = "shared"
            else:
                mapped["rent_type"] = "whole"
            confidence["rent_type"] = "inferred"

        # ── AI 提取描述文本中的隐藏字段 ──
        description = raw.get("description", "")
        if description and self.extractor:
            ai_extracted = await self.extractor.extract(description)
            for key, val in ai_extracted.items():
                if key not in mapped and val is not None:
                    mapped[key] = val
                    confidence[key] = "ai"

        return PMSPropertyData(
            external_id=raw.get("id", ""),
            raw=raw,
            mapped=mapped,
            unmapped=unmapped,
            confidence=confidence,
        )

    async def map_all(
        self,
        raw_list: list[dict[str, Any]],
        overrides: dict[str, Any] | None = None,
        room_type_mapping: dict[str, str] | None = None,
    ) -> list[PMSPropertyData]:
        """批量翻译"""
        results = []
        for raw in raw_list:
            results.append(await self.map_property(raw, overrides, room_type_mapping))
        return results

    async def close(self) -> None:
        await self.client.close()

    # ── 内部工具方法 ──────────────────────────────────────

    @staticmethod
    def _get_nested(data: dict[str, Any], path: str) -> Any:
        """从嵌套 dict 中按点号路径取值，如 'space.building' → data['space']['building']"""
        current: Any = data
        for key in path.split("."):
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
        return current

    @staticmethod
    def _apply_transform(transform_name: str, raw: dict[str, Any], _value: Any) -> Any:
        """执行计算转换"""
        space = raw
        lease = raw.get("lease", {})

        if transform_name == "multiply(4.33)":
            rate = lease.get("rate_per_week")
            if rate is not None:
                return round(Decimal(str(rate)) * Decimal("4.33"), 2)

        elif transform_name == "occupancy_to_bedrooms":
            occ = space.get("max_occupancy", 0)
            if occ <= 1:
                return 0
            elif occ == 2:
                return 1
            elif occ == 3:
                return 2
            else:
                return 3

        elif transform_name == "date_diff_months":
            start = lease.get("start_date")
            end = lease.get("end_date")
            if start and end:
                try:
                    s = datetime.strptime(start, "%Y-%m-%d").date()
                    e = datetime.strptime(end, "%Y-%m-%d").date()
                    return round((e - s).days / 30.44)
                except (ValueError, TypeError):
                    return None

        elif transform_name == "divide(4.33)":
            weeks = lease.get("min_stay_weeks")
            if weeks is not None:
                return max(1, round(weeks / 4.33))

        elif transform_name == "weeks_to_deposit_type":
            weeks = lease.get("deposit_weeks")
            if weeks is None:
                return None
            if weeks <= 1:
                return "custom"
            elif weeks <= 2:
                return "half_month"
            elif weeks <= 4:
                return "one_month"
            elif weeks <= 8:
                return "two_months"
            else:
                return "three_month"

        elif transform_name == "capacity_to_rent_type":
            cap = space.get("capacity", 1)
            return "shared" if cap > 1 else "whole"

        return None
