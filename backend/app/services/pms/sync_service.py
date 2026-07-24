"""PMS 同步调度层 — 调 connector 拉数据 → 翻译 → 写库"""
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pms_connection import PMSConnection, PMSSyncStatus
from app.models.property import Property
from app.schemas.property import PropertyCreate
from app.services.audit_service import AuditService
from app.services.pms.base import PMSConnector, PMSPropertyData
from app.services.property_service import PropertyService

logger = logging.getLogger(__name__)


class PMSSyncService:
    """PMS 同步调度器

    统一流程：
    1. 从 DB 读取 PMSConnection 配置
    2. 创建对应 Connector
    3. 拉取数据 → 逐条翻译 → 写库
    4. 更新 PMSConnection 同步状态
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── 公开接口 ──────────────────────────────────────────

    async def sync_connection(self, connection_id: int) -> dict[str, Any]:
        """对单个 PMS 连接执行全量同步"""
        conn = await self.session.get(PMSConnection, connection_id)
        if not conn:
            raise ValueError(f"PMSConnection {connection_id} not found")
        if not conn.is_active:
            raise ValueError(f"PMSConnection {connection_id} is inactive")

        # 标记同步中
        conn.sync_status = PMSSyncStatus.syncing
        await self.session.commit()

        stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0, "error_details": []}

        try:
            connector = self._create_connector(conn)

            # 1. 拉取数据
            raw_list = await connector.fetch_properties()

            # 2. 批量翻译
            mapped_list = await connector.map_all(
                raw_list,
                overrides=conn.field_map_overrides,
                room_type_mapping=conn.room_type_mapping,
            )

            # 3. 逐条写库
            for item in mapped_list:
                try:
                    result = await self._upsert_property(item, conn)
                    stats[result] += 1
                except Exception as exc:
                    stats["errors"] += 1
                    stats["error_details"].append({
                        "external_id": item.external_id,
                        "error": str(exc),
                    })
                    logger.warning("Sync error for %s: %s", item.external_id, exc)

            # 4. 更新同步状态
            conn.sync_status = PMSSyncStatus.success
            conn.last_synced_at = datetime.now(timezone.utc)
            conn.total_properties_synced = stats["created"] + stats["updated"]
            conn.last_sync_error = (json.dumps(stats["error_details"][:10])
                                    if stats["error_details"] else None)
            await self.session.commit()

            await connector.close()
            return stats

        except Exception as exc:
            conn.sync_status = PMSSyncStatus.failed
            conn.last_sync_error = str(exc)[:2000]
            await self.session.commit()
            raise

    async def preview_mapping(
        self, connection_id: int, limit: int = 5,
    ) -> list[dict[str, Any]]:
        """预览映射结果（入驻时人工确认用），不写库"""
        conn = await self.session.get(PMSConnection, connection_id)
        if not conn:
            raise ValueError(f"PMSConnection {connection_id} not found")

        connector = self._create_connector(conn)
        raw_list = await connector.fetch_properties()
        mapped_list = await connector.map_all(
            raw_list[:limit],
            overrides=conn.field_map_overrides,
            room_type_mapping=conn.room_type_mapping,
        )
        await connector.close()

        return [
            {
                "external_id": item.external_id,
                "mapped": item.mapped,
                "unmapped": item.unmapped,
                "confidence": item.confidence,
            }
            for item in mapped_list
        ]

    # ── 内部方法 ──────────────────────────────────────────

    def _create_connector(self, conn: PMSConnection) -> PMSConnector:
        """根据 PMSConnection 配置创建对应的 Connector"""
        pms_type = conn.pms_type.value

        if pms_type == "starrez":
            from app.services.pms.starrez import StarRezConnector
            return StarRezConnector(base_url=conn.base_url, api_key=conn.api_key)

        raise ValueError(f"Unsupported PMS type: {pms_type}")

    async def _upsert_property(
        self, item: PMSPropertyData, conn: PMSConnection,
    ) -> str:
        """写入或更新一条房源

        映射后的数据需要补全 PMS 连接特有的字段（landlord_id 暂用 institute 的 created_by），
        然后调 PropertyService.create() 或 PropertyService.update()。
        """
        mapped = item.mapped

        # ── 基础校验 ──
        if not mapped.get("title") or not mapped.get("address"):
            raise ValueError(f"Missing title or address for {item.external_id}")

        # ── 构造 PropertyCreate dict ──
        # institute 必须有 created_by（即 landlord_id），从 Institute 表查
        institute = conn.institute
        if not institute:
            raise ValueError(f"No institute linked to PMSConnection {conn.id}")

        property_data = {
            "landlord_id": institute.created_by,
            "institute_id": conn.institute_id,
            "title": mapped["title"],
            "address": mapped.get("address", ""),
            "district": mapped.get("district", "Unknown"),
            "price_monthly": mapped.get("price_monthly", 0),
            "country": mapped.get("country", "GB"),
            "property_type": mapped.get("property_type", "1-bed"),
            "status": mapped.get("status", "available"),
            "rent_type": mapped.get("rent_type", "monthly"),
            "description": mapped.get("description"),
            "area_sqm": mapped.get("area_sqm"),
            "bedrooms": mapped.get("bedrooms", 0),
            "bathrooms": mapped.get("bathrooms", 0),
            "latitude": mapped.get("latitude"),
            "longitude": mapped.get("longitude"),
            "room_number": mapped.get("room_number"),
            "floor": mapped.get("floor"),
            "amenities": mapped.get("amenities"),
            "available_from": mapped.get("available_from"),
            "min_lease_months": mapped.get("min_lease_months", 12),
            "min_stay_months": mapped.get("min_stay_months", 3),
            "deposit_amount": mapped.get("deposit_amount"),
            "deposit_type": mapped.get("deposit_type"),
            "image_urls": mapped.get("image_urls"),
        }

        # ── 去重检查 ──
        existing = await self.session.scalar(
            select(Property).where(
                Property.title == property_data["title"],
                Property.address == property_data["address"],
                Property.deleted_at.is_(None),
            )
        )

        if existing:
            # 更新已有房源
            for key, value in property_data.items():
                if key in ("landlord_id", "institute_id", "image_urls"):
                    continue
                if hasattr(existing, key) and value is not None:
                    setattr(existing, key, value)
            existing.updated_at = datetime.now(timezone.utc)
            await self.session.commit()

            await AuditService(self.session).create_log(
                user_id=property_data["landlord_id"],
                action="pms_sync_update",
                resource_type="property",
                resource_id=existing.id,
                details={"external_id": item.external_id, "pms_type": "starrez"},
            )
            return "updated"

        # ── 新建房源 ──
        # 清理 image_urls（PropertyService.create 需要单独处理）
        image_urls = property_data.pop("image_urls", None) or []
        create_schema = PropertyCreate(**property_data)
        if image_urls:
            create_schema.image_urls = image_urls

        property_service = PropertyService(self.session)
        await property_service.create(create_schema)

        await AuditService(self.session).create_log(
            user_id=property_data["landlord_id"],
            action="pms_sync_create",
            resource_type="property",
            resource_id=0,  # PropertyService.create doesn't return ID directly — TODO: fix
            details={"external_id": item.external_id, "pms_type": "starrez", "title": property_data["title"]},
        )
        return "created"
