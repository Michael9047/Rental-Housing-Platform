import asyncio
import csv
import io
import json
import logging
import threading
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_import import DataImport, ImportSourceType, ImportStatus
from app.models.property import Property, PropertyStatus, PropertyType
from app.services.column_mapper import ColumnMapper

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = {"title", "address", "district", "price_monthly"}
OPTIONAL_FIELDS = {
    "description",
    "area_sqm",
    "bedrooms",
    "bathrooms",
    "property_type",
    "latitude",
    "longitude",
    "status",
}
ALL_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS
VALID_PROPERTY_TYPES = {e.value for e in PropertyType}
VALID_STATUSES = {e.value for e in PropertyStatus}


class ImportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._created_property_ids: list[int] = []

    async def create_import_task(
        self,
        admin_id: int,
        source_name: str,
        source_type: str,
    ) -> DataImport:
        import_task = DataImport(
            admin_id=admin_id,
            source_name=source_name,
            source_type=ImportSourceType(source_type),
            status=ImportStatus.pending,
        )
        self.session.add(import_task)
        await self.session.commit()
        await self.session.refresh(import_task)
        return import_task

    async def get_import_task(self, task_id: int) -> DataImport | None:
        return await self.session.get(DataImport, task_id)

    async def list_tasks(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        status: str | None = None,
    ) -> list[DataImport]:
        stmt = (
            select(DataImport)
            .order_by(DataImport.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if status:
            stmt = stmt.where(DataImport.status == ImportStatus(status))
        result = await self.session.scalars(stmt)
        return list(result)

    async def parse_and_import(
        self,
        import_task: DataImport,
        file_content: bytes,
        landlord_id: int,
        institute_id: int | None = None,
    ) -> DataImport:
        self._created_property_ids = []
        import_task.status = ImportStatus.processing
        await self.session.commit()

        errors: list[dict] = []
        try:
            # ── Step 1: 解析文件 ───────────────────────
            raw_rows, raw_headers = self._parse_file_with_headers(file_content, import_task.source_type)

            # 检查空文件
            if not raw_headers:
                import_task.status = ImportStatus.failed
                import_task.failed_records = 1
                import_task.error_log = json.dumps(
                    [{"row": 0, "error": "文件无内容，未检测到表头行。请使用模板填写数据后重新上传", "type": "missing_field"}],
                    ensure_ascii=False,
                )
                await self.session.commit()
                return import_task

            # 检查只有表头无数据
            if not raw_rows:
                import_task.status = ImportStatus.failed
                import_task.failed_records = 1
                import_task.error_log = json.dumps(
                    [{"row": 0, "error": "未检测到有效房源信息，仅有表头无数据行。请在表头下方填写房源信息", "type": "missing_field"}],
                    ensure_ascii=False,
                )
                await self.session.commit()
                return import_task

            # ── Step 2: 列名映射 ────────────────────────
            mapper = ColumnMapper()
            mapping_result = mapper.match(raw_headers)

            # 检查必填列是否全部缺失
            mapped_fields = set(mapping_result.matched.values())
            missing_required = REQUIRED_FIELDS - mapped_fields
            if missing_required == REQUIRED_FIELDS:
                # 所有必填列都没匹配上 → 文件格式完全不对
                import_task.status = ImportStatus.failed
                import_task.failed_records = 1
                import_task.error_log = json.dumps(
                    [{"row": 0, "error": f"无法识别任何必填列（需要：房源标题/详细地址/所在区域/月租金）。检测到的列：{'、'.join(raw_headers[:8])}。请使用下载的模板格式", "type": "missing_field"}],
                    ensure_ascii=False,
                )
                await self.session.commit()
                return import_task

            if missing_required:
                cn_missing = [self.FIELD_CN.get(f, f) for f in missing_required]
                # 作为 warning 继续，但有行级校验兜底
                logger.warning("Missing required columns: %s", cn_missing)
            if mapping_result.unmatched:
                logger.info("Unmatched columns: %s", mapping_result.unmatched)

            # 应用映射
            rows = []
            for raw_row in raw_rows:
                mapped_row = {}
                for original_header, value in raw_row.items():
                    field = mapping_result.matched.get(original_header)
                    if field:
                        mapped_row[field] = value
                    elif original_header in mapping_result.unmatched:
                        mapped_row[original_header.lower().strip()] = value
                # 跳过全空行
                if any(v for v in mapped_row.values() if v):
                    rows.append(mapped_row)

            # 过滤后无有效行
            if not rows:
                import_task.status = ImportStatus.failed
                import_task.failed_records = 1
                import_task.error_log = json.dumps(
                    [{"row": 0, "error": "未检测到有效房源信息，所有数据行均为空。请填写至少一条房源信息后重新上传", "type": "missing_field"}],
                    ensure_ascii=False,
                )
                await self.session.commit()
                return import_task

            # ── Step 3: AI风险预评估（IQR + 孤立森林 + XGBoost）───
            from app.services.risk_evaluator import RiskEvaluator, RiskLevel
            evaluator = RiskEvaluator()
            risk_results = evaluator.evaluate_batch(rows, rent_predictor=None)
            # 建立行号→风险结果的索引
            risk_map = {i + 1: risk_results[i] for i in range(len(rows))}

            # ── Step 4: 逐行校验 & 分级入库 ───────────────
            import_task.total_records = len(rows)
            success = 0
            failed = 0
            pending_review = 0

            for idx, row in enumerate(rows):
                row_num = idx + 1
                try:
                    # 基础校验
                    validated = self._validate_row(row, row_num)
                    if institute_id:
                        validated["institute_id"] = institute_id

                    # 风险判定
                    risk = risk_map.get(row_num)
                    if risk and risk.level == RiskLevel.BLOCK:
                        # 阻断性错误 → 拒绝入库
                        raise ValueError(risk.reason)

                    # 根据风险等级决定入库状态
                    if risk and risk.should_set_pending:
                        validated["status"] = "pending_review"
                        pending_review += 1

                    await self._insert_property(validated, landlord_id)
                    success += 1

                except ValueError as exc:
                    failed += 1
                    err_msg = str(exc)
                    if "此房源已存在" in err_msg or "重复" in err_msg:
                        err_type = "duplicate"
                    elif "缺少必填" in err_msg or "不能为空" in err_msg:
                        err_type = "missing_field"
                    elif "疑似" in err_msg or "低于" in err_msg or "高于" in err_msg or "过小" in err_msg or "过大" in err_msg:
                        err_type = "blocked_risk"  # AI 风险阻断
                    elif "格式错误" in err_msg or "无效" in err_msg or "超出范围" in err_msg:
                        err_type = "format_error"
                    else:
                        err_type = "unknown"
                    errors.append({"row": row_num, "error": err_msg, "type": err_type})

            import_task.success_records = success
            import_task.failed_records = failed
            # 在 error_log 中附加 pending_review 数量
            if pending_review > 0:
                errors.insert(0, {
                    "row": 0,
                    "error": f"AI检测：{pending_review} 条房源标记为「待人工审核」（租金/面积异常），已入库但学生端暂不展示",
                    "type": "ai_review",
                })
            import_task.status = ImportStatus.completed

            if errors:
                import_task.error_log = json.dumps(errors, ensure_ascii=False)

            import_task.updated_at = datetime.now(timezone.utc)
            await self.session.commit()

            if success > 0:
                self._dispatch_batch_embedding()
                self._dispatch_batch_poi_generation(self._created_property_ids)

            return import_task

        except Exception as exc:
            import_task.status = ImportStatus.failed
            import_task.error_log = json.dumps(
                [{"row": 0, "error": str(exc)}],
                ensure_ascii=False,
            )
            await self.session.commit()
            logger.exception("Import task %s failed", import_task.id)
            return import_task

    async def retry_failed(self, import_task: DataImport, landlord_id: int, institute_id: int | None = None) -> DataImport:
        self._created_property_ids = []
        if not import_task.error_log:
            return import_task

        try:
            error_entries = json.loads(import_task.error_log)
        except json.JSONDecodeError:
            return import_task

        if not error_entries:
            return import_task

        import_task.status = ImportStatus.processing
        import_task.failed_records = 0
        import_task.error_log = None
        await self.session.commit()

        new_errors: list[dict] = []
        success_count = 0

        for entry in error_entries:
            row_data = entry.get("data")
            if not row_data:
                new_errors.append(entry)
                continue
            try:
                validated = self._validate_row(row_data, entry.get("row", 0))
                if institute_id:
                    validated["institute_id"] = institute_id
                await self._insert_property(validated, landlord_id)
                success_count += 1
            except ValueError as exc:
                new_errors.append({"row": entry.get("row", 0), "error": str(exc)})

        import_task.success_records += success_count
        import_task.failed_records = len(new_errors)
        if new_errors:
            import_task.error_log = json.dumps(new_errors, ensure_ascii=False)
        import_task.status = ImportStatus.completed
        import_task.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

        if success_count > 0:
            self._dispatch_batch_embedding()
            self._dispatch_batch_poi_generation(self._created_property_ids)

        return import_task

    # ---- private helpers ----

    def _parse_file_with_headers(self, content: bytes, source_type: ImportSourceType) -> tuple[list[dict], list[str]]:
        """Parse file and return (rows, original_headers)"""
        if source_type == ImportSourceType.csv:
            return self._parse_csv_with_headers(content)
        elif source_type == ImportSourceType.excel:
            return self._parse_excel_with_headers(content)
        else:
            raise ValueError(f"Unsupported source type: {source_type}")

    def _detect_encoding(self, content: bytes) -> str:
        """编码自动识别"""
        try:
            import chardet
            detected = chardet.detect(content)
            enc = detected.get('encoding') or 'utf-8'
            logger.info("Detected encoding: %s (confidence: %s)", enc, detected.get('confidence'))
            return enc
        except ImportError:
            # chardet not available, try common encodings
            for enc in ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'iso-8859-1']:
                try:
                    content.decode(enc)
                    return enc
                except (UnicodeDecodeError, LookupError):
                    continue
            return 'utf-8-sig'

    def _parse_csv_with_headers(self, content: bytes) -> tuple[list[dict], list[str]]:
        encoding = self._detect_encoding(content)
        text = content.decode(encoding)
        reader = csv.DictReader(io.StringIO(text))
        rows = []
        headers = []
        for row in reader:
            # Keep original header names for column mapping
            cleaned = {k.strip(): v.strip() if v else "" for k, v in row.items() if k}
            if not headers:
                headers = list(cleaned.keys())
            rows.append(cleaned)
        return rows, headers

    def _parse_excel_with_headers(self, content: bytes) -> tuple[list[dict], list[str]]:
        try:
            import openpyxl
        except ImportError:
            raise ValueError("openpyxl is required for Excel import. Install it: pip install openpyxl")

        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
        ws = wb.active
        if not ws:
            raise ValueError("No active sheet found in Excel file")

        rows_iter = ws.iter_rows(values_only=True)
        headers_raw = next(rows_iter, None)
        if not headers_raw:
            return [], []

        headers = [str(h).strip() if h else "" for h in headers_raw]
        rows = []
        for row in rows_iter:
            if not any(row):
                continue
            cleaned = {}
            for i, value in enumerate(row):
                if i < len(headers) and headers[i]:
                    cleaned[headers[i]] = str(value).strip() if value is not None else ""
            rows.append(cleaned)
        wb.close()
        return rows, headers

    # 中文字段名映射
    FIELD_CN = {
        "title": "房源标题",
        "address": "详细地址",
        "district": "所在区域",
        "price_monthly": "月租金",
        "area_sqm": "面积",
        "bedrooms": "卧室数",
        "bathrooms": "卫生间数",
        "property_type": "房源类型",
        "description": "房源描述",
        "latitude": "纬度",
        "longitude": "经度",
    }

    def _validate_row(self, row: dict, row_num: int) -> dict:
        missing = REQUIRED_FIELDS - set(row.keys())
        if missing:
            cn_missing = [self.FIELD_CN.get(f, f) for f in missing]
            raise ValueError(f"缺少必填字段：{'、'.join(cn_missing)}")

        validated: dict = {}

        title = str(row.get("title", "")).strip()
        if not title:
            raise ValueError("房源标题不能为空")
        validated["title"] = title

        address = str(row.get("address", "")).strip()
        if not address:
            raise ValueError("详细地址不能为空")
        validated["address"] = address

        district = str(row.get("district", "")).strip()
        if not district:
            raise ValueError("所在区域不能为空")
        validated["district"] = district

        try:
            price = Decimal(str(row.get("price_monthly", "0")).strip())
            if price < 0:
                raise ValueError(f"月租金不能为负数，当前值: {price}")
            validated["price_monthly"] = price
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"月租金格式错误，请输入数字。当前值: {row.get('price_monthly', '')}") from exc

        # Optional fields
        if row.get("description"):
            validated["description"] = str(row["description"]).strip()

        if row.get("area_sqm"):
            try:
                area = Decimal(str(row["area_sqm"]).strip())
                if area <= 0:
                    raise ValueError(f"面积必须大于0，当前值: {area}")
                validated["area_sqm"] = area
            except (InvalidOperation, ValueError):
                pass

        if row.get("bedrooms", "").strip():
            try:
                bedrooms = int(row["bedrooms"])
                if bedrooms < 0:
                    raise ValueError(f"卧室数不能为负，当前值: {bedrooms}")
                validated["bedrooms"] = bedrooms
            except ValueError:
                pass

        if row.get("bathrooms", "").strip():
            try:
                bathrooms = int(row["bathrooms"])
                if bathrooms < 0:
                    raise ValueError(f"卫生间数不能为负，当前值: {bathrooms}")
                validated["bathrooms"] = bathrooms
            except ValueError:
                pass

        if row.get("property_type", "").strip():
            ptype = str(row["property_type"]).strip().lower()
            if ptype not in VALID_PROPERTY_TYPES:
                raise ValueError(
                    f"房源类型 '{ptype}' 无效，可选: apartment(公寓) / house(别墅) / studio(单间) / shared(合租)"
                )
            validated["property_type"] = ptype

        if row.get("status", "").strip():
            pstatus = str(row["status"]).strip().lower()
            if pstatus not in VALID_STATUSES:
                raise ValueError(
                    f"房源状态 '{pstatus}' 无效，可选: available(可租) / rented(已租) / maintenance(维护) / offline(下线)"
                )
            validated["status"] = pstatus

        if row.get("latitude", "").strip() and row.get("longitude", "").strip():
            try:
                lat = Decimal(str(row["latitude"]).strip())
                lng = Decimal(str(row["longitude"]).strip())
                if not (-90 <= float(lat) <= 90):
                    raise ValueError(f"纬度超出范围(-90~90): {lat}")
                if not (-180 <= float(lng) <= 180):
                    raise ValueError(f"经度超出范围(-180~180): {lng}")
                validated["latitude"] = lat
                validated["longitude"] = lng
            except (InvalidOperation, ValueError):
                pass

        return validated

    async def _insert_property(self, data: dict, landlord_id: int) -> None:
        # Deduplication: check by title + address
        existing = await self.session.scalar(
            select(Property).where(
                and_(
                    Property.title == data["title"],
                    Property.address == data["address"],
                )
            )
        )
        if existing:
            raise ValueError(f"此房源已存在：标题「{data['title']}」+ 地址「{data['address']}」已有相同房源，请勿重复导入")

        property_obj = Property(
            landlord_id=landlord_id,
            institute_id=data.get("institute_id"),
            title=data["title"],
            address=data["address"],
            district=data["district"],
            price_monthly=data["price_monthly"],
            description=data.get("description"),
            area_sqm=data.get("area_sqm"),
            bedrooms=data.get("bedrooms", 0),
            bathrooms=data.get("bathrooms", 0),
            property_type=PropertyType(data.get("property_type", "apartment")),
            status=PropertyStatus(data.get("status", "available")),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
        )
        self.session.add(property_obj)
        await self.session.flush()
        self._created_property_ids.append(property_obj.id)

    @staticmethod
    def _dispatch_batch_embedding() -> None:
        def _run() -> None:
            try:
                from app.tasks.import_tasks import batch_embedding_new_properties
                batch_embedding_new_properties.delay()
            except Exception:
                logger.exception("Failed to dispatch batch embedding task")

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def _dispatch_batch_poi_generation(self, property_ids: list[int]) -> None:
        if not property_ids:
            return

        def _run() -> None:
            try:
                from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

                from app.core.config import get_settings
                from app.models.property import Property
                from app.services.poi_service import POIService

                async def _generate() -> None:
                    engine = create_async_engine(get_settings().database_url)
                    try:
                        maker = async_sessionmaker(engine, expire_on_commit=False)
                        async with maker() as session:
                            poi_service = POIService(session)
                            for property_id in property_ids:
                                try:
                                    prop = await session.get(Property, property_id)
                                    if prop:
                                        await poi_service.generate_poi_for_property(prop, force=True)
                                except Exception:
                                    logger.exception("Failed to generate POI for imported property %s", property_id)
                    finally:
                        await engine.dispose()

                asyncio.run(_generate())
            except Exception:
                logger.exception("Failed to dispatch batch POI generation")

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
