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
        mode: str = "flexible",
    ) -> tuple[DataImport, list[dict] | None]:
        self._created_property_ids = []
        # 保存关键属性到局部变量，避免 commit 后访问过期对象触发 MissingGreenlet
        source_type = import_task.source_type
        task_id = import_task.id
        import_task.status = ImportStatus.processing
        await self.session.commit()
        await self.session.refresh(import_task)

        errors: list[dict] = []
        try:
            # ── Step 1: 解析文件 ───────────────────────
            raw_rows, raw_headers = self._parse_file_with_headers(file_content, source_type)

            # 检查空文件
            if not raw_headers:
                import_task.status = ImportStatus.failed
                import_task.failed_records = 1
                import_task.error_log = json.dumps(
                    [{"row": 0, "error": "文件无内容，未检测到表头行。请使用模板填写数据后重新上传", "type": "missing_field"}],
                    ensure_ascii=False,
                )
                await self.session.commit()
                await self.session.refresh(import_task)
                return import_task, None

            # 检查只有表头无数据
            if not raw_rows:
                import_task.status = ImportStatus.failed
                import_task.failed_records = 1
                import_task.error_log = json.dumps(
                    [{"row": 0, "error": "未检测到有效房源信息，仅有表头无数据行。请在表头下方填写房源信息", "type": "missing_field"}],
                    ensure_ascii=False,
                )
                await self.session.commit()
                await self.session.refresh(import_task)
                return import_task, None

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
                await self.session.refresh(import_task)
                return import_task, None

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
                await self.session.refresh(import_task)
                return import_task, None

            # ── Step 3: 逐行全量校验 → 分离有效/失败行 ──
            import_task.total_records = len(rows)
            success = 0
            failed = 0
            pending_review = 0

            is_strict = (mode == "strict")
            row_results: list[dict] = []
            valid_rows: list[dict] = []        # 校验通过的行（待入库）
            valid_row_indices: list[int] = []   # 对应原始行号
            validated_list: list[dict] = []     # 校验通过后的数据

            for idx, row in enumerate(rows):
                row_num = idx + 1
                validated, row_errors, row_warnings = self._validate_row(row, row_num)

                if row_errors:
                    failed += 1
                    row_results.append({
                        "row": row_num,
                        "status": "failed",
                        "errors": row_errors,
                        "warnings": row_warnings,
                    })
                    continue

                # 通过基础校验 → 加入有效行队列
                if institute_id:
                    validated["institute_id"] = institute_id
                valid_rows.append(row)
                valid_row_indices.append(row_num)
                validated_list.append(validated)

            # ── Step 4: IQR 异常区间检测（仅对校验通过的行）───
            iqr_warnings_map: dict[int, list[dict]] = {}
            if valid_rows:
                from app.services.outlier_detector import IQROutlierDetector

                # 区域最低参考价（元）
                DISTRICT_FLOOR: dict[str, float] = {
                    "工业园区": 800, "姑苏区": 600, "高新区": 600,
                    "吴中区": 500, "相城区": 400, "吴江区": 400,
                    "昆山市": 500, "太仓市": 400, "常熟市": 400, "张家港市": 400,
                }
                # 户型面积参考范围 (㎡)
                TYPE_AREA: dict[str, tuple[float, float]] = {
                    "studio": (10, 60), "apartment": (30, 200),
                    "house": (40, 500), "shared": (10, 40),
                }

                iqr = IQROutlierDetector()

                # 用 2.0 乘数跑宽松 IQR（抓极端值）
                iqr_price_loose = set(iqr.detect(valid_rows, "price_monthly", multiplier=2.0))
                iqr_area_loose = set(iqr.detect(valid_rows, "area_sqm", multiplier=2.0))

                # 价格底价单独算：取后25%的中位数作为"正常低价区"
                prices_sorted = sorted(self._to_num(r.get("price_monthly", 0)) for r in valid_rows if self._to_num(r.get("price_monthly", 0)) > 0)
                p25_median = prices_sorted[len(prices_sorted)//4] if len(prices_sorted) >= 4 else 0

                for i in range(len(valid_rows)):
                    orig_row_num = valid_row_indices[i]
                    iqr_w = []
                    price_val = self._to_num(valid_rows[i].get("price_monthly", ""))
                    area_val = self._to_num(valid_rows[i].get("area_sqm", ""))
                    district = str(valid_rows[i].get("district", ""))
                    ptype = str(valid_rows[i].get("property_type", "1-bed")).lower()

                    # IQR 宽松检测
                    price_iqr_hit = i in iqr_price_loose
                    area_iqr_hit = i in iqr_area_loose

                    # 区域底价检测：低于区域参考价30%
                    dist_floor = DISTRICT_FLOOR.get(district, 500)
                    price_too_low = price_val > 0 and price_val < dist_floor * 0.4

                    # 面积异常检测
                    area_anomaly = False
                    ar = TYPE_AREA.get(ptype)
                    if ar and area_val > 0:
                        if area_val < ar[0] * 0.5 or area_val > ar[1] * 1.5:
                            area_anomaly = True

                    if price_val > 0 and (price_iqr_hit or price_too_low):
                        if price_too_low and not price_iqr_hit:
                            iqr_w.append({"field": "_iqr", "error": f"月租 {price_val:.0f} 元低于{district}最低参考价{dist_floor:.0f}元的40%（异常区间检测）", "type": "iqr_outlier"})
                        elif price_val < p25_median * 0.3 and p25_median > 0:
                            iqr_w.append({"field": "_iqr", "error": f"月租 {price_val:.0f} 元远低于同批次低价区中位数{p25_median:.0f}元（异常区间检测）", "type": "iqr_outlier"})
                        else:
                            iqr_w.append({"field": "_iqr", "error": f"月租 {price_val:.0f} 元偏离同批次中位数区间（异常区间检测）", "type": "iqr_outlier"})

                    if area_val > 0 and (area_iqr_hit or area_anomaly):
                        if area_anomaly and not area_iqr_hit:
                            iqr_w.append({"field": "_iqr", "error": f"面积 {area_val:.0f}㎡ 超出{ptype}正常区间{ar[0]:.0f}-{ar[1]:.0f}㎡（异常区间检测）", "type": "iqr_outlier"})
                        else:
                            iqr_w.append({"field": "_iqr", "error": f"面积 {area_val:.1f}㎡ 偏离同批次中位数区间（异常区间检测）", "type": "iqr_outlier"})

                    if iqr_w:
                        iqr_warnings_map[orig_row_num] = iqr_w

            # ── Step 5: 逐行入库有效行 ──
            for vi, validated in enumerate(validated_list):
                row_num = valid_row_indices[vi]
                row_warnings: list[dict] = []
                iqr_w = iqr_warnings_map.get(row_num, [])
                row_warnings.extend(iqr_w)
                try:
                    await self._insert_property(validated, landlord_id)
                    success += 1
                    row_results.append({
                        "row": row_num,
                        "status": "success",
                        "data": {
                            "title": validated.get("title", ""),
                            "address": validated.get("address", ""),
                            "district": validated.get("district", ""),
                            "price_monthly": str(validated.get("price_monthly", "")),
                            "area_sqm": str(validated.get("area_sqm", "")) if validated.get("area_sqm") else "",
                            "property_type": validated.get("property_type", ""),
                        },
                        "warnings": row_warnings if row_warnings else None,
                    })
                except ValueError as exc:
                    failed += 1
                    err_msg = str(exc)
                    insert_errors = []
                    if "此房源已存在" in err_msg or "重复" in err_msg:
                        insert_errors.append({"field": "_duplicate", "error": err_msg, "type": "duplicate"})
                    else:
                        insert_errors.append({"field": "_unknown", "error": err_msg, "type": "unknown"})
                    row_results.append({
                        "row": row_num,
                        "status": "failed",
                        "errors": insert_errors,
                        "warnings": row_warnings,
                    })

            # ── 严格模式：有错则全部回滚 ──
            if is_strict and failed > 0:
                if success > 0:
                    await self.session.rollback()
                import_task.total_records = len(rows)
                import_task.success_records = 0
                import_task.failed_records = len(rows)
                import_task.status = ImportStatus.failed
                # 仍保存 rows 供前端展示
                strict_errors = []
                for r in row_results:
                    if r["status"] == "failed":
                        for e in r.get("errors", []):
                            strict_errors.append({"row": r["row"], "error": e["error"], "type": e.get("type", "unknown")})
                import_task.error_log = json.dumps(strict_errors, ensure_ascii=False)
                import_task.updated_at = datetime.now(timezone.utc)
                await self.session.commit()
                await self.session.refresh(import_task)
                # 把 rows 也存到 error_log 旁边的 meta（通过 updated_at 后带在返回 dict 里）
                return import_task, None

            import_task.success_records = success
            import_task.failed_records = failed
            import_task.status = ImportStatus.completed

            # 在 error_log 中附加异常区间检测摘要
            flat_errors: list[dict] = []
            range_rows = sorted(set(
                r["row"] for r in row_results if r["status"] in ("success", "warning")
                and r.get("warnings") and any(w["type"] == "iqr_outlier" for w in (r["warnings"] or []))
            ))
            if range_rows:
                flat_errors.append({
                    "row": 0,
                    "error": f"异常区间检测：共{len(range_rows)}行房源存在区间数值异常，数据已完成入库，请核实对应房源后再上架",
                    "type": "review_summary",
                    "range_error_rows": range_rows,
                })
            for r in row_results:
                if r["status"] == "failed":
                    for e in r.get("errors", []):
                        flat_errors.append({"row": r["row"], "error": e["error"], "type": e["type"]})

            if flat_errors:
                import_task.error_log = json.dumps(flat_errors, ensure_ascii=False)

            import_task.updated_at = datetime.now(timezone.utc)
            await self.session.commit()

            if success > 0:
                self._dispatch_batch_embedding()
                self._dispatch_batch_poi_generation(self._created_property_ids)

            await self.session.refresh(import_task)

            return import_task, row_results

        except Exception as exc:
            logger.exception("Import task %s failed", task_id)
            # 合并当前 session 中的 import_task 以安全更新状态
            try:
                merged = await self.session.merge(import_task)
                merged.status = ImportStatus.failed
                merged.error_log = json.dumps(
                    [{"row": 0, "error": str(exc)}],
                    ensure_ascii=False,
                )
                await self.session.commit()
                await self.session.refresh(merged)
                return merged, None
            except Exception:
                logger.exception("Failed to update import task %s as failed", task_id)
                await self.session.rollback()
                return import_task, None

    async def preview_only(
        self,
        import_task: DataImport,
        file_content: bytes,
        landlord_id: int,
        institute_id: int | None = None,
    ) -> tuple[DataImport, list[dict]]:
        """仅预览：解析 + 校验 + IQR/孤立森林，不入库。
        返回 (import_task, row_results)，row_results 中每行含 errors/warnings/iqr/iforest。
        同时把原始行数据存入 import_task.error_log 供 confirm_import 复用。
        """
        source_type = import_task.source_type
        import_task.status = ImportStatus.pending  # preview 状态
        await self.session.commit()

        # ── 解析文件 ──
        raw_rows, raw_headers = self._parse_file_with_headers(file_content, source_type)
        if not raw_headers or not raw_rows:
            import_task.status = ImportStatus.failed
            import_task.error_log = json.dumps(
                [{"row": 0, "error": "文件无内容或仅有表头", "type": "missing_field"}],
                ensure_ascii=False,
            )
            await self.session.commit()
            await self.session.refresh(import_task)
            return import_task, []

        # ── 列名映射 ──
        mapper = ColumnMapper()
        mapping_result = mapper.match(raw_headers)
        mapped_fields = set(mapping_result.matched.values())
        missing_required = REQUIRED_FIELDS - mapped_fields
        if missing_required == REQUIRED_FIELDS:
            import_task.status = ImportStatus.failed
            import_task.error_log = json.dumps(
                [{"row": 0, "error": f"无法识别必填列。检测到的列：{'、'.join(raw_headers[:8])}", "type": "missing_field"}],
                ensure_ascii=False,
            )
            await self.session.commit()
            await self.session.refresh(import_task)
            return import_task, []

        rows = []
        for raw_row in raw_rows:
            mapped_row = {}
            for original_header, value in raw_row.items():
                field = mapping_result.matched.get(original_header)
                if field:
                    mapped_row[field] = value
            if any(v for v in mapped_row.values() if v):
                rows.append(mapped_row)

        if not rows:
            import_task.status = ImportStatus.failed
            import_task.error_log = json.dumps(
                [{"row": 0, "error": "所有数据行为空", "type": "missing_field"}],
                ensure_ascii=False,
            )
            await self.session.commit()
            await self.session.refresh(import_task)
            return import_task, []

        import_task.total_records = len(rows)
        row_results: list[dict] = []

        # ── Step 1: 逐行校验 ──
        valid_rows_data: list[dict] = []      # 校验通过的行数据（供 IQR/IF 用）
        valid_row_indices: list[int] = []      # 对应原始行号

        for idx, row in enumerate(rows):
            row_num = idx + 1
            validated, row_errors, row_warnings = self._validate_row(row, row_num)

            if row_errors:
                row_results.append({
                    "row": row_num,
                    "status": "failed",
                    "errors": row_errors,
                    "warnings": row_warnings,
                    "data_preview": {k: str(v) for k, v in row.items() if v},
                    "iqr_flagged": False,
                    "iforest_flagged": False,
                })
                continue

            row_results.append({
                "row": row_num,
                "status": "valid",
                "errors": [],
                "warnings": row_warnings,
                "data": {
                    "title": validated.get("title", ""),
                    "address": validated.get("address", ""),
                    "district": validated.get("district", ""),
                    "price_monthly": str(validated.get("price_monthly", "")),
                    "area_sqm": str(validated.get("area_sqm", "")) if validated.get("area_sqm") else "",
                    "property_type": validated.get("property_type", ""),
                },
                "iqr_flagged": False,
                "iforest_flagged": False,
            })
            valid_rows_data.append(row)
            valid_row_indices.append(row_num)

        # ── Step 2: IQR + 孤立森林（仅对校验通过的行）───
        if valid_rows_data:
            from app.services.risk_evaluator import RiskEvaluator
            evaluator = RiskEvaluator()
            ai_results = evaluator.evaluate_warnings_only(valid_rows_data, rent_predictor=None)

            for ar in ai_results:
                result_idx = ar["row_idx"] - 1
                # 找到对应的 row_results 条目
                orig_row_num = valid_row_indices[result_idx]
                for rr in row_results:
                    if rr["row"] == orig_row_num and rr["status"] == "valid":
                        if ar["iqr_flagged"]:
                            rr["iqr_flagged"] = True
                            rr.setdefault("warnings", [])
                            for w in ar["iqr_warnings"]:
                                (rr["warnings"]).append({"field": "_iqr", "error": w, "type": "iqr_outlier"})
                        if ar["iforest_flagged"]:
                            rr["iforest_flagged"] = True
                            rr.setdefault("warnings", [])
                            for w in ar["iforest_warnings"]:
                                (rr["warnings"]).append({"field": "_iforest", "error": w, "type": "iforest_outlier"})
                        break

        # ── 保存原始数据到 error_log 供 confirm_import 用 ──
        import_task.error_log = json.dumps(
            {
                "_raw_rows": rows,
                "_institute_id": institute_id,
                "_validated_rows": [
                    {
                        "row_num": valid_row_indices[i],
                        "validated": {},  # 会在 confirm 时重新 _validate_row
                    }
                    for i in range(len(valid_rows_data))
                ],
            },
            ensure_ascii=False,
            default=str,
        )
        import_task.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(import_task)

        return import_task, row_results

    async def confirm_import(
        self,
        import_task: DataImport,
        landlord_id: int,
        skip_rows: list[int] | None = None,
    ) -> tuple[DataImport, list[dict]]:
        """确认导入：根据预览中被忽略的行号，仅导入剩余行。
        参数:
            import_task: 预览阶段创建的 import task
            landlord_id: 房东 ID
            skip_rows: 用户选择忽略（不导入）的行号列表
        返回:
            (import_task, row_results)
        """
        skip_set = set(skip_rows or [])
        self._created_property_ids = []

        # 重新解析原始数据
        try:
            saved = json.loads(import_task.error_log) if import_task.error_log else {}
        except json.JSONDecodeError:
            saved = {}

        raw_rows = saved.get("_raw_rows", [])
        institute_id = saved.get("_institute_id")
        if not raw_rows:
            import_task.status = ImportStatus.failed
            import_task.error_log = json.dumps([{"row": 0, "error": "预览数据已过期，请重新上传文件"}], ensure_ascii=False)
            await self.session.commit()
            return import_task, []

        import_task.status = ImportStatus.processing
        import_task.failed_records = 0
        await self.session.commit()

        row_results: list[dict] = []
        success = 0
        failed = 0

        for idx, row in enumerate(raw_rows):
            row_num = idx + 1

            # 用户选择忽略 → 不导入
            if row_num in skip_set:
                row_results.append({
                    "row": row_num,
                    "status": "skipped",
                    "errors": [],
                    "warnings": [],
                })
                continue

            validated, row_errors, row_warnings = self._validate_row(row, row_num)

            if row_errors:
                failed += 1
                row_results.append({
                    "row": row_num,
                    "status": "failed",
                    "errors": row_errors,
                    "warnings": row_warnings,
                })
                continue

            if institute_id:
                validated["institute_id"] = institute_id

            try:
                await self._insert_property(validated, landlord_id)
                success += 1
                row_results.append({
                    "row": row_num,
                    "status": "success",
                    "data": {
                        "title": validated.get("title", ""),
                        "address": validated.get("address", ""),
                        "district": validated.get("district", ""),
                        "price_monthly": str(validated.get("price_monthly", "")),
                        "area_sqm": str(validated.get("area_sqm", "")) if validated.get("area_sqm") else "",
                        "property_type": validated.get("property_type", ""),
                    },
                    "warnings": row_warnings if row_warnings else None,
                })
            except ValueError as exc:
                failed += 1
                row_results.append({
                    "row": row_num,
                    "status": "failed",
                    "errors": [{"field": "_duplicate", "error": str(exc), "type": "duplicate"}],
                })

        import_task.total_records = len(raw_rows)
        import_task.success_records = success
        import_task.failed_records = failed
        import_task.skipped_count = len(skip_set)  # type: ignore[attr-defined]
        import_task.status = ImportStatus.completed
        import_task.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

        if success > 0:
            self._dispatch_batch_embedding()
            self._dispatch_batch_poi_generation(self._created_property_ids)

        await self.session.refresh(import_task)
        return import_task, row_results

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
            validated, row_errors, _row_warnings = self._validate_row(row_data, entry.get("row", 0))
            if row_errors:
                for e in row_errors:
                    new_errors.append({"row": entry.get("row", 0), "error": e["error"], "type": e["type"]})
                continue
            try:
                if institute_id:
                    validated["institute_id"] = institute_id
                await self._insert_property(validated, landlord_id)
                success_count += 1
            except ValueError as exc:
                new_errors.append({"row": entry.get("row", 0), "error": str(exc), "type": "duplicate"})

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

    @staticmethod
    def _to_num(val) -> float:
        try: return float(val) if val else 0.0
        except (ValueError, TypeError): return 0.0

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

    def _validate_row(self, row: dict, row_num: int) -> tuple[dict | None, list[dict], list[dict]]:
        """校验单行数据，收集全部错误和警告（不抛异常）。
        返回: (validated_data 或 None, errors[], warnings[])
          - errors: 阻断性错误（缺必填、格式错误）
          - warnings: 非阻断（可选字段格式错，已自动忽略）
        """
        errors: list[dict] = []
        warnings: list[dict] = []
        validated: dict = {}

        # ── 必填字段检查 ──
        for f in REQUIRED_FIELDS:
            val = str(row.get(f, "")).strip()
            if not val:
                errors.append({
                    "field": f,
                    "error": f"{self.FIELD_CN.get(f, f)}不能为空",
                    "type": "missing_field",
                })

        # ── title ──
        title = str(row.get("title", "")).strip()
        if title:
            validated["title"] = title

        # ── address ──
        address = str(row.get("address", "")).strip()
        if address:
            validated["address"] = address

        # ── district ──
        district = str(row.get("district", "")).strip()
        if district:
            validated["district"] = district

        # ── price_monthly ──
        price_raw = str(row.get("price_monthly", "")).strip()
        if price_raw:
            try:
                price = Decimal(price_raw)
                if price < 0:
                    errors.append({
                        "field": "price_monthly",
                        "error": f"月租金不能为负数，当前值: {price}",
                        "type": "format_error",
                    })
                else:
                    validated["price_monthly"] = price
            except (InvalidOperation, ValueError):
                errors.append({
                    "field": "price_monthly",
                    "error": f"月租金格式错误，请输入数字。当前值: {price_raw}",
                    "type": "format_error",
                })

        # ── description (可选) ──
        if row.get("description", "").strip():
            validated["description"] = str(row["description"]).strip()

        # ── area_sqm (可选) ──
        area_raw = str(row.get("area_sqm", "")).strip()
        if area_raw:
            try:
                area = Decimal(area_raw)
                if area <= 0:
                    warnings.append({
                        "field": "area_sqm",
                        "error": f"面积必须大于0，当前值{area}已忽略",
                        "type": "format_error",
                    })
                else:
                    validated["area_sqm"] = area
            except (InvalidOperation, ValueError):
                warnings.append({
                    "field": "area_sqm",
                    "error": f"面积格式错误，已忽略。当前值: {area_raw}",
                    "type": "format_error",
                })

        # ── bedrooms (可选) ──
        br_raw = str(row.get("bedrooms", "")).strip()
        if br_raw:
            try:
                bedrooms = int(br_raw)
                if bedrooms < 0:
                    warnings.append({
                        "field": "bedrooms",
                        "error": f"卧室数不能为负，已忽略。当前值: {bedrooms}",
                        "type": "format_error",
                    })
                else:
                    validated["bedrooms"] = bedrooms
            except ValueError:
                warnings.append({
                    "field": "bedrooms",
                    "error": f"卧室数格式错误，已忽略。当前值: {br_raw}",
                    "type": "format_error",
                })

        # ── bathrooms (可选) ──
        bh_raw = str(row.get("bathrooms", "")).strip()
        if bh_raw:
            try:
                bathrooms = int(bh_raw)
                if bathrooms < 0:
                    warnings.append({
                        "field": "bathrooms",
                        "error": f"卫生间数不能为负，已忽略。当前值: {bathrooms}",
                        "type": "format_error",
                    })
                else:
                    validated["bathrooms"] = bathrooms
            except ValueError:
                warnings.append({
                    "field": "bathrooms",
                    "error": f"卫生间数格式错误，已忽略。当前值: {bh_raw}",
                    "type": "format_error",
                })

        # ── property_type (可选) ──
        ptype_raw = str(row.get("property_type", "")).strip()
        if ptype_raw:
            ptype = ptype_raw.lower()
            if ptype not in VALID_PROPERTY_TYPES:
                errors.append({
                    "field": "property_type",
                    "error": f"房源类型 '{ptype_raw}' 无效，可选: apartment(公寓) / house(别墅) / studio(单间) / shared(合租)",
                    "type": "format_error",
                })
            else:
                validated["property_type"] = ptype

        # ── status (可选) ──
        status_raw = str(row.get("status", "")).strip()
        if status_raw:
            pstatus = status_raw.lower()
            if pstatus not in VALID_STATUSES:
                warnings.append({
                    "field": "status",
                    "error": f"房源状态 '{status_raw}' 无效，已忽略。可选: available/rented/maintenance/offline",
                    "type": "format_error",
                })
            else:
                validated["status"] = pstatus

        # ── latitude / longitude (可选) ──
        lat_raw = str(row.get("latitude", "")).strip()
        lng_raw = str(row.get("longitude", "")).strip()
        if lat_raw and lng_raw:
            lat_ok = False
            lng_ok = False
            lat_val = None
            lng_val = None
            try:
                lat_val = Decimal(lat_raw)
                if -90 <= float(lat_val) <= 90:
                    lat_ok = True
                else:
                    warnings.append({
                        "field": "latitude",
                        "error": f"纬度超出范围(-90~90)，当前值{lat_val}已忽略",
                        "type": "format_error",
                    })
            except (InvalidOperation, ValueError):
                warnings.append({
                    "field": "latitude",
                    "error": f"纬度格式错误，已忽略。当前值: {lat_raw}",
                    "type": "format_error",
                })
            try:
                lng_val = Decimal(lng_raw)
                if -180 <= float(lng_val) <= 180:
                    lng_ok = True
                else:
                    warnings.append({
                        "field": "longitude",
                        "error": f"经度超出范围(-180~180)，当前值{lng_val}已忽略",
                        "type": "format_error",
                    })
            except (InvalidOperation, ValueError):
                warnings.append({
                    "field": "longitude",
                    "error": f"经度格式错误，已忽略。当前值: {lng_raw}",
                    "type": "format_error",
                })
            if lat_ok and lng_ok:
                validated["latitude"] = lat_val
                validated["longitude"] = lng_val

        # ── deposit_amount (可选) ──
        dep_raw = str(row.get("deposit_amount", "")).strip()
        if dep_raw:
            try:
                dep = Decimal(dep_raw)
                if dep >= 0:
                    validated["deposit_amount"] = dep
                else:
                    warnings.append({
                        "field": "deposit_amount",
                        "error": f"押金不能为负，已忽略。当前值: {dep}",
                        "type": "format_error",
                    })
            except (InvalidOperation, ValueError):
                warnings.append({
                    "field": "deposit_amount",
                    "error": f"押金格式错误，已忽略。当前值: {dep_raw}",
                    "type": "format_error",
                })

        # ── service_fee_rate (可选) ──
        fee_raw = str(row.get("service_fee_rate", "")).strip()
        if fee_raw:
            try:
                fee = float(fee_raw)
                if 0 <= fee <= 1:
                    validated["service_fee_rate"] = fee
                else:
                    warnings.append({
                        "field": "service_fee_rate",
                        "error": f"服务费率应在0~1之间，已忽略。当前值: {fee}",
                        "type": "format_error",
                    })
            except ValueError:
                warnings.append({
                    "field": "service_fee_rate",
                    "error": f"服务费率格式错误，已忽略。当前值: {fee_raw}",
                    "type": "format_error",
                })

        # ── room_number / floor / building_name (可选透传) ──
        for f_opt in ("room_number", "floor", "building_name", "orientation"):
            v = str(row.get(f_opt, "")).strip()
            if v:
                try:
                    validated[f_opt] = int(v) if f_opt == "floor" else v
                except ValueError:
                    validated[f_opt] = v  # floor 非数字也保留原样

        if errors:
            return None, errors, warnings
        return validated, [], warnings

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
            property_type=PropertyType(data.get("property_type", "1-bed")),
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
        """批量导入后异步生成地图 POI（Celery 任务，不阻塞）"""
        if not property_ids:
            return

        def _run() -> None:
            try:
                from app.tasks.poi_tasks import generate_full_poi_for_property
                for property_id in property_ids:
                    generate_full_poi_for_property.delay(property_id)
            except Exception:
                logger.exception("Failed to dispatch batch map POI generation")

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
