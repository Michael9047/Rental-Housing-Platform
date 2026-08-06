"""将 BM PDF 模板与订单不可信任数据生成单一私有合同快照。"""

from __future__ import annotations

import hashlib
import io
from datetime import datetime, timezone
from typing import Any

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.contract import Contract
from app.models.contract_template import ContractTemplate
from app.services.contract_service import ContractService
from app.services.private_object_storage import PrivateObjectStorage


class ContractRenderError(Exception):
    """合同填充不满足业务前提时的可预期错误。"""

    def __init__(self, message: str, missing_fields: list[str] | None = None) -> None:
        super().__init__(message)
        self.missing_fields = missing_fields or []


class ContractPdfRenderService:
    """合同正式文件只使用一份渲染后快照，绝不将原始空白模板作为租客合同返回。"""

    _field_labels = {
        "tenant_name": "租客姓名",
        "tenant_phone": "租客电话",
        "tenant_email": "租客邮箱",
        "tenant_school": "租客学校",
        "tenant_passport": "租客护照号",
        "property_name": "公寓名称",
        "property_address": "公寓地址",
        "unit_type_name": "户型名称",
        "room_number": "房号",
        "monthly_rent": "月租金",
        "deposit_amount": "押金",
        "lease_start": "租期起始日",
        "lease_end": "租期结束日",
        "sign_date": "生成日期",
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.storage = PrivateObjectStorage()

    async def render_current_contract(self, contract: Contract) -> bytes:
        """幂等地取得正式 PDF。首次渲染才写入合同快照，后续一律读取同一文件。"""
        if contract.file_path and contract.pdf_status == "ready":
            return self.storage.get(contract.file_path)

        booking = await self.session.get(Booking, contract.booking_id)
        if not booking:
            raise ContractRenderError("合同对应订单不存在")
        context = await ContractService(self.session).build_contract_context(booking.id)
        context["agreement_number"] = contract.agreement_number

        template = await self.session.scalar(
            select(ContractTemplate)
            .where(
                ContractTemplate.institute_id == booking.institute_id,
                ContractTemplate.is_active.is_(True),
            )
            .order_by(ContractTemplate.updated_at.desc(), ContractTemplate.created_at.desc())
        )
        # 演示模式下，未设置字段坐标的 BM 原始 PDF 不能阻断已支付订单。
        # 它仍保留为原始模板；租客仅收到后端生成的默认实验合同快照。
        if template and (template.field_positions or {}):
            pdf = self._render_template(template, context)
            template_kind = "bm_template"
            template_id = template.id
        else:
            pdf = self._render_default_experiment_contract(context)
            template_kind = "system_default_experiment"
            template_id = None

        content_hash = hashlib.sha256(pdf).hexdigest()
        generated_at = datetime.now(timezone.utc)
        storage_key = f"contracts/{contract.id}/v{contract.version}-{content_hash[:16]}.pdf"
        self.storage.put(storage_key, pdf)
        snapshot = dict(contract.snapshot or {})
        snapshot.update(
            {
                "content_hash": content_hash,
                "agreement_number": contract.agreement_number,
                "rendered_template_id": template_id,
                "template_kind": template_kind,
                "rendered_at": generated_at.isoformat(),
            }
        )
        contract.file_path = storage_key
        contract.pdf_status = "ready"
        contract.pdf_last_error = None
        contract.content_hash = content_hash
        contract.snapshot = snapshot
        await self.session.commit()
        return pdf

    def _render_template(self, template: ContractTemplate, context: dict[str, Any]) -> bytes:
        self.validate_template_context(template, context)
        positions = template.field_positions or {}

        try:
            original = PdfReader(io.BytesIO(self.storage.get(template.file_path)))
        except (FileNotFoundError, ValueError) as exc:
            raise ContractRenderError("BM 合同模板文件不存在") from exc

        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        writer = PdfWriter()
        for page_index, page in enumerate(original.pages, start=1):
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)
            overlay_stream = io.BytesIO()
            overlay = canvas.Canvas(overlay_stream, pagesize=(width, height))
            overlay.setFont("STSong-Light", 10)
            for key, raw_position in positions.items():
                if not isinstance(raw_position, dict) or int(raw_position.get("page", 1)) != page_index:
                    continue
                value = context.get(key)
                if value in (None, ""):
                    continue
                x = float(raw_position.get("x", 0))
                y = float(raw_position.get("y", 0))
                font_size = max(6, min(int(raw_position.get("font_size", 12)), 48))
                # 保存的坐标以页面左上为原点，ReportLab 以左下为原点。
                overlay.setFont("STSong-Light", font_size)
                overlay.drawString(x, height - y - font_size, str(value))
            overlay.save()
            overlay_page = PdfReader(io.BytesIO(overlay_stream.getvalue())).pages[0]
            page.merge_page(overlay_page)
            writer.add_page(page)
        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()

    @classmethod
    def validate_template_context(cls, template: ContractTemplate, context: dict[str, Any]) -> None:
        """在锁定房号前验证模板映射，防止已支付订单进入一个无法填充的状态。"""
        positions = template.field_positions or {}
        if not positions:
            raise ContractRenderError(
                "BM 合同模板未配置自动填充字段，不能发送空白正式合同",
                list(cls._field_labels),
            )
        missing_values = [
            key for key in positions
            if key not in context or context.get(key) in (None, "")
        ]
        if missing_values:
            labels = [cls._field_labels.get(key, key) for key in missing_values]
            raise ContractRenderError("无法生成合同，缺少：" + "、".join(labels), missing_values)

    @staticmethod
    def _render_default_experiment_contract(context: dict[str, Any]) -> bytes:
        """演示模式使用的本地实验合同，绝不标记为生产正式合同。"""
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        output = io.BytesIO()
        doc = canvas.Canvas(output, pagesize=A4)
        doc.setTitle("System Default Experiment Contract")
        doc.setFont("STSong-Light", 16)
        doc.drawString(56, 790, "系统默认实验合同（仅用于本地测试）")
        doc.setFont("STSong-Light", 10)
        y = 760
        for label, key in [
            ("合同编号", "agreement_number"), ("订单编号", "order_number"),
            ("租客", "tenant_name_cn"), ("公寓", "property_name"),
            ("地址", "property_address"), ("户型", "unit_type_name"),
            ("房号", "room_number"), ("租期", "commencement_date"),
            ("结束日", "end_date"), ("租期月数", "lease_months"),
            ("月租", "monthly_rent"), ("押金", "security_deposit"),
        ]:
            doc.drawString(56, y, f"{label}: {context.get(key) or '未配置'}")
            y -= 24
        doc.drawString(56, y - 12, "实验环境使用模拟签署，不具法律效力。")
        doc.save()
        return output.getvalue()
